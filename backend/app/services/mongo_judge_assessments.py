from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.core.secrets import SecretCipher
from app.db.mongo import MongoDocumentStore
from app.services.judge_assessments import JudgeAssessmentError, _parse_judge_response
from app.services.model_executor import ModelExecutor


def assess_mongo_sample_attempt(
    store: MongoDocumentStore,
    *,
    sample_attempt_id: str,
    judge_endpoint_id: str,
    rubric: dict[str, Any] | None,
    cipher: SecretCipher,
    model_executor: ModelExecutor,
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
            "status": "running",
            "error_message": None,
            "created_at": datetime.now(timezone.utc),
        },
    )
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
                        "rubric": assessment["rubric"],
                        "input": attempt["input_snapshot"],
                        "reference": attempt["reference_snapshot"],
                        "prediction": attempt.get("parsed_prediction"),
                    },
                    ensure_ascii=False,
                ),
            },
        ]
    }
    result = model_executor.execute(
        type("DocumentEndpoint", (), endpoint)(),
        cipher.decrypt(str(endpoint["encrypted_api_key"])),
        input_snapshot,
    )
    values: dict[str, Any] = {"raw_response": result.raw_response}
    if not result.success or result.prediction is None:
        values.update(
            {
                "status": "failed",
                "error_message": result.error_message or "Judge execution failed.",
            }
        )
    else:
        try:
            parsed = _parse_judge_response(result.prediction)
            values.update(
                {
                    "score": parsed["score"],
                    "label": parsed.get("label"),
                    "rationale": parsed.get("rationale"),
                    "status": "succeeded",
                    "error_message": None,
                }
            )
        except JudgeAssessmentError as error:
            values.update({"status": "failed", "error_message": str(error)})
    updated = store.update_document("judge_assessments", str(assessment["id"]), values)
    assert updated is not None
    return updated
