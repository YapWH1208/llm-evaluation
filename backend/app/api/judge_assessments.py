from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.secrets import SecretCipher, SecretConfigurationError
from app.db.models import JudgeAssessment
from app.services.judge_assessments import JudgeAssessmentError, assess_sample_attempt
from app.services.model_executor import ModelExecutor


router = APIRouter(prefix="/api/v1/judge-assessments", tags=["LLM-as-judge"])


class JudgeAssessmentCreate(BaseModel):
    sample_attempt_id: str
    judge_endpoint_id: str
    rubric: dict[str, Any] = Field(default_factory=dict)


class JudgeAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sample_attempt_id: str
    judge_endpoint_id: str
    rubric: dict[str, Any]
    score: float | None
    label: str | None
    rationale: str | None
    raw_response: str | None
    status: str
    error_message: str | None
    created_at: datetime


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
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error


def get_model_executor(request: Request) -> ModelExecutor:
    return request.app.state.model_executor


SessionDependency = Annotated[Session, Depends(get_session)]
CipherDependency = Annotated[SecretCipher, Depends(get_cipher)]
ModelExecutorDependency = Annotated[ModelExecutor, Depends(get_model_executor)]


@router.post("", response_model=JudgeAssessmentResponse, status_code=status.HTTP_201_CREATED)
def create_judge_assessment(
    payload: JudgeAssessmentCreate,
    session: SessionDependency,
    cipher: CipherDependency,
    model_executor: ModelExecutorDependency,
) -> JudgeAssessment:
    try:
        return assess_sample_attempt(
            session,
            sample_attempt_id=payload.sample_attempt_id,
            judge_endpoint_id=payload.judge_endpoint_id,
            rubric=payload.rubric,
            cipher=cipher,
            model_executor=model_executor,
        )
    except JudgeAssessmentError as error:
        status_code = status.HTTP_404_NOT_FOUND if str(error).endswith("not found.") else status.HTTP_409_CONFLICT
        raise HTTPException(status_code, str(error)) from error


@router.get("/sample/{sample_attempt_id}", response_model=list[JudgeAssessmentResponse])
def list_judge_assessments(sample_attempt_id: str, session: SessionDependency) -> list[JudgeAssessment]:
    return list(
        session.scalars(
            select(JudgeAssessment)
            .where(JudgeAssessment.sample_attempt_id == sample_attempt_id)
            .order_by(JudgeAssessment.created_at.desc())
        )
    )
