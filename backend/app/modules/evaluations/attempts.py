from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.errors import ConflictError
from app.core.secrets import SecretCipher
from app.db.models import SampleAttemptStatus
from app.infrastructure.providers.contracts import ModelExecutor, SampleExecutionResult
from app.modules.benchmarks.metrics import build_execution_metric_evidence
from app.modules.benchmarks.scoring import ScoringError, score_prediction
from app.modules.evaluations.ports import ExecutionRepository
from app.modules.reviews.judges import JudgeAssessmentError
from app.modules.reviews.scoring import is_llm_judge_rule, judge_assessment_evidence, judge_failure_evidence


class AttemptProcessor:
    """Create retry attempts and persist per-sample execution/scoring evidence."""

    def __init__(self, repository: ExecutionRepository) -> None:
        self._repository = repository

    def prepare(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        payload = task_payload(task)
        sample_ids = [
            value
            for value in payload.get("retry_sample_ids") or payload.get("sample_ids") or []
            if isinstance(value, str)
        ]
        attempts = [
            attempt
            for attempt in self._repository.list_attempts(str(task["run_id"]))
            if str(attempt["task_id"]) == str(task["id"])
        ]
        latest = latest_attempts(attempts)
        if int(task.get("attempt_count", 0)) > 1:
            for sample_id in sample_ids:
                previous = latest.get(sample_id)
                if previous is None or previous.get("status") not in {
                    SampleAttemptStatus.FAILED.value,
                    SampleAttemptStatus.RETRY_SCHEDULED.value,
                }:
                    continue
                self._repository.create_attempt(
                    {
                        "run_id": previous["run_id"],
                        "task_id": previous["task_id"],
                        "sample_id": previous["sample_id"],
                        "attempt_number": int(previous["attempt_number"]) + 1,
                        "input_snapshot": previous["input_snapshot"],
                        "reference_snapshot": previous["reference_snapshot"],
                        "request_snapshot": None,
                        "raw_response": None,
                        "parsed_prediction": None,
                        "metric_evidence": None,
                        "score": None,
                        "latency_ms": None,
                        "input_tokens": None,
                        "output_tokens": None,
                        "estimated_cost": None,
                        "error_type": None,
                        "error_message": None,
                        "status": SampleAttemptStatus.PENDING.value,
                        "created_at": utc_now(),
                        "started_at": None,
                        "completed_at": None,
                    }
                )
            attempts = [
                attempt
                for attempt in self._repository.list_attempts(str(task["run_id"]))
                if str(attempt["task_id"]) == str(task["id"])
            ]
            latest = latest_attempts(attempts)
        return [
            latest[sample_id]
            for sample_id in sample_ids
            if sample_id in latest and latest[sample_id].get("status") == SampleAttemptStatus.PENDING.value
        ]

    def record_result(
        self,
        run: dict[str, Any],
        attempt: dict[str, Any],
        result: SampleExecutionResult,
        endpoint: dict[str, Any],
        lease_token: str,
        *,
        cipher: SecretCipher,
        model_executor: ModelExecutor,
    ) -> dict[str, Any]:
        values: dict[str, Any] = {
            "request_snapshot": result.request_snapshot,
            "raw_response": result.raw_response,
            "parsed_prediction": result.prediction,
            "latency_ms": result.latency_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "estimated_cost": estimate_cost(endpoint, result.input_tokens, result.output_tokens),
            "metric_evidence": build_execution_metric_evidence(
                token_logprobs=result.token_logprobs,
                existing=(attempt.get("metric_evidence") if isinstance(attempt.get("metric_evidence"), dict) else None),
            ),
            "completed_at": utc_now(),
        }
        if result.success and result.prediction is not None:
            reference = attempt.get("reference_snapshot")
            scoring = reference.get("scoring") if isinstance(reference, dict) else None
            if is_llm_judge_rule(scoring):
                checkpoint = self._repository.update_attempt(
                    str(attempt["id"]),
                    {**values, "score": None, "error_type": None, "error_message": None},
                )
                if checkpoint is None:
                    raise ConflictError("Task lease was lost before result persistence.")
                evidence = self._automatic_judge(
                    run,
                    checkpoint,
                    cipher=cipher,
                    model_executor=model_executor,
                )
                self._require_lease(str(attempt["task_id"]), lease_token)
                stored = self._repository.complete_attempt(
                    str(attempt["id"]),
                    lease_token,
                    {
                        "metric_evidence": {**values["metric_evidence"], "llm_judge": evidence},
                        "status": SampleAttemptStatus.SUCCEEDED.value,
                    },
                )
                if stored is None:
                    raise ConflictError("Task lease was lost before judge evidence persistence.")
                return stored
            try:
                values.update(
                    {
                        "score": score_prediction(result.prediction, dict(reference or {})),
                        "status": SampleAttemptStatus.SUCCEEDED.value,
                        "error_type": None,
                        "error_message": None,
                    }
                )
            except ScoringError as error:
                values.update(
                    {
                        "score": None,
                        "status": SampleAttemptStatus.FAILED.value,
                        "error_type": "scoring_error",
                        "error_message": str(error),
                    }
                )
        else:
            values.update(
                {
                    "score": None,
                    "status": SampleAttemptStatus.FAILED.value,
                    "error_type": result.error_type or "execution_error",
                    "error_message": result.error_message or "Sample execution failed.",
                }
            )
        stored = self._repository.complete_attempt(str(attempt["id"]), lease_token, values)
        if stored is None:
            raise ConflictError("Task lease was lost before result persistence.")
        return stored

    def _automatic_judge(
        self,
        run: dict[str, Any],
        attempt: dict[str, Any],
        *,
        cipher: SecretCipher,
        model_executor: ModelExecutor,
    ) -> dict[str, object]:
        configuration = run.get("configuration_snapshot")
        configuration = configuration if isinstance(configuration, dict) else {}
        judge = configuration.get("judge") if isinstance(configuration.get("judge"), dict) else {}
        endpoint = judge.get("endpoint") if isinstance(judge.get("endpoint"), dict) else {}
        endpoint_id = endpoint.get("id")
        system_message = judge.get("system_message")
        if not isinstance(endpoint_id, str) or not endpoint_id:
            return judge_failure_evidence("Frozen judge endpoint configuration is missing.")
        if not isinstance(system_message, str) or not system_message:
            return judge_failure_evidence("Frozen judge system message is missing.")
        try:
            assessment = self._repository.assess_judge(
                sample_attempt_id=str(attempt["id"]),
                judge_endpoint_id=endpoint_id,
                rubric={"source": "llm_judge_metric", "reference_field": judge.get("reference_field")},
                system_message=system_message,
                cipher=cipher,
                model_executor=model_executor,
                endpoint_override=endpoint,
            )
        except JudgeAssessmentError as error:
            return judge_failure_evidence(str(error))
        return judge_assessment_evidence(assessment)

    def _require_lease(self, task_id: str, lease_token: str) -> None:
        if self._repository.update_task_for_lease(task_id, lease_token) is None:
            raise ConflictError("Task lease was lost before result persistence.")


def latest_attempts(attempts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        sample_id = str(attempt["sample_id"])
        previous = latest.get(sample_id)
        if previous is None or int(attempt.get("attempt_number", 1)) > int(previous.get("attempt_number", 1)):
            latest[sample_id] = attempt
    return latest


def task_payload(task: dict[str, Any]) -> dict[str, Any]:
    payload = task.get("payload")
    return dict(payload) if isinstance(payload, dict) else {}


def estimate_cost(endpoint: dict[str, Any], input_tokens: int | None, output_tokens: int | None) -> float | None:
    if input_tokens is None and output_tokens is None:
        return None
    input_cost = (input_tokens or 0) * (float(endpoint.get("input_cost_per_million") or 0) / 1_000_000)
    output_cost = (output_tokens or 0) * (float(endpoint.get("output_cost_per_million") or 0) / 1_000_000)
    return round(input_cost + output_cost, 12)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
