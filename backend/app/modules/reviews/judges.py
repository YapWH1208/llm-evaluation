from __future__ import annotations

import secrets
from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.secrets import SecretCipher
from app.db.models import EndpointStatus, EvaluationRun, JudgeAssessment, ModelEndpoint, SampleAttempt
from app.infrastructure.providers.contracts import ModelExecutor
from app.modules.reviews.scoring import (
    DEFAULT_PAIRWISE_JUDGE_SYSTEM_MESSAGE,
    DEFAULT_SINGLE_JUDGE_SYSTEM_MESSAGE,
    JudgeScoringError,
    build_pairwise_judge_input,
    build_single_judge_input,
    parse_judge_response,
)


class JudgeAssessmentError(ValueError):
    pass


def _execution_endpoint(endpoint: ModelEndpoint, override: Mapping[str, object] | None) -> Any:
    """Merge a frozen endpoint description over the live row for reproducible judging."""
    if override is None:
        return endpoint
    return SimpleNamespace(
        base_url=str(override.get("base_url", endpoint.base_url)),
        model_name=str(override.get("model_name", endpoint.model_name)),
        protocol_profile=str(override.get("protocol_profile", endpoint.protocol_profile)),
        default_request_body=override.get("default_request_body", endpoint.default_request_body),
        timeout_seconds=int(override.get("timeout_seconds", endpoint.timeout_seconds)),
        custom_headers=override.get("custom_headers", endpoint.custom_headers),
        input_cost_per_million=override.get("input_cost_per_million", endpoint.input_cost_per_million),
        output_cost_per_million=override.get("output_cost_per_million", endpoint.output_cost_per_million),
    )


def _estimated_cost(endpoint: Any, input_tokens: int | None, output_tokens: int | None) -> float | None:
    if input_tokens is None and output_tokens is None:
        return None
    input_cost = (input_tokens or 0) * (endpoint.input_cost_per_million or 0) / 1_000_000
    output_cost = (output_tokens or 0) * (endpoint.output_cost_per_million or 0) / 1_000_000
    return round(input_cost + output_cost, 12)


def assess_sample_attempt(
    session: Session,
    *,
    sample_attempt_id: str,
    judge_endpoint_id: str,
    rubric: dict[str, Any] | None,
    system_message: str = DEFAULT_SINGLE_JUDGE_SYSTEM_MESSAGE,
    persist: bool = True,
    cipher: SecretCipher,
    model_executor: ModelExecutor,
    endpoint_override: Mapping[str, object] | None = None,
) -> JudgeAssessment:
    attempt = session.get(SampleAttempt, sample_attempt_id)
    if attempt is None:
        raise JudgeAssessmentError("Sample attempt not found.")
    endpoint = session.get(ModelEndpoint, judge_endpoint_id)
    if endpoint is None:
        raise JudgeAssessmentError("Judge model endpoint not found.")
    if endpoint.status != EndpointStatus.AVAILABLE.value:
        raise JudgeAssessmentError("Judge model endpoint must pass a connection test.")
    run = session.get(EvaluationRun, attempt.run_id)
    if run is not None and run.model_endpoint_id == endpoint.id:
        raise JudgeAssessmentError("A model endpoint cannot judge its own evaluation output.")

    assessment = JudgeAssessment(
        sample_attempt_id=attempt.id,
        judge_endpoint_id=endpoint.id,
        rubric=rubric or {},
        status="running",
    )
    session.add(assessment)
    session.flush()
    if persist:
        session.commit()
        session.refresh(assessment)

    input_snapshot = build_single_judge_input(
        system_message=system_message,
        rubric=assessment.rubric,
        input_snapshot=attempt.input_snapshot,
        reference_snapshot=attempt.reference_snapshot,
        prediction=attempt.parsed_prediction,
    )
    execution_endpoint = _execution_endpoint(endpoint, endpoint_override)
    result = model_executor.execute(execution_endpoint, cipher.decrypt(endpoint.encrypted_api_key), input_snapshot)
    assessment.raw_response = result.raw_response
    assessment.input_tokens = result.input_tokens
    assessment.output_tokens = result.output_tokens
    assessment.estimated_cost = _estimated_cost(execution_endpoint, result.input_tokens, result.output_tokens)
    if not result.success or result.prediction is None:
        assessment.status = "failed"
        assessment.error_message = result.error_message or "Judge execution failed."
        _save_assessment(session, assessment, persist=persist)
        return assessment

    try:
        parsed = parse_judge_response(result.prediction)
        assessment.score = parsed["score"]
        assessment.label = parsed.get("label")
        assessment.rationale = parsed.get("rationale")
        assessment.status = "succeeded"
        assessment.error_message = None
    except JudgeScoringError as error:
        assessment.status = "failed"
        assessment.error_message = str(error)
    _save_assessment(session, assessment, persist=persist)
    return assessment


def _save_assessment(session: Session, assessment: JudgeAssessment, *, persist: bool) -> None:
    session.flush()
    if persist:
        session.commit()
        session.refresh(assessment)


def assess_pairwise_sample_attempt(
    session: Session,
    *,
    sample_attempt_id: str,
    comparison_sample_attempt_id: str,
    judge_endpoint_id: str,
    rubric: dict[str, Any] | None,
    swap_test: bool,
    cipher: SecretCipher,
    model_executor: ModelExecutor,
) -> list[JudgeAssessment]:
    """Judge two matching sample attempts without revealing either model identity."""

    attempt = session.get(SampleAttempt, sample_attempt_id)
    comparison = session.get(SampleAttempt, comparison_sample_attempt_id)
    if attempt is None or comparison is None:
        raise JudgeAssessmentError("Sample attempt not found.")
    if attempt.id == comparison.id:
        raise JudgeAssessmentError("Pairwise judging requires two different sample attempts.")
    if attempt.sample_id != comparison.sample_id:
        raise JudgeAssessmentError("Pairwise sample attempts must have the same sample id.")
    endpoint = session.get(ModelEndpoint, judge_endpoint_id)
    if endpoint is None:
        raise JudgeAssessmentError("Judge model endpoint not found.")
    if endpoint.status != EndpointStatus.AVAILABLE.value:
        raise JudgeAssessmentError("Judge model endpoint must pass a connection test.")
    for candidate in (attempt, comparison):
        run = session.get(EvaluationRun, candidate.run_id)
        if run is not None and run.model_endpoint_id == endpoint.id:
            raise JudgeAssessmentError("A model endpoint cannot judge its own evaluation output.")

    rubric_snapshot = rubric or {}
    first_order = ["target", "comparison"] if secrets.randbelow(2) == 0 else ["comparison", "target"]
    orders = [first_order, list(reversed(first_order))] if swap_test else [first_order]
    group_id = str(uuid4()) if swap_test else None
    assessments: list[JudgeAssessment] = []
    for order in orders:
        assessment = JudgeAssessment(
            sample_attempt_id=attempt.id,
            comparison_sample_attempt_id=comparison.id,
            judge_endpoint_id=endpoint.id,
            rubric=rubric_snapshot,
            answer_order=order,
            swap_test_group_id=group_id,
            status="running",
        )
        session.add(assessment)
        session.commit()
        session.refresh(assessment)
        answers = {
            "A": attempt.parsed_prediction if order[0] == "target" else comparison.parsed_prediction,
            "B": comparison.parsed_prediction if order[1] == "comparison" else attempt.parsed_prediction,
        }
        input_snapshot = build_pairwise_judge_input(
            system_message=DEFAULT_PAIRWISE_JUDGE_SYSTEM_MESSAGE,
            rubric=rubric_snapshot,
            input_snapshot=attempt.input_snapshot,
            reference_snapshot=attempt.reference_snapshot,
            answers=answers,
        )
        result = model_executor.execute(endpoint, cipher.decrypt(endpoint.encrypted_api_key), input_snapshot)
        assessment.raw_response = result.raw_response
        assessment.input_tokens = result.input_tokens
        assessment.output_tokens = result.output_tokens
        assessment.estimated_cost = _estimated_cost(endpoint, result.input_tokens, result.output_tokens)
        if not result.success or result.prediction is None:
            assessment.status = "failed"
            assessment.error_message = result.error_message or "Judge execution failed."
        else:
            try:
                parsed = parse_judge_response(result.prediction)
                assessment.score = parsed["score"]
                assessment.label = parsed.get("label")
                assessment.rationale = parsed.get("rationale")
                assessment.selected_answer = parsed.get("winner")
                assessment.status = "succeeded"
                assessment.error_message = None
            except JudgeScoringError as error:
                assessment.status = "failed"
                assessment.error_message = str(error)
        session.commit()
        session.refresh(assessment)
        assessments.append(assessment)
    return assessments


def build_judge_agreement(assessments: list[JudgeAssessment | dict[str, Any]]) -> dict[str, object]:
    """Make multi-judge disagreement explicit without merging judge evidence."""

    successful = [item for item in assessments if _assessment_value(item, "status") == "succeeded"]
    scores = [float(score) for item in successful if isinstance(score := _assessment_value(item, "score"), (int, float))]
    decisions = [_normalized_pairwise_decision(item) for item in successful if _normalized_pairwise_decision(item) is not None]
    labels = [str(value) for item in successful if isinstance(value := _assessment_value(item, "label"), str) and value]
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
        "judge_endpoint_count": len({_assessment_value(item, "judge_endpoint_id") for item in successful}),
        "scores": {
            "mean": round(sum(scores) / len(scores), 12) if scores else None,
            "range": round(score_range, 12) if score_range is not None else None,
        },
        "decisions": {"distinct": distinct_decisions, "count": len(decision_values)},
        "swap_test_group_count": len({_assessment_value(item, "swap_test_group_id") for item in successful if _assessment_value(item, "swap_test_group_id")}),
    }


def _assessment_value(assessment: JudgeAssessment | dict[str, Any], key: str) -> object:
    return assessment.get(key) if isinstance(assessment, dict) else getattr(assessment, key)


def _normalized_pairwise_decision(assessment: JudgeAssessment | dict[str, Any]) -> str | None:
    selected = _assessment_value(assessment, "selected_answer")
    order = _assessment_value(assessment, "answer_order")
    if not isinstance(selected, str) or selected not in {"A", "B", "tie"}:
        return None
    if selected == "tie":
        return selected
    if not isinstance(order, list) or len(order) != 2 or any(item not in {"target", "comparison"} for item in order):
        return selected
    return str(order[0] if selected == "A" else order[1])
