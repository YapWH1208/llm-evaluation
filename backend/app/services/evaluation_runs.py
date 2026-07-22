from __future__ import annotations

from sqlalchemy.orm import Session

from app.benchmarks import TEXT_QUICK_CHECK
from app.db import (
    EndpointStatus,
    EvaluationRun,
    ModelEndpoint,
    RunStatus,
    SampleAttempt,
    TaskStatus,
    TaskUnit,
)


class RunCreationError(ValueError):
    """Raised when a requested evaluation run cannot be scheduled."""


def create_text_quick_check_run(
    session: Session,
    *,
    model_endpoint_id: str,
    sample_limit: int | None,
) -> EvaluationRun:
    endpoint = session.get(ModelEndpoint, model_endpoint_id)
    if endpoint is None:
        raise RunCreationError("Model endpoint not found.")
    if endpoint.status != EndpointStatus.AVAILABLE.value:
        raise RunCreationError("Model endpoint must pass a connection test before scheduling a run.")

    samples = TEXT_QUICK_CHECK.samples[:sample_limit]
    if not samples:
        raise RunCreationError("At least one benchmark sample is required.")

    snapshot = {
        "benchmark": {
            "id": TEXT_QUICK_CHECK.identifier,
            "version": TEXT_QUICK_CHECK.version,
        },
        "endpoint": {
            "id": endpoint.id,
            "base_url": endpoint.base_url,
            "model_name": endpoint.model_name,
            "protocol_profile": endpoint.protocol_profile,
            "default_request_body": endpoint.default_request_body,
        },
        "sample_ids": [sample.sample_id for sample in samples],
    }
    run = EvaluationRun(
        model_endpoint_id=endpoint.id,
        benchmark_id=TEXT_QUICK_CHECK.identifier,
        benchmark_version=TEXT_QUICK_CHECK.version,
        configuration_snapshot=snapshot,
        status=RunStatus.QUEUED.value,
        total_samples=len(samples),
    )
    session.add(run)
    session.flush()

    task = TaskUnit(
        run_id=run.id,
        task_type="evaluation_shard",
        payload={"sample_ids": [sample.sample_id for sample in samples]},
        status=TaskStatus.PENDING.value,
    )
    session.add(task)
    session.flush()

    session.add_all(
        [
            SampleAttempt(
                run_id=run.id,
                task_id=task.id,
                sample_id=sample.sample_id,
                input_snapshot={
                    "messages": [{"role": "user", "content": sample.prompt}],
                    "modality": "text",
                },
                reference_snapshot={"type": "exact_match", "answer": sample.reference_answer},
            )
            for sample in samples
        ]
    )
    session.commit()
    session.refresh(run)
    return run
