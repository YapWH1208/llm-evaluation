from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.modules.analytics.leaderboard import (
    LeaderboardFilters,
    LeaderboardQuery,
    LeaderboardService,
)


router = APIRouter(prefix="/api/v1/leaderboard", tags=["leaderboard"])


def get_leaderboard_service(request: Request) -> LeaderboardService:
    return request.app.state.leaderboard_service


LeaderboardServiceDependency = Annotated[LeaderboardService, Depends(get_leaderboard_service)]


@router.get("")
def leaderboard(
    service: LeaderboardServiceDependency,
    dataset: str | None = Query(default=None, max_length=128),
    model_endpoint_id: str | None = Query(default=None, max_length=128),
    statuses: list[str] | None = Query(default=None, alias="status"),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    capability: str | None = Query(default=None, max_length=64),
    language: str | None = Query(default=None, max_length=64),
    evaluation_type: str | None = Query(default=None, max_length=32),
    available_metric: str | None = Query(default=None, max_length=128),
    sort: str = Query(default="default", min_length=1, max_length=128),
    direction: str = Query(default="desc", min_length=3, max_length=4),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> dict[str, object]:
    return service.query(
        LeaderboardQuery(
            filters=LeaderboardFilters(
                dataset=dataset,
                model_endpoint_id=model_endpoint_id,
                statuses=frozenset(statuses) if statuses is not None else None,
                created_from=created_from,
                created_to=created_to,
                capability=capability,
                language=language,
                evaluation_type=evaluation_type,
                available_metric=available_metric,
            ),
            sort=sort,
            direction=direction,
            page=page,
            page_size=page_size,
        )
    )
