from __future__ import annotations

import json
import secrets
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.secrets import SecretCipher
from app.db.models import EndpointStatus, EvaluationRun, JudgeAssessment, ModelEndpoint, SampleAttempt
from app.services.model_executor import ModelExecutor


class JudgeAssessmentError(ValueError):
    pass


def assess_sample_attempt(
    session: Session,
    *,
    sample_attempt_id: str,
    judge_endpoint_id: str,
    rubric: dict[str, Any] | None,
    cipher: SecretCipher,
    model_executor: ModelExecutor,
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
    session.commit()
    session.refresh(assessment)

    input_snapshot = {
        "messages": [
            {
                "role": "system",
                "content": "You are an evaluation judge. Return only JSON with score (0 to 1), label, and rationale.",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "rubric": assessment.rubric,
                        "input": attempt.input_snapshot,
                        "reference": attempt.reference_snapshot,
                        "prediction": attempt.parsed_prediction,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
    }
    result = model_executor.execute(endpoint, cipher.decrypt(endpoint.encrypted_api_key), input_snapshot)
    assessment.raw_response = result.raw_response
    if not result.success or result.prediction is None:
        assessment.status = "failed"
        assessment.error_message = result.error_message or "Judge execution failed."
        session.commit()
        session.refresh(assessment)
        return assessment

    try:
        parsed = _parse_judge_response(result.prediction)
        assessment.score = parsed["score"]
        assessment.label = parsed.get("label")
        assessment.rationale = parsed.get("rationale")
        assessment.status = "succeeded"
        assessment.error_message = None
    except JudgeAssessmentError as error:
        assessment.status = "failed"
        assessment.error_message = str(error)
    session.commit()
    session.refresh(assessment)
    return assessment


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
        input_snapshot = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an evaluation judge. Compare two anonymized candidate answers. Return only JSON with score (0 to 1), label, rationale, and winner (A, B, or tie). Do not infer model identity.",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "rubric": rubric_snapshot,
                            "input": attempt.input_snapshot,
                            "reference": attempt.reference_snapshot,
                            "answers": answers,
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
        }
        result = model_executor.execute(endpoint, cipher.decrypt(endpoint.encrypted_api_key), input_snapshot)
        assessment.raw_response = result.raw_response
        if not result.success or result.prediction is None:
            assessment.status = "failed"
            assessment.error_message = result.error_message or "Judge execution failed."
        else:
            try:
                parsed = _parse_judge_response(result.prediction)
                assessment.score = parsed["score"]
                assessment.label = parsed.get("label")
                assessment.rationale = parsed.get("rationale")
                assessment.selected_answer = parsed.get("winner")
                assessment.status = "succeeded"
                assessment.error_message = None
            except JudgeAssessmentError as error:
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


def _parse_judge_response(prediction: str) -> dict[str, object]:
    text = prediction.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3].strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise JudgeAssessmentError("Judge response was not valid JSON.") from error
    if not isinstance(payload, dict):
        raise JudgeAssessmentError("Judge response must be a JSON object.")
    try:
        score = float(payload["score"])
    except (KeyError, TypeError, ValueError) as error:
        raise JudgeAssessmentError("Judge response must include a numeric score.") from error
    if not 0 <= score <= 1:
        raise JudgeAssessmentError("Judge score must be between 0 and 1.")
    parsed: dict[str, object] = {"score": score}
    for field in ("label", "rationale"):
        value = payload.get(field)
        if value is not None and not isinstance(value, str):
            raise JudgeAssessmentError(f"Judge response field {field} must be a string.")
        if isinstance(value, str):
            parsed[field] = value
    winner = payload.get("winner")
    if winner is not None:
        if not isinstance(winner, str) or winner not in {"A", "B", "tie"}:
            raise JudgeAssessmentError("Judge response winner must be A, B, or tie.")
        parsed["winner"] = winner
    return parsed
