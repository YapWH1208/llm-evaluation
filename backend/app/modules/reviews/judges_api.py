from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import ConfigurationError
from app.core.secrets import SecretCipher, SecretConfigurationError
from app.infrastructure.providers.contracts import ModelExecutor
from app.modules.reviews.judges import JudgeService


router = APIRouter(prefix="/api/v1/judge-assessments", tags=["LLM-as-judge"])


class JudgeAssessmentCreate(BaseModel):
    sample_attempt_id: str
    judge_endpoint_id: str
    rubric: dict[str, Any] = Field(default_factory=dict)


class JudgeComparisonCreate(JudgeAssessmentCreate):
    comparison_sample_attempt_id: str
    swap_test: bool = True


class JudgeAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sample_attempt_id: str
    judge_endpoint_id: str
    comparison_sample_attempt_id: str | None = None
    rubric: dict[str, Any]
    answer_order: list[str] = Field(default_factory=list)
    swap_test_group_id: str | None = None
    selected_answer: str | None = None
    score: float | None
    label: str | None
    rationale: str | None
    raw_response: str | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: float | None
    status: str
    error_message: str | None
    created_at: datetime


def get_judge_service(request: Request) -> JudgeService:
    return request.app.state.judge_service


def get_cipher(request: Request) -> SecretCipher:
    try:
        return SecretCipher(request.app.state.settings.secret_encryption_key)
    except SecretConfigurationError as error:
        raise ConfigurationError(str(error)) from error


def get_model_executor(request: Request) -> ModelExecutor:
    return request.app.state.model_executor


JudgeServiceDependency = Annotated[JudgeService, Depends(get_judge_service)]
CipherDependency = Annotated[SecretCipher, Depends(get_cipher)]
ModelExecutorDependency = Annotated[ModelExecutor, Depends(get_model_executor)]


@router.post("", response_model=JudgeAssessmentResponse, status_code=status.HTTP_201_CREATED)
def create_judge_assessment(
    payload: JudgeAssessmentCreate,
    service: JudgeServiceDependency,
    cipher: CipherDependency,
    model_executor: ModelExecutorDependency,
) -> Any:
    return service.assess(
        sample_attempt_id=payload.sample_attempt_id,
        judge_endpoint_id=payload.judge_endpoint_id,
        rubric=payload.rubric,
        cipher=cipher,
        model_executor=model_executor,
    )


@router.post("/compare", response_model=list[JudgeAssessmentResponse], status_code=status.HTTP_201_CREATED)
def create_judge_comparison(
    payload: JudgeComparisonCreate,
    service: JudgeServiceDependency,
    cipher: CipherDependency,
    model_executor: ModelExecutorDependency,
) -> list[Any]:
    return service.assess_pairwise(
        sample_attempt_id=payload.sample_attempt_id,
        comparison_sample_attempt_id=payload.comparison_sample_attempt_id,
        judge_endpoint_id=payload.judge_endpoint_id,
        rubric=payload.rubric,
        swap_test=payload.swap_test,
        cipher=cipher,
        model_executor=model_executor,
    )


@router.get("/sample/{sample_attempt_id}", response_model=list[JudgeAssessmentResponse])
def list_judge_assessments(sample_attempt_id: str, service: JudgeServiceDependency) -> list[Any]:
    return service.list_for_sample(sample_attempt_id)


@router.get("/sample/{sample_attempt_id}/agreement")
def get_judge_agreement(sample_attempt_id: str, service: JudgeServiceDependency) -> dict[str, object]:
    return service.agreement(sample_attempt_id)
