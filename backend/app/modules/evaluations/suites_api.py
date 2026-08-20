from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.modules.evaluations.service import EvaluationService


router = APIRouter(prefix="/api/v1/evaluation-suites", tags=["evaluation suites"])


class EvaluationSuiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    benchmark_list: list[dict[str, Any]] = Field(min_length=1)
    default_prompt_overrides: dict[str, Any] = Field(default_factory=dict)
    default_request_body: dict[str, Any] = Field(default_factory=dict)
    weight_configuration: dict[str, Any] = Field(default_factory=dict)
    version: str = Field(default="1", min_length=1, max_length=64)


class EvaluationSuiteUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=4000)
    benchmark_list: list[dict[str, Any]] | None = Field(default=None, min_length=1)
    default_prompt_overrides: dict[str, Any] | None = None
    default_request_body: dict[str, Any] | None = None
    weight_configuration: dict[str, Any] | None = None


class EvaluationSuiteResponse(EvaluationSuiteCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_by: str | None
    created_at: datetime


class SuiteRunCreate(BaseModel):
    model_endpoint_id: str
    sample_limit: int | None = Field(default=None, ge=1, le=3)
    request_body_override: dict[str, Any] = Field(default_factory=dict)
    max_concurrency: int | None = Field(default=None, ge=1, le=1000)


def get_evaluation_service(request: Request) -> EvaluationService:
    return request.app.state.evaluation_service


EvaluationServiceDependency = Annotated[EvaluationService, Depends(get_evaluation_service)]


@router.post("", response_model=EvaluationSuiteResponse, status_code=status.HTTP_201_CREATED)
def create_suite(
    payload: EvaluationSuiteCreate,
    request: Request,
    service: EvaluationServiceDependency,
) -> dict[str, Any]:
    return service.create_suite(
        payload.model_dump(),
        created_by=getattr(request.state, "actor_id", None),
    )


@router.get("", response_model=list[EvaluationSuiteResponse])
def list_suites(service: EvaluationServiceDependency) -> list[dict[str, Any]]:
    return service.list_suites()


@router.get("/{suite_id}", response_model=EvaluationSuiteResponse)
def get_suite(suite_id: str, service: EvaluationServiceDependency) -> dict[str, Any]:
    return service.get_suite(suite_id)


@router.patch("/{suite_id}", response_model=EvaluationSuiteResponse)
def update_suite(
    suite_id: str,
    payload: EvaluationSuiteUpdate,
    service: EvaluationServiceDependency,
) -> dict[str, Any]:
    return service.update_suite(suite_id, payload.model_dump(exclude_unset=True))


@router.post("/{suite_id}/runs", status_code=status.HTTP_201_CREATED)
def create_suite_runs(
    suite_id: str,
    payload: SuiteRunCreate,
    request: Request,
    service: EvaluationServiceDependency,
) -> list[dict[str, Any]]:
    return service.create_suite_runs(
        suite_id,
        model_endpoint_id=payload.model_endpoint_id,
        sample_limit=payload.sample_limit,
        request_body_override=payload.request_body_override,
        max_concurrency=payload.max_concurrency,
        created_by=getattr(request.state, "actor_id", None),
    )
