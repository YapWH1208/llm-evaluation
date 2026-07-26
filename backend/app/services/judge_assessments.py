from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.secrets import SecretCipher
from app.db.models import EndpointStatus, JudgeAssessment, ModelEndpoint, SampleAttempt
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
    return parsed
