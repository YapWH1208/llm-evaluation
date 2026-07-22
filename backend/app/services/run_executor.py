from __future__ import annotations

from datetime import datetime, timezone

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
from app.services.model_executor import ModelExecutor, normalize_exact_match


class RunExecutionError(ValueError):
    """Raised when a queued run cannot be executed."""


def execute_queued_text_run(
    session: Session,
    *,
    run_id: str,
    cipher: SecretCipher,
    model_executor: ModelExecutor,
) -> EvaluationRun:
    run = session.get(EvaluationRun, run_id)
    if run is None:
        raise RunExecutionError("Evaluation run not found.")
    if run.status != RunStatus.QUEUED.value:
        raise RunExecutionError("Only queued evaluation runs can be executed.")

    endpoint = session.get(ModelEndpoint, run.model_endpoint_id)
    if endpoint is None:
        raise RunExecutionError("The model endpoint for this run no longer exists.")

    task = session.scalar(select(TaskUnit).where(TaskUnit.run_id == run.id))
    if task is None:
        raise RunExecutionError("No task was created for this evaluation run.")

    api_key = cipher.decrypt(endpoint.encrypted_api_key)
    now = datetime.now(timezone.utc)
    run.status = RunStatus.RUNNING.value
    run.started_at = now
    task.status = TaskStatus.RUNNING.value
    task.attempt_count += 1
    session.commit()

    attempts = list(
        session.scalars(
            select(SampleAttempt)
            .where(
                SampleAttempt.run_id == run.id,
                SampleAttempt.status == SampleAttemptStatus.PENDING.value,
            )
            .order_by(SampleAttempt.created_at)
        )
    )

    for attempt in attempts:
        attempt.status = SampleAttemptStatus.RUNNING.value
        attempt.started_at = datetime.now(timezone.utc)
        session.commit()

        result = model_executor.execute(endpoint, api_key, attempt.input_snapshot)
        attempt.request_snapshot = result.request_snapshot
        attempt.raw_response = result.raw_response
        attempt.parsed_prediction = result.prediction
        attempt.completed_at = datetime.now(timezone.utc)

        if result.success and result.prediction is not None:
            reference_answer = str(attempt.reference_snapshot["answer"])
            attempt.score = float(
                normalize_exact_match(result.prediction) == normalize_exact_match(reference_answer)
            )
            attempt.status = SampleAttemptStatus.SUCCEEDED.value
            attempt.error_type = None
            attempt.error_message = None
        else:
            attempt.status = SampleAttemptStatus.FAILED.value
            attempt.error_type = result.error_type or "execution_error"
            attempt.error_message = result.error_message or "Sample execution failed."
        session.commit()

    _finalize_run(session, run, task)
    return run


def _finalize_run(session: Session, run: EvaluationRun, task: TaskUnit) -> None:
    attempts = list(session.scalars(select(SampleAttempt).where(SampleAttempt.run_id == run.id)))
    successful = sum(attempt.status == SampleAttemptStatus.SUCCEEDED.value for attempt in attempts)
    failed = sum(attempt.status == SampleAttemptStatus.FAILED.value for attempt in attempts)

    run.completed_samples = successful + failed
    run.successful_samples = successful
    run.failed_samples = failed
    run.completed_at = datetime.now(timezone.utc)
    if failed:
        run.status = RunStatus.COMPLETED_WITH_ERRORS.value
        task.status = TaskStatus.FAILED.value
    else:
        run.status = RunStatus.COMPLETED.value
        task.status = TaskStatus.SUCCEEDED.value
    session.commit()
    session.refresh(run)
