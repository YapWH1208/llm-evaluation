from __future__ import annotations

from collections import defaultdict
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import DatasetVersion, EvaluationRun, ModelEndpoint, Report, TaskUnit
from app.db.mongo import MongoDocumentStore
from app.services.run_analysis import latest_attempts, summarize_attempts


router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


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
        runs=store.list_documents("evaluation_runs",sort=[("created_at",-1)]); tasks=store.list_documents("task_units"); endpoints=store.list_documents("model_endpoints"); datasets=store.list_documents("dataset_versions"); reports=store.list_documents("reports")
        completed=[run for run in runs if run["status"] in {"completed","completed_with_errors"}]; active_workers={task.get("leased_by") for task in tasks if task.get("status") in {"leased","running"} and task.get("leased_by")}
        costs: defaultdict[str,float]=defaultdict(float); attempts=[]
        for run in completed:
            current={}
            for item in store.list_documents("sample_attempts",query={"run_id":run["id"]},sort=[("sample_id",1),("attempt_number",-1)]):current.setdefault(item["sample_id"],item)
            attempts.extend(type("Attempt",(),item)() for item in current.values())
            endpoint=next((item for item in endpoints if item["id"]==run["model_endpoint_id"]),None)
            for item in current.values():
                if item.get("estimated_cost") is not None:costs[str(endpoint.get("currency","unknown") if endpoint else "unknown")]+=float(item["estimated_cost"])
        evidence=summarize_attempts(attempts,total_samples=sum(int(run["total_samples"]) for run in completed))
        return {"runs":{"active":sum(run["status"] in {"queued","running","paused"} for run in runs),"completed":len(completed),"recent_completed":[{"id":run["id"],"benchmark_id":run["benchmark_id"],"status":run["status"],"completed_samples":run["completed_samples"],"total_samples":run["total_samples"],"completed_at":run.get("completed_at").isoformat() if run.get("completed_at") else None} for run in completed[:5]]},"queue":{"pending":sum(task["status"] in {"pending","retry_scheduled"} for task in tasks),"leased":sum(task["status"] in {"leased","running"} for task in tasks)},"workers":{"active":len(active_workers)},"endpoints":{"available":sum(item["status"]=="available" for item in endpoints),"unavailable":sum(item["status"]=="unavailable" for item in endpoints),"total":len(endpoints)},"datasets":{"ready":sum(item["status"]=="ready" for item in datasets),"blocked":sum(item["status"] in {"license_required","failed"} for item in datasets)},"quality":evidence,"api":{"request_error_rate":evidence["errors"]["api_error_rate"],"estimated_cost_by_currency":{key:round(value,12) for key,value in sorted(costs.items())}},"reports":len(reports)}
    assert session is not None
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
