from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.secrets import SecretCipher
from app.db.mongo import MongoDocumentStore
from app.services.judge_assessments import JudgeAssessmentError, _parse_judge_response
from app.services.judge_scoring import (
    DEFAULT_PAIRWISE_JUDGE_SYSTEM_MESSAGE,
    DEFAULT_SINGLE_JUDGE_SYSTEM_MESSAGE,
    build_pairwise_judge_input,
    build_single_judge_input,
)
from app.services.model_executor import ModelExecutor


def assess_mongo_sample_attempt(
    store: MongoDocumentStore,
    *,
    sample_attempt_id: str,
    judge_endpoint_id: str,
    rubric: dict[str, Any] | None,
    system_message: str = DEFAULT_SINGLE_JUDGE_SYSTEM_MESSAGE,
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
    input_snapshot = build_single_judge_input(
        system_message=system_message,
        rubric=assessment["rubric"],
        input_snapshot=attempt["input_snapshot"],
        reference_snapshot=attempt["reference_snapshot"],
        prediction=attempt.get("parsed_prediction"),
    )
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
            type("DocumentEndpoint", (), endpoint)(),
            cipher.decrypt(str(endpoint["encrypted_api_key"])),
            input_snapshot,
        )
        values: dict[str, Any] = {"raw_response": result.raw_response}
        if not result.success or result.prediction is None:
            values.update({"status": "failed", "error_message": result.error_message or "Judge execution failed."})
        else:
            try:
                parsed = _parse_judge_response(result.prediction)
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
            except JudgeAssessmentError as error:
                values.update({"status": "failed", "error_message": str(error)})
        updated = store.update_document("judge_assessments", str(assessment["id"]), values)
        assert updated is not None
        assessments.append(updated)
    return assessments
