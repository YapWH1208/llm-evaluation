from __future__ import annotations

from collections import defaultdict
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import DatasetVersion, EvaluationRun, ModelEndpoint, Report, TaskUnit
from app.services.run_analysis import latest_attempts, summarize_attempts


router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def get_session(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.database.get_session()
    try:
        yield session
    finally:
        session.close()


SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("")
def summary(session: SessionDependency) -> dict[str, Any]:
    def count(model: type, condition: Any = None) -> int:
        query = select(func.count()).select_from(model)
        if condition is not None:
            query = query.where(condition)
        return session.scalar(query) or 0

    runs = list(session.scalars(select(EvaluationRun).order_by(EvaluationRun.created_at.desc())))
    completed_runs = [
        run for run in runs if run.status in {"completed", "completed_with_errors"}
    ]
    current_attempts = [
        attempt for run in completed_runs for attempt in latest_attempts(session, run.id)
    ]
    evidence = summarize_attempts(current_attempts, total_samples=sum(run.total_samples for run in completed_runs))
    costs_by_currency: defaultdict[str, float] = defaultdict(float)
    for run in completed_runs:
        endpoint = session.get(ModelEndpoint, run.model_endpoint_id)
        currency = endpoint.currency if endpoint is not None else "unknown"
        for attempt in latest_attempts(session, run.id):
            if attempt.estimated_cost is not None:
                costs_by_currency[currency] += attempt.estimated_cost

    now = datetime.now(timezone.utc)
    active_workers = {
        task.leased_by
        for task in session.scalars(
            select(TaskUnit).where(TaskUnit.status.in_(["leased", "running"]))
        )
        if task.leased_by and _lease_is_current(task.lease_expires_at, now)
    }
    return {
        "runs": {
            "active": count(EvaluationRun, EvaluationRun.status.in_(["queued", "running", "paused"])),
            "completed": count(
                EvaluationRun,
                EvaluationRun.status.in_(["completed", "completed_with_errors"]),
            ),
            "recent_completed": [
                {
                    "id": run.id,
                    "benchmark_id": run.benchmark_id,
                    "status": run.status,
                    "completed_samples": run.completed_samples,
                    "total_samples": run.total_samples,
                    "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                }
                for run in completed_runs[:5]
            ],
        },
        "queue": {
            "pending": count(TaskUnit, TaskUnit.status.in_(["pending", "retry_scheduled"])),
            "leased": count(TaskUnit, TaskUnit.status.in_(["leased", "running"])),
        },
        "workers": {"active": len(active_workers)},
        "endpoints": {
            "available": count(ModelEndpoint, ModelEndpoint.status == "available"),
            "unavailable": count(ModelEndpoint, ModelEndpoint.status == "unavailable"),
            "total": count(ModelEndpoint),
        },
        "datasets": {
            "ready": count(DatasetVersion, DatasetVersion.status == "ready"),
            "blocked": count(DatasetVersion, DatasetVersion.status.in_(["license_required", "failed"])),
        },
        "quality": evidence,
        "api": {
            "request_error_rate": evidence["errors"]["api_error_rate"],
            "estimated_cost_by_currency": {
                currency: round(cost, 12) for currency, cost in sorted(costs_by_currency.items())
            },
        },
        "reports": count(Report),
    }


def _lease_is_current(expires_at: datetime | None, now: datetime) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        return expires_at >= now.replace(tzinfo=None)
    return expires_at >= now
