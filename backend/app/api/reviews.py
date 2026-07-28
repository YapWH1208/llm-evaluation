from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from statistics import mean, pstdev
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import HumanReview, SampleAttempt
from app.db.mongo import MongoDocumentStore


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


def get_session(request: Request) -> Generator[Session | None, None, None]:
    if getattr(request.app.state, "document_store", None) is not None:
        yield None
        return
    session = request.app.state.database.get_session()
    try:
        yield session
    finally:
        session.close()


SessionDependency = Annotated[Session | None, Depends(get_session)]


@router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create(payload: ReviewCreate, request: Request, session: SessionDependency) -> HumanReview | dict[str, Any]:
    """Store independent primary/secondary reviews or an explicit adjudication."""

    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        if store.get_document("sample_attempts", payload.sample_attempt_id) is None:
            raise HTTPException(404, "Sample attempt not found")
        reviews = store.list_documents("human_reviews", query={"sample_attempt_id": payload.sample_attempt_id})
        _validate_new_review(payload, reviews)
        return store.insert_document(
            "human_reviews",
            {**payload.model_dump(), "created_at": datetime.now(timezone.utc)},
        )

    assert session is not None
    if session.get(SampleAttempt, payload.sample_attempt_id) is None:
        raise HTTPException(404, "Sample attempt not found")
    existing = list(
        session.scalars(
            select(HumanReview).where(HumanReview.sample_attempt_id == payload.sample_attempt_id)
        )
    )
    _validate_new_review(payload, existing)
    item = HumanReview(**payload.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.get("/sample/{sample_attempt_id}", response_model=list[ReviewResponse])
def list_for_sample(
    sample_attempt_id: str,
    request: Request,
    session: SessionDependency,
) -> list[HumanReview | dict[str, Any]]:
    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        return store.list_documents(
            "human_reviews",
            query={"sample_attempt_id": sample_attempt_id},
            sort=[("created_at", 1)],
        )
    assert session is not None
    return list(
        session.scalars(
            select(HumanReview)
            .where(HumanReview.sample_attempt_id == sample_attempt_id)
            .order_by(HumanReview.created_at)
        )
    )


@router.get("/sample/{sample_attempt_id}/agreement", response_model=ReviewAgreementResponse)
def review_agreement(
    sample_attempt_id: str,
    request: Request,
    session: SessionDependency,
) -> ReviewAgreementResponse:
    """Expose transparent dual-review agreement statistics and adjudication state."""

    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        if store.get_document("sample_attempts", sample_attempt_id) is None:
            raise HTTPException(404, "Sample attempt not found")
        return _agreement(sample_attempt_id, store.list_documents("human_reviews", query={"sample_attempt_id": sample_attempt_id}))
    assert session is not None
    if session.get(SampleAttempt, sample_attempt_id) is None:
        raise HTTPException(404, "Sample attempt not found")
    reviews = list(
        session.scalars(select(HumanReview).where(HumanReview.sample_attempt_id == sample_attempt_id))
    )
    return _agreement(sample_attempt_id, reviews)


def _validate_new_review(payload: ReviewCreate, reviews: list[Any]) -> None:
    existing = [_review_mapping(review) for review in reviews]
    if payload.review_stage in {"primary", "secondary"}:
        if any(
            review.get("reviewer_id") == payload.reviewer_id
            and review.get("review_stage", "primary") == payload.review_stage
            for review in existing
        ):
            raise HTTPException(409, "This reviewer already submitted that review stage for the sample")
        if payload.adjudicates_review_ids:
            raise HTTPException(422, "Only an adjudication review may reference prior reviews")
        return

    reference_ids = list(dict.fromkeys(payload.adjudicates_review_ids))
    non_adjudication = [review for review in existing if review.get("review_stage", "primary") != "adjudication"]
    available_ids = {str(review.get("id")) for review in non_adjudication}
    if len(reference_ids) < 2:
        raise HTTPException(422, "An adjudication must reference at least two primary or secondary reviews")
    if any(review_id not in available_ids for review_id in reference_ids):
        raise HTTPException(422, "Adjudication references a review from another sample or an unknown review")


def _agreement(sample_attempt_id: str, reviews: list[Any]) -> ReviewAgreementResponse:
    rows = [_review_mapping(review) for review in reviews]
    independent = [row for row in rows if row.get("review_stage", "primary") != "adjudication"]
    adjudications = [row for row in rows if row.get("review_stage") == "adjudication"]
    scores = [float(row["score"]) for row in independent if row.get("score") is not None]
    label_sets = [set(str(label) for label in row.get("labels", []) if isinstance(label, str)) for row in independent]
    label_agreement = _mean_pairwise_jaccard(label_sets)
    score_range = round(max(scores) - min(scores), 6) if scores else None
    numeric_score: dict[str, float | int | None] = {
        "count": len(scores),
        "mean": round(mean(scores), 6) if scores else None,
        "standard_deviation": round(pstdev(scores), 6) if len(scores) > 1 else 0.0 if scores else None,
        "range": score_range,
    }
    stage_counts = {stage: sum(row.get("review_stage", "primary") == stage for row in rows) for stage in ("primary", "secondary", "adjudication")}
    if adjudications:
        agreement_status = "adjudicated"
    elif len(independent) < 2 or len({str(row.get("reviewer_id")) for row in independent}) < 2:
        agreement_status = "awaiting_second_review"
    elif (score_range is not None and score_range > 0.1) or (label_agreement is not None and label_agreement < 0.8):
        agreement_status = "needs_adjudication"
    else:
        agreement_status = "agreement"
    return ReviewAgreementResponse(
        sample_attempt_id=sample_attempt_id,
        review_count=len(rows),
        distinct_reviewer_count=len({str(row.get("reviewer_id")) for row in rows}),
        review_stage_counts=stage_counts,
        numeric_score=numeric_score,
        label_agreement=label_agreement,
        status=agreement_status,
        adjudication_review_id=str(adjudications[-1].get("id")) if adjudications else None,
    )


def _review_mapping(review: Any) -> dict[str, Any]:
    if isinstance(review, dict):
        return review
    return {
        "id": review.id,
        "reviewer_id": review.reviewer_id,
        "score": review.score,
        "labels": review.labels,
        "review_stage": review.review_stage,
        "adjudicates_review_ids": review.adjudicates_review_ids,
    }


def _mean_pairwise_jaccard(label_sets: list[set[str]]) -> float | None:
    if len(label_sets) < 2:
        return None
    values: list[float] = []
    for index, left in enumerate(label_sets):
        for right in label_sets[index + 1 :]:
            union = left | right
            values.append(1.0 if not union else len(left & right) / len(union))
    return round(mean(values), 6) if values else None
