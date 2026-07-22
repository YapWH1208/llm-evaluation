from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.secrets import SecretCipher, SecretConfigurationError
from app.db import EvaluationRun, SampleAttempt
from app.services.evaluation_runs import RunCreationError, create_text_quick_check_run
from app.services.model_executor import ModelExecutor
from app.services.run_executor import RunExecutionError, execute_queued_text_run

router = APIRouter(prefix="/api/v1/evaluation-runs", tags=["evaluation runs"])


class EvaluationRunCreate(BaseModel):
    model_endpoint_id: str
    sample_limit: Annotated[int | None, Field(ge=1, le=3)] = None


class EvaluationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    model_endpoint_id: str
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
        return create_text_quick_check_run(
            session,
            model_endpoint_id=payload.model_endpoint_id,
            sample_limit=payload.sample_limit,
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


@router.get("/{run_id}", response_model=EvaluationRunResponse)
def get_evaluation_run(run_id: str, session: SessionDependency) -> EvaluationRun:
    run = session.get(EvaluationRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    return run
