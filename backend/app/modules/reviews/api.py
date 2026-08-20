from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.modules.reviews.service import ReviewService


router = APIRouter(prefix="/api/v1/reviews", tags=["human review"])
ReviewStage = Literal["primary", "secondary", "adjudication"]


class ReviewCreate(BaseModel):
    sample_attempt_id: str
    reviewer_id: str = Field(min_length=1, max_length=128)
    rubric: dict[str, Any] | None = None
    score: float | None = Field(default=None, ge=0, le=1)
    labels: list[str] = Field(default_factory=list, max_length=64)
    notes: str | None = Field(default=None, max_length=10_000)
    review_stage: ReviewStage = "primary"
    adjudicates_review_ids: list[str] = Field(default_factory=list, max_length=32)


class ReviewResponse(ReviewCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime


class ReviewAgreementResponse(BaseModel):
    sample_attempt_id: str
    review_count: int
    distinct_reviewer_count: int
    review_stage_counts: dict[str, int]
    numeric_score: dict[str, float | int | None]
    label_agreement: float | None
    status: str
    adjudication_review_id: str | None


def get_review_service(request: Request) -> ReviewService:
    return request.app.state.review_service


ReviewServiceDependency = Annotated[ReviewService, Depends(get_review_service)]


@router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create(payload: ReviewCreate, service: ReviewServiceDependency) -> Any:
    """Store independent primary/secondary reviews or an explicit adjudication."""
    return service.create(payload)


@router.get("/sample/{sample_attempt_id}", response_model=list[ReviewResponse])
def list_for_sample(
    sample_attempt_id: str,
    service: ReviewServiceDependency,
) -> list[Any]:
    return service.list_for_sample(sample_attempt_id)


@router.get("/sample/{sample_attempt_id}/agreement", response_model=ReviewAgreementResponse)
def review_agreement(
    sample_attempt_id: str,
    service: ReviewServiceDependency,
) -> ReviewAgreementResponse:
    """Expose transparent dual-review agreement statistics and adjudication state."""
    return ReviewAgreementResponse.model_validate(service.agreement(sample_attempt_id))
