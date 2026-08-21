from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean, pstdev
from typing import Any

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.reviews.ports import ReviewRepository


class ReviewService:
    """Human-review behavior shared by every persistence adapter."""

    def __init__(self, repository: ReviewRepository) -> None:
        self._repository = repository

    def create(self, payload: Any) -> Any:
        if not self._repository.sample_attempt_exists(payload.sample_attempt_id):
            raise NotFoundError("Sample attempt not found", context={"sample_attempt_id": payload.sample_attempt_id})
        existing = self._repository.list_for_sample(payload.sample_attempt_id)
        _validate_new_review(payload, existing)
        return self._repository.create({**payload.model_dump(), "created_at": datetime.now(timezone.utc)})

    def list_for_sample(self, sample_attempt_id: str) -> list[Any]:
        return self._repository.list_for_sample(sample_attempt_id)

    def agreement(self, sample_attempt_id: str) -> dict[str, Any]:
        if not self._repository.sample_attempt_exists(sample_attempt_id):
            raise NotFoundError("Sample attempt not found", context={"sample_attempt_id": sample_attempt_id})
        return _agreement(sample_attempt_id, self._repository.list_for_sample(sample_attempt_id))


def _validate_new_review(payload: Any, reviews: list[Any]) -> None:
    existing = [_review_mapping(review) for review in reviews]
    if payload.review_stage in {"primary", "secondary"}:
        if any(
            review.get("reviewer_id") == payload.reviewer_id
            and review.get("review_stage", "primary") == payload.review_stage
            for review in existing
        ):
            raise ConflictError("This reviewer already submitted that review stage for the sample")
        if payload.adjudicates_review_ids:
            raise ValidationError("Only an adjudication review may reference prior reviews")
        return

    reference_ids = list(dict.fromkeys(payload.adjudicates_review_ids))
    non_adjudication = [review for review in existing if review.get("review_stage", "primary") != "adjudication"]
    available_ids = {str(review.get("id")) for review in non_adjudication}
    if len(reference_ids) < 2:
        raise ValidationError("An adjudication must reference at least two primary or secondary reviews")
    if any(review_id not in available_ids for review_id in reference_ids):
        raise ValidationError("Adjudication references a review from another sample or an unknown review")


def _agreement(sample_attempt_id: str, reviews: list[Any]) -> dict[str, Any]:
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
    stage_counts = {
        stage: sum(row.get("review_stage", "primary") == stage for row in rows)
        for stage in ("primary", "secondary", "adjudication")
    }
    if adjudications:
        agreement_status = "adjudicated"
    elif len(independent) < 2 or len({str(row.get("reviewer_id")) for row in independent}) < 2:
        agreement_status = "awaiting_second_review"
    elif (score_range is not None and score_range > 0.1) or (label_agreement is not None and label_agreement < 0.8):
        agreement_status = "needs_adjudication"
    else:
        agreement_status = "agreement"
    return {
        "sample_attempt_id": sample_attempt_id,
        "review_count": len(rows),
        "distinct_reviewer_count": len({str(row.get("reviewer_id")) for row in rows}),
        "review_stage_counts": stage_counts,
        "numeric_score": numeric_score,
        "label_agreement": label_agreement,
        "status": agreement_status,
        "adjudication_review_id": str(adjudications[-1].get("id")) if adjudications else None,
    }


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
