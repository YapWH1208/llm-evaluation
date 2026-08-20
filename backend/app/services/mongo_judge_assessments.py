from __future__ import annotations

import secrets
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.secrets import SecretCipher
from app.db.mongo import MongoDocumentStore
from app.services.judge_assessments import JudgeAssessmentError
from app.services.judge_scoring import (
    DEFAULT_PAIRWISE_JUDGE_SYSTEM_MESSAGE,
    DEFAULT_SINGLE_JUDGE_SYSTEM_MESSAGE,
    JudgeScoringError,
    build_pairwise_judge_input,
    build_single_judge_input,
    parse_judge_response,
)
from app.infrastructure.providers.contracts import ModelExecutor

_FROZEN_JUDGE_FIELDS = (
    "base_url",
    "model_name",
    "protocol_profile",
    "default_request_body",
    "timeout_seconds",
    "custom_headers",
    "input_cost_per_million",
    "output_cost_per_million",
)


def _merged_judge_endpoint(endpoint: dict[str, Any], override: Mapping[str, object] | None) -> dict[str, Any]:
    """Merge a frozen endpoint description over the live document for reproducible judging."""
    if override is None:
        return endpoint
    values = dict(endpoint)
    for name in _FROZEN_JUDGE_FIELDS:
        if name in override:
            values[name] = override[name]
    return values


def _proxy(document: dict[str, Any]) -> Any:
    return type("DocumentEndpoint", (), document)()


def _mongo_estimated_cost(endpoint: dict[str, Any], input_tokens: int | None, output_tokens: int | None) -> float | None:
    if input_tokens is None and output_tokens is None:
        return None
    input_cost = (input_tokens or 0) * (float(endpoint.get("input_cost_per_million") or 0) / 1_000_000)
    output_cost = (output_tokens or 0) * (float(endpoint.get("output_cost_per_million") or 0) / 1_000_000)
    return round(input_cost + output_cost, 12)


def assess_mongo_sample_attempt(
    store: MongoDocumentStore,
    *,
    sample_attempt_id: str,
    judge_endpoint_id: str,
    rubric: dict[str, Any] | None,
    system_message: str = DEFAULT_SINGLE_JUDGE_SYSTEM_MESSAGE,
    cipher: SecretCipher,
    model_executor: ModelExecutor,
    endpoint_override: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Run an LLM-as-judge assessment while retaining document evidence."""

    attempt = store.get_document("sample_attempts", sample_attempt_id)
    if attempt is None:
        raise JudgeAssessmentError("Sample attempt not found.")
    endpoint = store.get_document("model_endpoints", judge_endpoint_id)
    if endpoint is None:
        raise JudgeAssessmentError("Judge model endpoint not found.")
    if endpoint.get("status") != "available":
        raise JudgeAssessmentError("Judge model endpoint must pass a connection test.")
    run = store.get_document("evaluation_runs", str(attempt["run_id"]))
    if run is not None and run.get("model_endpoint_id") == judge_endpoint_id:
        raise JudgeAssessmentError("A model endpoint cannot judge its own evaluation output.")

    assessment = store.insert_document(
        "judge_assessments",
        {
            "sample_attempt_id": sample_attempt_id,
            "judge_endpoint_id": judge_endpoint_id,
            "rubric": rubric or {},
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
        },
    )
    input_snapshot = build_single_judge_input(
        system_message=system_message,
        rubric=assessment["rubric"],
        input_snapshot=attempt["input_snapshot"],
        reference_snapshot=attempt["reference_snapshot"],
        prediction=attempt.get("parsed_prediction"),
    )
    execution_endpoint = _merged_judge_endpoint(endpoint, endpoint_override)
    result = model_executor.execute(
        _proxy(execution_endpoint),
        cipher.decrypt(str(endpoint["encrypted_api_key"])),
        input_snapshot,
    )
    values: dict[str, Any] = {
        "raw_response": result.raw_response,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "estimated_cost": _mongo_estimated_cost(execution_endpoint, result.input_tokens, result.output_tokens),
    }
    if not result.success or result.prediction is None:
        values.update(
            {
                "status": "failed",
                "error_message": result.error_message or "Judge execution failed.",
            }
        )
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
        except JudgeScoringError as error:
            values.update({"status": "failed", "error_message": str(error)})
    updated = store.update_document("judge_assessments", str(assessment["id"]), values)
    assert updated is not None
    return updated


def assess_mongo_pairwise_sample_attempt(
    store: MongoDocumentStore,
    *,
    sample_attempt_id: str,
    comparison_sample_attempt_id: str,
    judge_endpoint_id: str,
    rubric: dict[str, Any] | None,
    swap_test: bool,
    cipher: SecretCipher,
    model_executor: ModelExecutor,
) -> list[dict[str, Any]]:
    """Run one or two blinded pairwise assessments in document-store mode."""

    attempt = store.get_document("sample_attempts", sample_attempt_id)
    comparison = store.get_document("sample_attempts", comparison_sample_attempt_id)
    if attempt is None or comparison is None:
        raise JudgeAssessmentError("Sample attempt not found.")
    if sample_attempt_id == comparison_sample_attempt_id:
        raise JudgeAssessmentError("Pairwise judging requires two different sample attempts.")
    if attempt.get("sample_id") != comparison.get("sample_id"):
        raise JudgeAssessmentError("Pairwise sample attempts must have the same sample id.")
    endpoint = store.get_document("model_endpoints", judge_endpoint_id)
    if endpoint is None:
        raise JudgeAssessmentError("Judge model endpoint not found.")
    if endpoint.get("status") != "available":
        raise JudgeAssessmentError("Judge model endpoint must pass a connection test.")
    for candidate in (attempt, comparison):
        run = store.get_document("evaluation_runs", str(candidate["run_id"]))
        if run is not None and run.get("model_endpoint_id") == judge_endpoint_id:
            raise JudgeAssessmentError("A model endpoint cannot judge its own evaluation output.")

    rubric_snapshot = rubric or {}
    first_order = ["target", "comparison"] if secrets.randbelow(2) == 0 else ["comparison", "target"]
    orders = [first_order, list(reversed(first_order))] if swap_test else [first_order]
    group_id = str(uuid4()) if swap_test else None
    assessments: list[dict[str, Any]] = []
    for order in orders:
        assessment = store.insert_document(
            "judge_assessments",
            {
                "sample_attempt_id": sample_attempt_id,
                "comparison_sample_attempt_id": comparison_sample_attempt_id,
                "judge_endpoint_id": judge_endpoint_id,
            "rubric": rubric_snapshot,
            "answer_order": order,
            "swap_test_group_id": group_id,
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
        },
    )
        answers = {
            "A": attempt.get("parsed_prediction") if order[0] == "target" else comparison.get("parsed_prediction"),
            "B": comparison.get("parsed_prediction") if order[1] == "comparison" else attempt.get("parsed_prediction"),
        }
        input_snapshot = build_pairwise_judge_input(
            system_message=DEFAULT_PAIRWISE_JUDGE_SYSTEM_MESSAGE,
            rubric=rubric_snapshot,
            input_snapshot=attempt["input_snapshot"],
            reference_snapshot=attempt["reference_snapshot"],
            answers=answers,
        )
        result = model_executor.execute(
            _proxy(endpoint),
            cipher.decrypt(str(endpoint["encrypted_api_key"])),
            input_snapshot,
        )
        values: dict[str, Any] = {
            "raw_response": result.raw_response,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "estimated_cost": _mongo_estimated_cost(endpoint, result.input_tokens, result.output_tokens),
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
                        "selected_answer": parsed.get("winner"),
                        "status": "succeeded",
                        "error_message": None,
                    }
                )
            except JudgeScoringError as error:
                values.update({"status": "failed", "error_message": str(error)})
        updated = store.update_document("judge_assessments", str(assessment["id"]), values)
        assert updated is not None
        assessments.append(updated)
    return assessments
