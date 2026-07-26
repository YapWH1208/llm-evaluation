from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.secrets import SecretCipher
from app.db import (
    EvaluationRun,
    ModelEndpoint,
    RunStatus,
    SampleAttempt,
    SampleAttemptStatus,
    TaskStatus,
    TaskUnit,
)
from app.services.model_executor import ModelExecutor, SampleExecutionResult
from app.services.scoring import ScoringError, score_prediction
from app.services.task_queue import claim_task, clear_lease, has_valid_lease


class RunExecutionError(ValueError):
    """Raised when an evaluation task cannot safely be executed."""


DEFAULT_RETRY_POLICY = {
    "max_attempts": 3,
    "base_delay_seconds": 2,
    "max_delay_seconds": 60,
    "strategy": "exponential_jitter",
    "jitter_ratio": 0.2,
    "max_total_wait_seconds": 600,
    "respect_retry_after": True,
    "retry_response_parse_errors": True,
}


def execute_queued_text_run(
    session: Session,
    *,
    run_id: str,
    cipher: SecretCipher,
    model_executor: ModelExecutor,
) -> EvaluationRun:
    """Compatibility endpoint for a local interactive worker execution."""

    run = session.get(EvaluationRun, run_id)
    if run is None:
        raise RunExecutionError("Evaluation run not found.")
    if run.status != RunStatus.QUEUED.value:
        raise RunExecutionError("Only queued evaluation runs can be executed.")
    task = claim_task(session, "interactive-api", lease_seconds=600, run_id=run_id)
    if task is None or task.lease_token is None:
        raise RunExecutionError("No due task is available for this evaluation run.")
    run, _ = execute_leased_text_task(
        session,
        task_id=task.id,
        lease_token=task.lease_token,
        cipher=cipher,
        model_executor=model_executor,
    )
    return run


def execute_leased_text_task(
    session: Session,
    *,
    task_id: str,
    lease_token: str,
    cipher: SecretCipher,
    model_executor: ModelExecutor,
) -> tuple[EvaluationRun, TaskUnit]:
    """Execute one leased task and either finish it or schedule a bounded retry."""

    task = session.get(TaskUnit, task_id)
    if task is None:
        raise RunExecutionError("Task not found.")
    if not has_valid_lease(task, lease_token):
        raise RunExecutionError("Task lease is no longer valid.")
    if task.task_type != "evaluation_shard":
        raise RunExecutionError("Unsupported task type.")

    run = session.get(EvaluationRun, task.run_id)
    if run is None:
        raise RunExecutionError("Evaluation run not found.")
    if run.status not in {RunStatus.QUEUED.value, RunStatus.RUNNING.value}:
        task.status = TaskStatus.CANCELLED.value
        clear_lease(task)
        session.commit()
        raise RunExecutionError("Evaluation run is not executable in its current state.")
    endpoint = session.get(ModelEndpoint, run.model_endpoint_id)
    if endpoint is None:
        raise RunExecutionError("The model endpoint for this run no longer exists.")

    run.status = RunStatus.RUNNING.value
    run.started_at = run.started_at or datetime.now(timezone.utc)
    task.status = TaskStatus.RUNNING.value
    task.attempt_count += 1
    session.commit()

    attempts = _prepare_attempts_for_execution(session, task)
    api_key = cipher.decrypt(endpoint.encrypted_api_key)
    retry_sample_ids: list[str] = []
    provider_retry_after_seconds: float | None = None
    policy = _retry_policy(task.payload)
    for attempt in attempts:
        _mark_attempt_running(session, attempt)
        result = model_executor.execute(endpoint, api_key, attempt.input_snapshot)
        _record_result(attempt, result, endpoint)
        if not result.success and _is_retryable(result.error_type, policy):
            retry_sample_ids.append(attempt.sample_id)
            if result.retry_after_seconds is not None:
                provider_retry_after_seconds = max(
                    provider_retry_after_seconds or 0.0,
                    result.retry_after_seconds,
                )
        session.commit()

    retry_sample_ids = sorted(set(retry_sample_ids))
    if (
        retry_sample_ids
        and task.attempt_count < policy["max_attempts"]
        and _schedule_retry(
            session,
            run,
            task,
            retry_sample_ids,
            policy,
            provider_retry_after_seconds=provider_retry_after_seconds,
        )
    ):
        pass
    else:
        _finalize_task_and_run(session, run, task)
    session.refresh(run)
    session.refresh(task)
    return run, task


def _prepare_attempts_for_execution(session: Session, task: TaskUnit) -> list[SampleAttempt]:
    payload = task.payload if isinstance(task.payload, dict) else {}
    requested_ids = payload.get("retry_sample_ids") or payload.get("sample_ids") or []
    sample_ids = [sample_id for sample_id in requested_ids if isinstance(sample_id, str)]
    latest = _latest_attempts_for_task(session, task.id)
    if task.attempt_count > 1:
        for sample_id in sample_ids:
            previous = latest.get(sample_id)
            if previous is None or previous.status != SampleAttemptStatus.FAILED.value:
                continue
            replacement = SampleAttempt(
                run_id=previous.run_id,
                task_id=previous.task_id,
                sample_id=previous.sample_id,
                attempt_number=previous.attempt_number + 1,
                input_snapshot=previous.input_snapshot,
                reference_snapshot=previous.reference_snapshot,
                status=SampleAttemptStatus.PENDING.value,
            )
            session.add(replacement)
        session.commit()

    latest = _latest_attempts_for_task(session, task.id)
    return [
        latest[sample_id]
        for sample_id in sample_ids
        if sample_id in latest and latest[sample_id].status == SampleAttemptStatus.PENDING.value
    ]


def _latest_attempts_for_task(session: Session, task_id: str) -> dict[str, SampleAttempt]:
    attempts = list(
        session.scalars(
            select(SampleAttempt)
            .where(SampleAttempt.task_id == task_id)
            .order_by(SampleAttempt.sample_id, SampleAttempt.attempt_number.desc())
        )
    )
    latest: dict[str, SampleAttempt] = {}
    for attempt in attempts:
        latest.setdefault(attempt.sample_id, attempt)
    return latest


def _mark_attempt_running(session: Session, attempt: SampleAttempt) -> None:
    attempt.status = SampleAttemptStatus.RUNNING.value
    attempt.started_at = datetime.now(timezone.utc)
    attempt.completed_at = None
    session.commit()


def _record_result(attempt: SampleAttempt, result: SampleExecutionResult, endpoint: ModelEndpoint) -> None:
    attempt.request_snapshot = result.request_snapshot
    attempt.raw_response = result.raw_response
    attempt.parsed_prediction = result.prediction
    attempt.latency_ms = result.latency_ms
    attempt.input_tokens = result.input_tokens
    attempt.output_tokens = result.output_tokens
    attempt.estimated_cost = _estimate_cost(endpoint, result.input_tokens, result.output_tokens)
    attempt.completed_at = datetime.now(timezone.utc)
    if result.success and result.prediction is not None:
        try:
            attempt.score = score_prediction(result.prediction, attempt.reference_snapshot)
            attempt.status = SampleAttemptStatus.SUCCEEDED.value
            attempt.error_type = None
            attempt.error_message = None
        except ScoringError as error:
            attempt.score = None
            attempt.status = SampleAttemptStatus.FAILED.value
            attempt.error_type = "scoring_error"
            attempt.error_message = str(error)
        return
    attempt.status = SampleAttemptStatus.FAILED.value
    attempt.score = None
    attempt.error_type = result.error_type or "execution_error"
    attempt.error_message = result.error_message or "Sample execution failed."


def _estimate_cost(
    endpoint: ModelEndpoint,
    input_tokens: int | None,
    output_tokens: int | None,
) -> float | None:
    if input_tokens is None and output_tokens is None:
        return None
    input_cost = (input_tokens or 0) * (endpoint.input_cost_per_million or 0) / 1_000_000
    output_cost = (output_tokens or 0) * (endpoint.output_cost_per_million or 0) / 1_000_000
    return round(input_cost + output_cost, 12)


def _is_retryable(error_type: str | None, policy: dict[str, Any]) -> bool:
    if error_type in {"timeout", "connection_error"}:
        return True
    if error_type == "response_parse_error":
        return bool(policy["retry_response_parse_errors"])
    if not error_type or not error_type.startswith("http_"):
        return False
    try:
        status_code = int(error_type.removeprefix("http_"))
    except ValueError:
        return False
    return status_code in {408, 409, 425, 429} or 500 <= status_code <= 599


def _retry_policy(payload: dict[str, Any]) -> dict[str, Any]:
    configured = payload.get("retry_policy") if isinstance(payload, dict) else None
    configured = configured if isinstance(configured, dict) else {}
    strategy = configured.get("strategy", DEFAULT_RETRY_POLICY["strategy"])
    if strategy not in {"fixed", "exponential", "exponential_jitter"}:
        strategy = DEFAULT_RETRY_POLICY["strategy"]
    return {
        "max_attempts": max(1, int(configured.get("max_attempts", DEFAULT_RETRY_POLICY["max_attempts"]))),
        "base_delay_seconds": max(0, int(configured.get("base_delay_seconds", DEFAULT_RETRY_POLICY["base_delay_seconds"]))),
        "max_delay_seconds": max(0, int(configured.get("max_delay_seconds", DEFAULT_RETRY_POLICY["max_delay_seconds"]))),
        "strategy": strategy,
        "jitter_ratio": min(1.0, max(0.0, float(configured.get("jitter_ratio", DEFAULT_RETRY_POLICY["jitter_ratio"])))),
        "max_total_wait_seconds": max(0, int(configured.get("max_total_wait_seconds", DEFAULT_RETRY_POLICY["max_total_wait_seconds"]))),
        "respect_retry_after": bool(configured.get("respect_retry_after", DEFAULT_RETRY_POLICY["respect_retry_after"])),
        "retry_response_parse_errors": bool(configured.get("retry_response_parse_errors", DEFAULT_RETRY_POLICY["retry_response_parse_errors"])),
    }


def _schedule_retry(
    session: Session,
    run: EvaluationRun,
    task: TaskUnit,
    retry_sample_ids: list[str],
    policy: dict[str, Any],
    *,
    provider_retry_after_seconds: float | None,
) -> bool:
    delay_seconds = _retry_delay_seconds(
        task.attempt_count,
        policy,
        provider_retry_after_seconds=provider_retry_after_seconds,
    )
    previous_wait = _nonnegative_float((task.payload or {}).get("retry_total_wait_seconds", 0))
    if previous_wait + delay_seconds > policy["max_total_wait_seconds"]:
        task.payload = {
            **task.payload,
            "retry_exhausted_reason": "max_total_wait_seconds",
            "retry_total_wait_seconds": previous_wait,
        }
        return False
    task.payload = {
        **task.payload,
        "retry_sample_ids": retry_sample_ids,
        "retry_total_wait_seconds": round(previous_wait + delay_seconds, 3),
        "last_retry_delay_seconds": delay_seconds,
    }
    task.status = TaskStatus.RETRY_SCHEDULED.value
    task.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
    clear_lease(task)
    _update_run_progress(session, run, retry_sample_ids)
    run.status = RunStatus.QUEUED.value
    session.commit()
    return True


def _retry_delay_seconds(
    attempt_count: int,
    policy: dict[str, Any],
    *,
    provider_retry_after_seconds: float | None,
) -> float:
    base_delay = float(policy["base_delay_seconds"])
    if policy["strategy"] == "fixed":
        delay = base_delay
    else:
        delay = base_delay * (2 ** max(0, attempt_count - 1))
    delay = min(float(policy["max_delay_seconds"]), delay)
    if policy["strategy"] == "exponential_jitter" and delay:
        delay *= 1 + random.uniform(-policy["jitter_ratio"], policy["jitter_ratio"])
    if policy["respect_retry_after"] and provider_retry_after_seconds is not None:
        delay = max(delay, provider_retry_after_seconds)
    return round(max(0.0, delay), 3)


def _nonnegative_float(value: object) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _finalize_task_and_run(session: Session, run: EvaluationRun, task: TaskUnit) -> None:
    task.status = TaskStatus.SUCCEEDED.value
    task.next_retry_at = None
    if isinstance(task.payload, dict) and "retry_sample_ids" in task.payload:
        task.payload = {key: value for key, value in task.payload.items() if key != "retry_sample_ids"}
    clear_lease(task)
    _update_run_progress(session, run, [])
    if run.failed_samples:
        run.status = RunStatus.COMPLETED_WITH_ERRORS.value
        task.status = TaskStatus.FAILED.value
    else:
        run.status = RunStatus.COMPLETED.value
    run.completed_at = datetime.now(timezone.utc)
    session.commit()


def _update_run_progress(
    session: Session,
    run: EvaluationRun,
    retry_sample_ids: list[str],
) -> None:
    latest: dict[str, SampleAttempt] = {}
    attempts = session.scalars(
        select(SampleAttempt)
        .where(SampleAttempt.run_id == run.id)
        .order_by(SampleAttempt.sample_id, SampleAttempt.attempt_number.desc())
    )
    for attempt in attempts:
        latest.setdefault(attempt.sample_id, attempt)
    retry_set = set(retry_sample_ids)
    successful = sum(attempt.status == SampleAttemptStatus.SUCCEEDED.value for attempt in latest.values())
    failed = sum(
        attempt.status == SampleAttemptStatus.FAILED.value and attempt.sample_id not in retry_set
        for attempt in latest.values()
    )
    run.successful_samples = successful
    run.failed_samples = failed
    run.completed_samples = successful + failed
