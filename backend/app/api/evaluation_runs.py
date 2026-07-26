from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.secrets import SecretCipher, SecretConfigurationError
from app.db import EvaluationRun, SampleAttempt, RunStatus, SampleAttemptStatus, TaskStatus, TaskUnit
from app.services.evaluation_runs import RunCreationError, create_benchmark_run
from app.services.model_executor import ModelExecutor
from app.services.run_analysis import build_run_summary
from app.services.run_executor import RunExecutionError, execute_queued_text_run
from app.services.run_operations import RunOperationError, clone_run, retry_failed_samples

router = APIRouter(prefix="/api/v1/evaluation-runs", tags=["evaluation runs"])


class EvaluationRunCreate(BaseModel):
    model_endpoint_id: str
    sample_limit: Annotated[int | None, Field(ge=1, le=3)] = None
    prompt_package_id: str | None = None
    benchmark_id: str = "text-quick-check"
    benchmark_version: str = "1.0.0"


class EvaluationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    model_endpoint_id: str
    prompt_package_id: str | None
    benchmark_id: str
    benchmark_version: str
    configuration_snapshot: dict[str, Any]
    status: str
    total_samples: int
    completed_samples: int
    successful_samples: int
    failed_samples: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class SampleAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sample_id: str
    attempt_number: int
    input_snapshot: dict[str, Any]
    reference_snapshot: dict[str, Any]
    request_snapshot: dict[str, Any] | None
    raw_response: str | None
    parsed_prediction: str | None
    score: float | None
    latency_ms: float | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: float | None
    error_type: str | None
    error_message: str | None
    status: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


def get_session(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.database.get_session()
    try:
        yield session
    finally:
        session.close()


def get_cipher(request: Request) -> SecretCipher:
    try:
        return SecretCipher(request.app.state.settings.secret_encryption_key)
    except SecretConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


def get_model_executor(request: Request) -> ModelExecutor:
    return request.app.state.model_executor


SessionDependency = Annotated[Session, Depends(get_session)]
CipherDependency = Annotated[SecretCipher, Depends(get_cipher)]
ModelExecutorDependency = Annotated[ModelExecutor, Depends(get_model_executor)]


@router.post("", response_model=EvaluationRunResponse, status_code=status.HTTP_201_CREATED)
def create_evaluation_run(
    payload: EvaluationRunCreate,
    session: SessionDependency,
) -> EvaluationRun:
    try:
        return create_benchmark_run(
            session,
            model_endpoint_id=payload.model_endpoint_id,
            sample_limit=payload.sample_limit,
            prompt_package_id=payload.prompt_package_id,
            benchmark_id=payload.benchmark_id,
            benchmark_version=payload.benchmark_version,
        )
    except RunCreationError as error:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if str(error) == "Model endpoint not found."
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=status_code, detail=str(error)) from error


@router.get("", response_model=list[EvaluationRunResponse])
def list_evaluation_runs(session: SessionDependency) -> list[EvaluationRun]:
    return list(session.scalars(select(EvaluationRun).order_by(EvaluationRun.created_at.desc())))

@router.post("/{run_id}/pause", response_model=EvaluationRunResponse)
def pause_evaluation_run(run_id: str, session: SessionDependency) -> EvaluationRun:
    run = session.get(EvaluationRun, run_id)
    if run is None: raise HTTPException(404, "Evaluation run not found")
    if run.status not in {RunStatus.QUEUED.value, RunStatus.RUNNING.value}: raise HTTPException(409, "Run cannot be paused in its current state")
    run.status = RunStatus.PAUSED.value
    session.query(TaskUnit).filter(TaskUnit.run_id == run.id, TaskUnit.status.in_([TaskStatus.PENDING.value, TaskStatus.RUNNING.value])).update({TaskUnit.status: TaskStatus.CANCELLED.value})
    session.commit(); session.refresh(run); return run

@router.post("/{run_id}/resume", response_model=EvaluationRunResponse)
def resume_evaluation_run(run_id: str, session: SessionDependency) -> EvaluationRun:
    run = session.get(EvaluationRun, run_id)
    if run is None: raise HTTPException(404, "Evaluation run not found")
    if run.status != RunStatus.PAUSED.value: raise HTTPException(409, "Only paused runs can be resumed")
    run.status = RunStatus.QUEUED.value
    for task in session.scalars(select(TaskUnit).where(TaskUnit.run_id == run.id)):
        if task.status == TaskStatus.CANCELLED.value: task.status = TaskStatus.PENDING.value
    session.commit(); session.refresh(run); return run

@router.post("/{run_id}/cancel", response_model=EvaluationRunResponse)
def cancel_evaluation_run(run_id: str, session: SessionDependency) -> EvaluationRun:
    run = session.get(EvaluationRun, run_id)
    if run is None: raise HTTPException(404, "Evaluation run not found")
    if run.status in {RunStatus.COMPLETED.value, RunStatus.COMPLETED_WITH_ERRORS.value, RunStatus.CANCELLED.value}: raise HTTPException(409, "Run cannot be cancelled in its current state")
    run.status = RunStatus.CANCELLED.value
    session.query(TaskUnit).filter(TaskUnit.run_id == run.id).update({TaskUnit.status: TaskStatus.CANCELLED.value})
    session.query(SampleAttempt).filter(SampleAttempt.run_id == run.id, SampleAttempt.status == SampleAttemptStatus.PENDING.value).update({SampleAttempt.status: SampleAttemptStatus.CANCELLED.value})
    session.commit(); session.refresh(run); return run


@router.post("/{run_id}/clone", response_model=EvaluationRunResponse, status_code=status.HTTP_201_CREATED)
def clone_evaluation_run(run_id: str, session: SessionDependency) -> EvaluationRun:
    try:
        return clone_run(session, run_id)
    except RunOperationError as error:
        status_code = status.HTTP_404_NOT_FOUND if str(error) == "Evaluation run not found." else status.HTTP_409_CONFLICT
        raise HTTPException(status_code, str(error)) from error


@router.post("/{run_id}/retry-failed", response_model=EvaluationRunResponse)
def retry_failed_evaluation_samples(run_id: str, session: SessionDependency) -> EvaluationRun:
    try:
        return retry_failed_samples(session, run_id)
    except RunOperationError as error:
        status_code = status.HTTP_404_NOT_FOUND if str(error) == "Evaluation run not found." else status.HTTP_409_CONFLICT
        raise HTTPException(status_code, str(error)) from error


@router.post("/{run_id}/execute", response_model=EvaluationRunResponse)
def execute_evaluation_run(
    run_id: str,
    session: SessionDependency,
    cipher: CipherDependency,
    model_executor: ModelExecutorDependency,
) -> EvaluationRun:
    try:
        return execute_queued_text_run(
            session,
            run_id=run_id,
            cipher=cipher,
            model_executor=model_executor,
        )
    except RunExecutionError as error:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if str(error) == "Evaluation run not found."
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=status_code, detail=str(error)) from error
    except SecretConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.get("/{run_id}/attempts", response_model=list[SampleAttemptResponse])
def list_sample_attempts(run_id: str, session: SessionDependency) -> list[SampleAttempt]:
    run = session.get(EvaluationRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    return list(
        session.scalars(
            select(SampleAttempt)
            .where(SampleAttempt.run_id == run.id)
            .order_by(SampleAttempt.created_at)
        )
    )


@router.get("/{run_id}/summary")
def get_run_summary(run_id: str, session: SessionDependency) -> dict[str, Any]:
    run = session.get(EvaluationRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    return build_run_summary(session, run)


@router.get("/{run_id}", response_model=EvaluationRunResponse)
def get_evaluation_run(run_id: str, session: SessionDependency) -> EvaluationRun:
    run = session.get(EvaluationRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    return run
