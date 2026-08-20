from __future__ import annotations

from collections import defaultdict
from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AggregateMetric, EvaluationRun, ModelEndpoint, RunStatus
from app.db.mongo import MongoDocumentStore
from app.modules.datasets.metadata import EVALUATION_TYPES
from app.modules.analytics.leaderboard import (
    LeaderboardFilters,
    LeaderboardQuery,
    LeaderboardQueryError,
    SORT_FIELDS,
    build_leaderboard,
)
from app.modules.benchmarks.metrics import metric_definitions


router = APIRouter(prefix="/api/v1/leaderboard", tags=["leaderboard"])
ALLOWED_STATUSES = frozenset(status.value for status in RunStatus)
ALLOWED_METRICS = frozenset(definition.metric_name for definition in metric_definitions())


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


@router.get("")
def leaderboard(
    request: Request,
    session: SessionDependency,
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
    """Return one filtered and deterministically ordered leaderboard page."""

    unknown_statuses = sorted(set(statuses or ()) - ALLOWED_STATUSES)
    if unknown_statuses:
        raise HTTPException(422, f"Unknown run status: {', '.join(unknown_statuses)}.")
    if evaluation_type is not None and evaluation_type not in EVALUATION_TYPES:
        raise HTTPException(422, "Unknown evaluation type.")
    if available_metric is not None and available_metric not in ALLOWED_METRICS:
        raise HTTPException(422, "Unknown available metric.")
    if sort not in SORT_FIELDS:
        raise HTTPException(422, "Unknown leaderboard sort.")

    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        runs: list[Any] = store.list_documents("evaluation_runs")
        endpoints = {str(endpoint["id"]): endpoint for endpoint in store.list_documents("model_endpoints")}
        metric_rows: list[Any] = store.list_documents(
            "aggregate_metrics",
            sort=[("run_id", 1), ("metric_name", 1), ("aggregation_version", -1)],
        )
    else:
        assert session is not None
        runs = list(session.scalars(select(EvaluationRun).where(EvaluationRun.archived_at.is_(None))))
        endpoints = {endpoint.id: endpoint for endpoint in session.scalars(select(ModelEndpoint))}
        metric_rows = list(
            session.scalars(
                select(AggregateMetric).order_by(
                    AggregateMetric.run_id,
                    AggregateMetric.metric_name,
                    AggregateMetric.aggregation_version.desc(),
                )
            )
        )

    query = LeaderboardQuery(
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
    try:
        return build_leaderboard(runs, endpoints, _latest_metrics_by_run(metric_rows), query)
    except LeaderboardQueryError as error:
        raise HTTPException(422, str(error)) from error


def _latest_metrics_by_run(rows: list[Any]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(dict)
    for row in rows:
        run_id = str(_value(row, "run_id"))
        metric_name = str(_value(row, "metric_name"))
        grouped[run_id].setdefault(metric_name, row)
    return grouped


def _value(item: Any, field: str) -> Any:
    return item.get(field) if isinstance(item, dict) else getattr(item, field, None)
