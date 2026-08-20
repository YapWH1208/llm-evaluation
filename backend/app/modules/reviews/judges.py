from __future__ import annotations

import secrets
from collections.abc import Mapping
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from app.core.errors import ConflictError, NotFoundError
from app.core.secrets import SecretCipher
from app.infrastructure.providers.contracts import ModelExecutor
from app.modules.reviews.ports import JudgeRepository
from app.modules.reviews.scoring import (
    DEFAULT_PAIRWISE_JUDGE_SYSTEM_MESSAGE,
    DEFAULT_SINGLE_JUDGE_SYSTEM_MESSAGE,
    JudgeScoringError,
    build_pairwise_judge_input,
    build_single_judge_input,
    parse_judge_response,
)


_FROZEN_ENDPOINT_FIELDS = (
    "base_url",
    "model_name",
    "protocol_profile",
    "default_request_body",
    "timeout_seconds",
    "custom_headers",
    "input_cost_per_million",
    "output_cost_per_million",
)


class JudgeService:
    """LLM-as-judge behavior shared by SQLite, Mongo, APIs, and automatic scoring."""

    def __init__(self, repository: JudgeRepository) -> None:
        self._repository = repository

    def assess(
        self,
        *,
        sample_attempt_id: str,
        judge_endpoint_id: str,
        rubric: dict[str, Any] | None,
        cipher: SecretCipher,
        model_executor: ModelExecutor,
        system_message: str = DEFAULT_SINGLE_JUDGE_SYSTEM_MESSAGE,
        endpoint_override: Mapping[str, object] | None = None,
    ) -> Any:
        attempt = self._require_attempt(sample_attempt_id)
        endpoint = self._require_endpoint(judge_endpoint_id)
        self._require_independent_judge(attempt, endpoint)
        assessment = self._repository.create_assessment(
            _assessment_values(
                sample_attempt_id=sample_attempt_id,
                judge_endpoint_id=judge_endpoint_id,
                rubric=rubric or {},
            )
        )
        input_snapshot = build_single_judge_input(
            system_message=system_message,
            rubric=rubric or {},
            input_snapshot=_value(attempt, "input_snapshot"),
            reference_snapshot=_value(attempt, "reference_snapshot"),
            prediction=_value(attempt, "parsed_prediction"),
        )
        execution_endpoint = _execution_endpoint(endpoint, endpoint_override)
        result = model_executor.execute(
            execution_endpoint,
            cipher.decrypt(str(_value(endpoint, "encrypted_api_key"))),
            input_snapshot,
        )
        return self._finish_assessment(str(_value(assessment, "id")), execution_endpoint, result)

    def assess_pairwise(
        self,
        *,
        sample_attempt_id: str,
        comparison_sample_attempt_id: str,
        judge_endpoint_id: str,
        rubric: dict[str, Any] | None,
        swap_test: bool,
        cipher: SecretCipher,
        model_executor: ModelExecutor,
    ) -> list[Any]:
        attempt = self._require_attempt(sample_attempt_id)
        comparison = self._require_attempt(comparison_sample_attempt_id)
        if sample_attempt_id == comparison_sample_attempt_id:
            raise ConflictError("Pairwise judging requires two different sample attempts.")
        if _value(attempt, "sample_id") != _value(comparison, "sample_id"):
            raise ConflictError("Pairwise sample attempts must have the same sample id.")
        endpoint = self._require_endpoint(judge_endpoint_id)
        self._require_independent_judge(attempt, endpoint)
        self._require_independent_judge(comparison, endpoint)

        rubric_snapshot = rubric or {}
        first_order = ["target", "comparison"] if secrets.randbelow(2) == 0 else ["comparison", "target"]
        orders = [first_order, list(reversed(first_order))] if swap_test else [first_order]
        group_id = str(uuid4()) if swap_test else None
        assessments: list[Any] = []
        for order in orders:
            assessment = self._repository.create_assessment(
                _assessment_values(
                    sample_attempt_id=sample_attempt_id,
                    comparison_sample_attempt_id=comparison_sample_attempt_id,
                    judge_endpoint_id=judge_endpoint_id,
                    rubric=rubric_snapshot,
                    answer_order=order,
                    swap_test_group_id=group_id,
                )
            )
            answers = {
                "A": _value(attempt, "parsed_prediction")
                if order[0] == "target"
                else _value(comparison, "parsed_prediction"),
                "B": _value(comparison, "parsed_prediction")
                if order[1] == "comparison"
                else _value(attempt, "parsed_prediction"),
            }
            input_snapshot = build_pairwise_judge_input(
                system_message=DEFAULT_PAIRWISE_JUDGE_SYSTEM_MESSAGE,
                rubric=rubric_snapshot,
                input_snapshot=_value(attempt, "input_snapshot"),
                reference_snapshot=_value(attempt, "reference_snapshot"),
                answers=answers,
            )
            result = model_executor.execute(
                _execution_endpoint(endpoint, None),
                cipher.decrypt(str(_value(endpoint, "encrypted_api_key"))),
                input_snapshot,
            )
            assessments.append(
                self._finish_assessment(
                    str(_value(assessment, "id")),
                    _execution_endpoint(endpoint, None),
                    result,
                    pairwise=True,
                )
            )
        return assessments

    def list_for_sample(self, sample_attempt_id: str) -> list[Any]:
        return self._repository.list_assessments(sample_attempt_id)

    def agreement(self, sample_attempt_id: str) -> dict[str, object]:
        self._require_attempt(sample_attempt_id)
        return build_judge_agreement(self._repository.list_assessments(sample_attempt_id))

    def _require_attempt(self, sample_attempt_id: str) -> Any:
        attempt = self._repository.get_sample_attempt(sample_attempt_id)
        if attempt is None:
            raise NotFoundError("Sample attempt not found.", context={"sample_attempt_id": sample_attempt_id})
        return attempt

    def _require_endpoint(self, endpoint_id: str) -> Any:
        endpoint = self._repository.get_endpoint(endpoint_id)
        if endpoint is None:
            raise NotFoundError("Judge model endpoint not found.", context={"endpoint_id": endpoint_id})
        if _value(endpoint, "status") != "available":
            raise ConflictError("Judge model endpoint must pass a connection test.")
        return endpoint

    def _require_independent_judge(self, attempt: Any, endpoint: Any) -> None:
        run = self._repository.get_run(str(_value(attempt, "run_id")))
        if run is not None and _value(run, "model_endpoint_id") == _value(endpoint, "id"):
            raise ConflictError("A model endpoint cannot judge its own evaluation output.")

    def _finish_assessment(
        self,
        assessment_id: str,
        endpoint: Any,
        result: Any,
        *,
        pairwise: bool = False,
    ) -> Any:
        values: dict[str, Any] = {
            "raw_response": result.raw_response,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "estimated_cost": _estimated_cost(endpoint, result.input_tokens, result.output_tokens),
        }
        if not result.success or result.prediction is None:
            values.update({"status": "failed", "error_message": result.error_message or "Judge execution failed."})
        else:
            try:
                parsed = parse_judge_response(result.prediction)
                values.update(
                    {
                        "score": parsed["score"],
                        "label": parsed.get("label"),
                        "rationale": parsed.get("rationale"),
                        "status": "succeeded",
                        "error_message": None,
                    }
                )
                if pairwise:
                    values["selected_answer"] = parsed.get("winner")
            except JudgeScoringError as error:
                values.update({"status": "failed", "error_message": str(error)})
        updated = self._repository.update_assessment(assessment_id, values)
        if updated is None:
            raise NotFoundError("Judge assessment not found.", context={"assessment_id": assessment_id})
        return updated


def _assessment_values(
    *,
    sample_attempt_id: str,
    judge_endpoint_id: str,
    rubric: dict[str, Any],
    comparison_sample_attempt_id: str | None = None,
    answer_order: list[str] | None = None,
    swap_test_group_id: str | None = None,
) -> dict[str, Any]:
    return {
        "sample_attempt_id": sample_attempt_id,
        "comparison_sample_attempt_id": comparison_sample_attempt_id,
        "judge_endpoint_id": judge_endpoint_id,
        "rubric": rubric,
        "answer_order": answer_order or [],
        "swap_test_group_id": swap_test_group_id,
        "selected_answer": None,
        "score": None,
        "label": None,
        "rationale": None,
        "raw_response": None,
        "input_tokens": None,
        "output_tokens": None,
        "estimated_cost": None,
        "status": "running",
        "error_message": None,
        "created_at": datetime.now(timezone.utc),
    }


def _execution_endpoint(endpoint: Any, override: Mapping[str, object] | None) -> Any:
    values = {name: _value(endpoint, name) for name in _FROZEN_ENDPOINT_FIELDS}
    if override is not None:
        values.update({name: override[name] for name in _FROZEN_ENDPOINT_FIELDS if name in override})
    return SimpleNamespace(**values)


def _estimated_cost(endpoint: Any, input_tokens: int | None, output_tokens: int | None) -> float | None:
    if input_tokens is None and output_tokens is None:
        return None
    input_cost = (input_tokens or 0) * (float(_value(endpoint, "input_cost_per_million") or 0) / 1_000_000)
    output_cost = (output_tokens or 0) * (float(_value(endpoint, "output_cost_per_million") or 0) / 1_000_000)
    return round(input_cost + output_cost, 12)


def build_judge_agreement(assessments: list[Any]) -> dict[str, object]:
    """Make multi-judge disagreement explicit without merging judge evidence."""

    successful = [item for item in assessments if _value(item, "status") == "succeeded"]
    scores = [float(score) for item in successful if isinstance(score := _value(item, "score"), int | float)]
    decisions = [_normalized_pairwise_decision(item) for item in successful]
    decisions = [decision for decision in decisions if decision is not None]
    labels = [str(value) for item in successful if isinstance(value := _value(item, "label"), str) and value]
    decision_values = decisions or labels
    score_range = max(scores) - min(scores) if scores else None
    distinct_decisions = sorted(set(decision_values))
    if not assessments:
        agreement_status = "no_assessments"
    elif not successful:
        agreement_status = "no_successful_judgments"
    elif (score_range is not None and score_range > 0.1) or len(distinct_decisions) > 1:
        agreement_status = "disagreement"
    else:
        agreement_status = "agreement"
    return {
        "status": agreement_status,
        "assessment_count": len(assessments),
        "successful_assessment_count": len(successful),
        "judge_endpoint_count": len({_value(item, "judge_endpoint_id") for item in successful}),
        "scores": {
            "mean": round(sum(scores) / len(scores), 12) if scores else None,
            "range": round(score_range, 12) if score_range is not None else None,
        },
        "decisions": {"distinct": distinct_decisions, "count": len(decision_values)},
        "swap_test_group_count": len(
            {_value(item, "swap_test_group_id") for item in successful if _value(item, "swap_test_group_id")}
        ),
    }


def _value(item: Any, key: str, default: Any = None) -> Any:
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


def _normalized_pairwise_decision(assessment: Any) -> str | None:
    selected = _value(assessment, "selected_answer")
    order = _value(assessment, "answer_order")
    if not isinstance(selected, str) or selected not in {"A", "B", "tie"}:
        return None
    if selected == "tie":
        return selected
    if not isinstance(order, list) or len(order) != 2 or any(item not in {"target", "comparison"} for item in order):
        return selected
    return str(order[0] if selected == "A" else order[1])
