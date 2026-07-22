from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import EvaluationRun
from app.services.evaluation_runs import RunCreationError, create_text_quick_check_run

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


def get_session(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.database.get_session()
    try:
        yield session
    finally:
        session.close()


SessionDependency = Annotated[Session, Depends(get_session)]


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


@router.get("/{run_id}", response_model=EvaluationRunResponse)
def get_evaluation_run(run_id: str, session: SessionDependency) -> EvaluationRun:
    run = session.get(EvaluationRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    return run
