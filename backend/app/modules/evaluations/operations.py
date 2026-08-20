from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    EvaluationRun,
    ModelEndpoint,
    RunStatus,
    SampleAttempt,
    SampleAttemptStatus,
    TaskStatus,
    TaskType,
    TaskUnit,
)
from app.modules.evaluations.service import RunCreationError, _split_items_for_endpoint_budget
from app.modules.evaluations.analysis import latest_attempts


class RunOperationError(ValueError):
    pass


def retry_failed_samples(session: Session, run_id: str) -> EvaluationRun:
    run = session.get(EvaluationRun, run_id)
    if run is None:
        raise RunOperationError("Evaluation run not found.")
    if run.status not in {RunStatus.COMPLETED.value, RunStatus.COMPLETED_WITH_ERRORS.value}:
        raise RunOperationError("Only completed evaluation runs can retry failed samples.")

    failed_attempts = [
        attempt for attempt in latest_attempts(session, run.id) if attempt.status == SampleAttemptStatus.FAILED.value
    ]
    if not failed_attempts:
        raise RunOperationError("This run has no failed samples to retry.")
    endpoint = session.get(ModelEndpoint, run.model_endpoint_id)
    if endpoint is None:
        raise RunOperationError("The model endpoint for this run no longer exists.")

    latest_task = session.scalar(
        select(TaskUnit)
        .where(TaskUnit.run_id == run.id, TaskUnit.task_type == TaskType.EVALUATION_SHARD.value)
        .order_by(TaskUnit.created_at.desc())
        .limit(1)
    )
    source_policy = (
        latest_task.payload.get("retry_policy") if latest_task and isinstance(latest_task.payload, dict) else None
    )
    retry_policy = (
        source_policy
        if isinstance(source_policy, dict)
        else {"max_attempts": 3, "base_delay_seconds": 2, "max_delay_seconds": 60}
    )
    benchmark_task = session.scalar(
        select(TaskUnit)
        .where(TaskUnit.run_id == run.id, TaskUnit.task_type == TaskType.BENCHMARK.value)
        .order_by(TaskUnit.created_at.desc())
        .limit(1)
    )
    try:
        retry_groups = _split_items_for_endpoint_budget(
            (tuple(failed_attempts),), endpoint, token_estimate=_estimate_retry_attempt_tokens
        )
    except RunCreationError as error:
        raise RunOperationError(str(error)) from error
    for group in retry_groups:
        token_estimates = {attempt.sample_id: _estimate_retry_attempt_tokens(attempt) for attempt in group}
        task = TaskUnit(
            run_id=run.id,
            parent_task_id=benchmark_task.id if benchmark_task is not None else None,
            task_type=TaskType.EVALUATION_SHARD.value,
            payload={
                "sample_ids": [attempt.sample_id for attempt in group],
                "estimated_request_count": len(group),
                "estimated_token_count": sum(token_estimates.values()),
                "sample_token_estimates": token_estimates,
                "retry_policy": retry_policy,
                "manual_retry": True,
            },
            status=TaskStatus.PENDING.value,
        )
        session.add(task)
        session.flush()
        session.add_all(
            [
                SampleAttempt(
                    run_id=run.id,
                    task_id=task.id,
                    sample_id=attempt.sample_id,
                    attempt_number=attempt.attempt_number + 1,
                    input_snapshot=attempt.input_snapshot,
                    reference_snapshot=attempt.reference_snapshot,
                    status=SampleAttemptStatus.PENDING.value,
                )
                for attempt in group
            ]
        )
    run.status = RunStatus.QUEUED.value
    run.completed_at = None
    run.completed_samples -= len(failed_attempts)
    run.failed_samples = 0
    session.commit()
    session.refresh(run)
    return run


def _estimate_retry_attempt_tokens(attempt: SampleAttempt) -> int:
    """Recover a conservative admission estimate from durable attempt evidence."""

    snapshot = attempt.input_snapshot if isinstance(attempt.input_snapshot, dict) else {}
    messages = snapshot.get("messages") if isinstance(snapshot.get("messages"), list) else []
    encoded = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    media_parts = sum(
        1
        for message in messages
        if isinstance(message, dict) and isinstance(message.get("content"), list)
        for part in message["content"]
        if isinstance(part, dict) and part.get("type") not in {"text", "tool_result"}
    )
    return max(1, (len(encoded) + 3) // 4) + 32 + (media_parts * 256)
