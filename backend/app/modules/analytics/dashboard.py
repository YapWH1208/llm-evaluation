from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from app.modules.datasets.service import DatasetService
from app.modules.endpoints.service import EndpointService
from app.modules.evaluations.analysis import summarize_attempts
from app.modules.evaluations.names import resolve_run_display_name
from app.modules.evaluations.ports import EvaluationRepository
from app.modules.reports.service import ReportService


DASHBOARD_RUN_LIMIT = 50
DASHBOARD_ATTEMPT_LIMIT = 5_000


class DashboardService:
    """Compose the workspace summary from feature-owned application services."""

    def __init__(
        self,
        evaluations: EvaluationRepository,
        endpoints: EndpointService,
        datasets: DatasetService,
        reports: ReportService,
    ) -> None:
        self._evaluations = evaluations
        self._endpoints = endpoints
        self._datasets = datasets
        self._reports = reports

    def summary(self) -> dict[str, Any]:
        all_runs = self._evaluations.list_runs(include_archived=True)
        recent_runs = all_runs[:DASHBOARD_RUN_LIMIT]
        completed_runs = [run for run in recent_runs if run["status"] in {"completed", "completed_with_errors"}]
        attempts = self._current_attempts(completed_runs)
        evidence = summarize_attempts(
            [SimpleNamespace(**attempt) for attempt in attempts],
            total_samples=sum(int(run["total_samples"]) for run in completed_runs),
        )

        endpoint_rows = self._endpoints.list()
        endpoint_map = {str(_value(endpoint, "id")): endpoint for endpoint in endpoint_rows}
        run_endpoint_ids = {str(run["id"]): str(run["model_endpoint_id"]) for run in completed_runs}
        costs_by_currency: defaultdict[str, float] = defaultdict(float)
        for attempt in attempts:
            if attempt.get("estimated_cost") is None:
                continue
            endpoint = endpoint_map.get(run_endpoint_ids.get(str(attempt["run_id"]), ""))
            costs_by_currency[str(_value(endpoint, "currency", "unknown"))] += float(attempt["estimated_cost"])

        tasks = [task for run in all_runs for task in self._evaluations.list_tasks(str(run["id"]))]
        now = datetime.now(timezone.utc)
        active_workers = {
            str(task["leased_by"])
            for task in tasks
            if task.get("status") in {"leased", "running"}
            and task.get("leased_by")
            and _lease_is_current(task.get("lease_expires_at"), now)
        }
        datasets = self._datasets.list()
        return {
            "runs": {
                "active": sum(run["status"] in {"queued", "running", "paused"} for run in all_runs),
                "completed": sum(run["status"] in {"completed", "completed_with_errors"} for run in all_runs),
                "recent_completed": [_run_summary(run) for run in completed_runs[:5]],
            },
            "queue": {
                "pending": sum(task.get("status") in {"pending", "retry_scheduled"} for task in tasks),
                "leased": sum(task.get("status") in {"leased", "running"} for task in tasks),
            },
            "workers": {"active": len(active_workers)},
            "endpoints": {
                "available": sum(_value(endpoint, "status") == "available" for endpoint in endpoint_rows),
                "unavailable": sum(_value(endpoint, "status") == "unavailable" for endpoint in endpoint_rows),
                "total": len(endpoint_rows),
            },
            "datasets": {
                "ready": sum(dataset.get("status") == "ready" for dataset in datasets),
                "blocked": sum(dataset.get("status") in {"license_required", "failed"} for dataset in datasets),
            },
            "quality": evidence,
            "api": {
                "request_error_rate": evidence["errors"]["api_error_rate"],
                "estimated_cost_by_currency": {
                    currency: round(cost, 12) for currency, cost in sorted(costs_by_currency.items())
                },
            },
            "reports": sum(len(self._reports.list_for_run(str(run["id"]))) for run in all_runs),
        }

    def _current_attempts(self, runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        current: dict[tuple[str, str], dict[str, Any]] = {}
        for run in runs:
            run_id = str(run["id"])
            for attempt in self._evaluations.list_attempts(run_id):
                current[(run_id, str(attempt["sample_id"]))] = attempt
        return list(current.values())[:DASHBOARD_ATTEMPT_LIMIT]


def _lease_is_current(expires_at: datetime | None, now: datetime) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        return expires_at >= now.replace(tzinfo=None)
    return expires_at >= now


def _run_summary(run: dict[str, Any]) -> dict[str, Any]:
    completed_at = run.get("completed_at")
    return {
        "id": run["id"],
        "display_name": resolve_run_display_name(run),
        "benchmark_id": run["benchmark_id"],
        "status": run["status"],
        "completed_samples": run["completed_samples"],
        "total_samples": run["total_samples"],
        "completed_at": completed_at.isoformat() if completed_at else None,
    }


def _value(item: Any, field: str, default: Any = None) -> Any:
    if item is None:
        return default
    return item.get(field, default) if isinstance(item, dict) else getattr(item, field, default)
