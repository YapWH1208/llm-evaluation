from __future__ import annotations

from collections import defaultdict
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import DatasetVersion, EvaluationRun, ModelEndpoint, Report, SampleAttempt, TaskUnit
from app.db.mongo import MongoDocumentStore
from app.modules.evaluations.analysis import summarize_attempts
from app.modules.evaluations.names import resolve_run_display_name


router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
DASHBOARD_RUN_LIMIT = 50
DASHBOARD_ATTEMPT_LIMIT = 5_000


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
def summary(request: Request, session: SessionDependency) -> dict[str, Any]:
    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        runs = store.list_documents("evaluation_runs", sort=[("created_at", -1)], limit=DASHBOARD_RUN_LIMIT)
        completed = [run for run in runs if run["status"] in {"completed", "completed_with_errors"}]
        run_ids = [str(run["id"]) for run in completed]
        rows = store.list_documents(
            "sample_attempts",
            query={"run_id": {"$in": run_ids}},
            sort=[("run_id", 1), ("sample_id", 1), ("attempt_number", -1)],
            limit=DASHBOARD_ATTEMPT_LIMIT,
        ) if run_ids else []
        current: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            current.setdefault((str(row["run_id"]), str(row["sample_id"])), row)
        endpoint_ids = [str(run["model_endpoint_id"]) for run in completed]
        endpoints = {
            str(endpoint["id"]): endpoint
            for endpoint in store.list_documents("model_endpoints", query={"id": {"$in": endpoint_ids}})
        } if endpoint_ids else {}
        run_endpoint_ids = {str(run["id"]): str(run["model_endpoint_id"]) for run in completed}
        attempts = [type("Attempt", (), row)() for row in current.values()]
        costs: defaultdict[str, float] = defaultdict(float)
        for row in current.values():
            if row.get("estimated_cost") is not None:
                endpoint = endpoints.get(run_endpoint_ids.get(str(row["run_id"]), ""))
                costs[str(endpoint.get("currency", "unknown") if endpoint else "unknown")] += float(row["estimated_cost"])
        evidence = summarize_attempts(attempts, total_samples=sum(int(run["total_samples"]) for run in completed))
        return {
            "runs": {"active": store.count_documents("evaluation_runs", {"status": {"$in": ["queued", "running", "paused"]}}), "completed": store.count_documents("evaluation_runs", {"status": {"$in": ["completed", "completed_with_errors"]}}), "recent_completed": [_run_summary(run) for run in completed[:5]]},
            "queue": {"pending": store.count_documents("task_units", {"status": {"$in": ["pending", "retry_scheduled"]}}), "leased": store.count_documents("task_units", {"status": {"$in": ["leased", "running"]}})},
            "workers": {"active": len(store.distinct_values("task_units", "leased_by", {"status": {"$in": ["leased", "running"]}}))},
            "endpoints": {"available": store.count_documents("model_endpoints", {"status": "available"}), "unavailable": store.count_documents("model_endpoints", {"status": "unavailable"}), "total": store.count_documents("model_endpoints")},
            "datasets": {"ready": store.count_documents("dataset_versions", {"status": "ready"}), "blocked": store.count_documents("dataset_versions", {"status": {"$in": ["license_required", "failed"]}})},
            "quality": evidence,
            "api": {"request_error_rate": evidence["errors"]["api_error_rate"], "estimated_cost_by_currency": {key: round(value, 12) for key, value in sorted(costs.items())}},
            "reports": store.count_documents("reports"),
        }
    assert session is not None
    def count(model: type, condition: Any = None) -> int:
        query = select(func.count()).select_from(model)
        if condition is not None:
            query = query.where(condition)
        return session.scalar(query) or 0

    runs = list(session.scalars(select(EvaluationRun).order_by(EvaluationRun.created_at.desc()).limit(DASHBOARD_RUN_LIMIT)))
    completed_runs = [
        run for run in runs if run.status in {"completed", "completed_with_errors"}
    ]
    run_ids = [run.id for run in completed_runs]
    rows = session.scalars(
        select(SampleAttempt)
        .where(SampleAttempt.run_id.in_(run_ids))
        .order_by(SampleAttempt.run_id, SampleAttempt.sample_id, SampleAttempt.attempt_number.desc())
        .limit(DASHBOARD_ATTEMPT_LIMIT)
    ) if run_ids else []
    current_by_sample: dict[tuple[str, str], SampleAttempt] = {}
    for attempt in rows:
        current_by_sample.setdefault((attempt.run_id, attempt.sample_id), attempt)
    current_attempts = list(current_by_sample.values())
    evidence = summarize_attempts(current_attempts, total_samples=sum(run.total_samples for run in completed_runs))
    costs_by_currency: defaultdict[str, float] = defaultdict(float)
    endpoint_map = {
        endpoint.id: endpoint
        for endpoint in session.scalars(select(ModelEndpoint).where(ModelEndpoint.id.in_([run.model_endpoint_id for run in completed_runs])))
    } if completed_runs else {}
    run_endpoint_ids = {run.id: run.model_endpoint_id for run in completed_runs}
    for attempt in current_attempts:
        if attempt.estimated_cost is not None:
            endpoint = endpoint_map.get(run_endpoint_ids.get(attempt.run_id, ""))
            costs_by_currency[endpoint.currency if endpoint is not None else "unknown"] += attempt.estimated_cost

    now = datetime.now(timezone.utc)
    active_workers = {
        task.leased_by
        for task in session.scalars(
            select(TaskUnit).where(TaskUnit.status.in_(["leased", "running"])).limit(500)
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
                _run_summary(run)
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


def _run_summary(run: Any) -> dict[str, Any]:
    completed_at = getattr(run, "completed_at", None) if not isinstance(run, dict) else run.get("completed_at")
    return {
        "id": run["id"] if isinstance(run, dict) else run.id,
        "display_name": resolve_run_display_name(run),
        "benchmark_id": run["benchmark_id"] if isinstance(run, dict) else run.benchmark_id,
        "status": run["status"] if isinstance(run, dict) else run.status,
        "completed_samples": run["completed_samples"] if isinstance(run, dict) else run.completed_samples,
        "total_samples": run["total_samples"] if isinstance(run, dict) else run.total_samples,
        "completed_at": completed_at.isoformat() if completed_at else None,
    }
