from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.benchmarks.prompts import PromptTemplateError, validate_template
from app.modules.benchmarks.scoring import ScoringError, validate_scoring_rule
from app.modules.benchmarks.service import PromptPackageService


router = APIRouter(prefix="/api/v1/prompt-packages", tags=["prompt packages"])


class PromptPackageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=64)
    prompt_type: Literal["official", "platform_default", "user_custom", "benchmark_variant", "language_specific"] = (
        "user_custom"
    )
    system_message: str | None = None
    user_template: str = Field(min_length=1)
    few_shot_examples: list[Any] = Field(default_factory=list)
    output_format: dict[str, Any] | None = None
    response_parser: dict[str, Any] | None = None
    scoring_rule: dict[str, Any] | None = None
    change_log: str | None = None

    @field_validator("user_template")
    @classmethod
    def validate_user_template(cls, value: str) -> str:
        try:
            validate_template(value)
        except PromptTemplateError as error:
            raise ValueError(str(error)) from error
        return value

    @field_validator("scoring_rule")
    @classmethod
    def validate_scoring_rule_config(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return value
        try:
            validate_scoring_rule(value)
        except ScoringError as error:
            raise ValueError(str(error)) from error
        return value


class PromptPackageResponse(PromptPackageCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime


def get_prompt_package_service(request: Request) -> PromptPackageService:
    return request.app.state.prompt_package_service


PromptPackageServiceDependency = Annotated[PromptPackageService, Depends(get_prompt_package_service)]


@router.post("", response_model=PromptPackageResponse, status_code=status.HTTP_201_CREATED)
def create_prompt_package(payload: PromptPackageCreate, service: PromptPackageServiceDependency) -> Any:
    return service.create(payload)


@router.get("", response_model=list[PromptPackageResponse])
def list_prompt_packages(service: PromptPackageServiceDependency) -> list[Any]:
    return service.list()


@router.put("/{prompt_package_id}", response_model=PromptPackageResponse)
def update_prompt_package(
    prompt_package_id: str,
    payload: PromptPackageCreate,
    service: PromptPackageServiceDependency,
) -> Any:
    return service.update(prompt_package_id, payload)


@router.delete("/{prompt_package_id}", response_model=PromptPackageResponse)
def delete_prompt_package(prompt_package_id: str, service: PromptPackageServiceDependency) -> Any:
    return service.delete(prompt_package_id)
