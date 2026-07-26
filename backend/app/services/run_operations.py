from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EvaluationRun, RunStatus, SampleAttempt, SampleAttemptStatus, TaskStatus, TaskUnit
from app.services.evaluation_runs import RunCreationError, create_benchmark_run
from app.services.run_analysis import latest_attempts


class RunOperationError(ValueError):
    pass


def clone_run(session: Session, run_id: str) -> EvaluationRun:
    source = session.get(EvaluationRun, run_id)
    if source is None:
        raise RunOperationError("Evaluation run not found.")
    try:
        return create_benchmark_run(
            session,
            model_endpoint_id=source.model_endpoint_id,
            sample_limit=source.total_samples,
            prompt_package_id=source.prompt_package_id,
            benchmark_id=source.benchmark_id,
            benchmark_version=source.benchmark_version,
        )
    except RunCreationError as error:
        raise RunOperationError(str(error)) from error


def retry_failed_samples(session: Session, run_id: str) -> EvaluationRun:
    run = session.get(EvaluationRun, run_id)
    if run is None:
        raise RunOperationError("Evaluation run not found.")
    if run.status not in {RunStatus.COMPLETED.value, RunStatus.COMPLETED_WITH_ERRORS.value}:
        raise RunOperationError("Only completed evaluation runs can retry failed samples.")

    failed_attempts = [
        attempt
        for attempt in latest_attempts(session, run.id)
        if attempt.status == SampleAttemptStatus.FAILED.value
    ]
    if not failed_attempts:
        raise RunOperationError("This run has no failed samples to retry.")

    latest_task = session.scalar(
        select(TaskUnit)
        .where(TaskUnit.run_id == run.id)
        .order_by(TaskUnit.created_at.desc())
        .limit(1)
    )
    source_policy = latest_task.payload.get("retry_policy") if latest_task and isinstance(latest_task.payload, dict) else None
    retry_policy = source_policy if isinstance(source_policy, dict) else {"max_attempts": 3, "base_delay_seconds": 2, "max_delay_seconds": 60}
    task = TaskUnit(
        run_id=run.id,
        task_type="evaluation_shard",
        payload={
            "sample_ids": [attempt.sample_id for attempt in failed_attempts],
            "estimated_request_count": len(failed_attempts),
            "estimated_token_count": 0,
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
            for attempt in failed_attempts
        ]
    )
    run.status = RunStatus.QUEUED.value
    run.completed_at = None
    run.completed_samples -= len(failed_attempts)
    run.failed_samples = 0
    session.commit()
    session.refresh(run)
    return run
