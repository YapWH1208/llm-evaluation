from __future__ import annotations

from collections import defaultdict
from collections.abc import Generator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BenchmarkDefinition, EvaluationRun, ModelEndpoint
from app.services.run_analysis import build_run_summary


router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def get_session(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.database.get_session()
    try:
        yield session
    finally:
        session.close()


SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("/matrix")
def capability_matrix(session: SessionDependency) -> dict[str, Any]:
    """Return a model-by-benchmark heatmap and capability-level aggregate cells."""

    completed_runs = list(
        session.scalars(
            select(EvaluationRun)
            .where(EvaluationRun.status.in_(["completed", "completed_with_errors"]))
            .order_by(EvaluationRun.completed_at.desc())
        )
    )
    heatmap: list[dict[str, Any]] = []
    grouped: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for run in completed_runs:
        endpoint = session.get(ModelEndpoint, run.model_endpoint_id)
        benchmark = session.scalar(
            select(BenchmarkDefinition).where(
                BenchmarkDefinition.benchmark_id == run.benchmark_id,
                BenchmarkDefinition.version == run.benchmark_version,
            )
        )
        required_capabilities = []
        if benchmark is not None and isinstance(benchmark.manifest, dict):
            required_capabilities = [
                key for key in benchmark.manifest.get("required_capabilities", []) if isinstance(key, str)
            ]
        if not required_capabilities:
            required_capabilities = ["custom"]
        summary = build_run_summary(session, run)
        cell = {
            "run_id": run.id,
            "model_endpoint_id": run.model_endpoint_id,
            "model_name": endpoint.model_name if endpoint is not None else "unknown",
            "benchmark_id": run.benchmark_id,
            "benchmark_version": run.benchmark_version,
            "accuracy": summary["samples"]["accuracy"],
            "success_rate": summary["samples"]["success_rate"],
            "error_rate": summary["errors"]["rate"],
            "average_latency_ms": summary["latency_ms"]["average"],
            "estimated_cost": summary["cost"]["estimated"],
            "currency": summary["cost"]["currency"],
            "required_capabilities": required_capabilities,
        }
        heatmap.append(cell)
        for capability in required_capabilities:
            grouped[(run.model_endpoint_id, capability)].append(cell)

    capability_cells = [
        {
            "model_endpoint_id": endpoint_id,
            "capability": capability,
            "run_count": len(cells),
            "accuracy": _mean([cell["accuracy"] for cell in cells]),
            "success_rate": _mean([cell["success_rate"] for cell in cells]),
            "error_rate": _mean([cell["error_rate"] for cell in cells]),
            "average_latency_ms": _mean([cell["average_latency_ms"] for cell in cells]),
            "estimated_cost": _sum_or_none([cell["estimated_cost"] for cell in cells]),
        }
        for (endpoint_id, capability), cells in sorted(grouped.items())
    ]
    return {"heatmap": heatmap, "capability_matrix": capability_cells}


def _mean(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return round(sum(present) / len(present), 6) if present else None


def _sum_or_none(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return round(sum(present), 12) if present else None
