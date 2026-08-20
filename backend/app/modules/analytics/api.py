from __future__ import annotations

from collections import defaultdict
import math
from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AggregateMetric, BenchmarkDefinition, EvaluationRun, ModelEndpoint
from app.db.mongo import MongoDocumentStore
from app.modules.analytics.aggregation import (
    AggregationError,
    list_aggregate_metrics,
    list_mongo_aggregate_metrics,
    recompute_aggregate_metrics,
    recompute_mongo_aggregate_metrics,
)
from app.modules.benchmarks.metrics import METRIC_PROFILE_VERSION, metric_definition
from app.modules.analytics.scatter import (
    ScatterFilters,
    ScatterQueryError,
    build_scatter_response,
)
from app.modules.datasets.metadata import EVALUATION_TYPES


router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def get_session(request: Request) -> Generator[Session | None, None, None]:
    if getattr(request.app.state,"document_store",None) is not None:
        yield None;return
    session = request.app.state.database.get_session()
    try:
        yield session
    finally:
        session.close()


SessionDependency = Annotated[Session | None, Depends(get_session)]


class AggregateMetricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    benchmark_id: str
    model_endpoint_id: str
    metric_name: str
    metric_value: float | None
    availability_reason: str | None = None
    sample_count: int
    confidence_interval: dict[str, object] | None
    aggregation_version: str
    created_at: datetime
    metric_label: str = ""
    unit: str = ""
    profile: str = ""
    required_evidence: list[str] = Field(default_factory=list)
    profile_version: str = METRIC_PROFILE_VERSION

    @model_validator(mode="after")
    def add_metric_definition(self) -> "AggregateMetricResponse":
        try:
            definition = metric_definition(self.metric_name)
        except ValueError:
            self.metric_label = self.metric_name.replace("_", " ").title()
            self.unit = "value"
            self.profile = "custom"
            self.required_evidence = []
            return self
        self.metric_label = definition.label
        self.unit = definition.unit
        self.profile = definition.profile
        self.required_evidence = list(definition.required_evidence)
        return self


@router.get("/runs/{run_id}/metrics", response_model=list[AggregateMetricResponse])
def run_aggregate_metrics(
    run_id: str,
    request: Request,
    session: SessionDependency,
) -> list[AggregateMetric | dict[str, Any]]:
    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        if store.get_document("evaluation_runs", run_id) is None:
            raise HTTPException(404, "Evaluation run not found")
        return list_mongo_aggregate_metrics(store, run_id)
    assert session is not None
    if session.get(EvaluationRun, run_id) is None:
        raise HTTPException(404, "Evaluation run not found")
    return list_aggregate_metrics(session, run_id)


@router.post("/runs/{run_id}/metrics/recompute", response_model=list[AggregateMetricResponse])
def recompute_run_aggregate_metrics(
    run_id: str,
    request: Request,
    session: SessionDependency,
) -> list[AggregateMetric | dict[str, Any]]:
    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    try:
        if store is not None:
            return recompute_mongo_aggregate_metrics(store, run_id)
        assert session is not None
        return recompute_aggregate_metrics(session, run_id)
    except AggregationError as error:
        raise HTTPException(404, str(error)) from error


@router.get("/scatter")
def evidence_scatter(
    request: Request,
    session: SessionDependency,
    x_axis: str = Query(default="score", min_length=1, max_length=128),
    y_axis: str = Query(default="average_latency_ms", min_length=1, max_length=128),
    run_ids: list[str] | None = Query(default=None),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    model_endpoint_id: str | None = Query(default=None, max_length=128),
    dataset: str | None = Query(default=None, max_length=128),
    statuses: list[str] | None = Query(default=None, alias="status"),
    capability: str | None = Query(default=None, max_length=64),
    language: str | None = Query(default=None, max_length=64),
    evaluation_type: str | None = Query(default=None, max_length=32),
    min_score: float | None = None,
    max_score: float | None = None,
    min_accuracy: float | None = None,
    max_accuracy: float | None = None,
    min_latency_ms: float | None = None,
    max_latency_ms: float | None = None,
    min_cost: float | None = None,
    max_cost: float | None = None,
    max_points: int = Query(default=500, ge=1, le=500),
) -> dict[str, object]:
    """Return a bounded, deterministic run-level scatter representation."""

    if run_ids is not None and len(run_ids) > 1_000:
        raise HTTPException(422, "At most 1,000 run IDs may be selected.")
    allowed_statuses = {
        "waiting_for_dataset", "queued", "running", "pausing", "paused",
        "cancelling", "cancelled", "completed", "completed_with_errors", "failed",
        "scoring", "aggregating", "generating_report",
    }
    unknown_statuses = sorted(set(statuses or ()) - allowed_statuses)
    if unknown_statuses:
        raise HTTPException(422, f"Unknown run status: {', '.join(unknown_statuses)}.")
    if evaluation_type is not None and evaluation_type not in EVALUATION_TYPES:
        raise HTTPException(422, "Unknown evaluation type.")

    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        runs: list[Any] = store.list_documents("evaluation_runs")
        endpoints = {
            str(endpoint["id"]): endpoint
            for endpoint in store.list_documents("model_endpoints")
        }
        metric_rows: list[Any] = store.list_documents(
            "aggregate_metrics",
            sort=[("run_id", 1), ("metric_name", 1), ("aggregation_version", -1)],
        )
    else:
        assert session is not None
        runs = list(session.scalars(select(EvaluationRun)))
        endpoints = {
            endpoint.id: endpoint
            for endpoint in session.scalars(select(ModelEndpoint))
        }
        metric_rows = list(session.scalars(
            select(AggregateMetric).order_by(
                AggregateMetric.run_id,
                AggregateMetric.metric_name,
                AggregateMetric.aggregation_version.desc(),
            )
        ))
    metrics_by_run = _latest_metrics_by_run(metric_rows)
    filters = ScatterFilters(
        run_ids=frozenset(run_ids) if run_ids is not None else None,
        created_from=date_from,
        created_to=date_to,
        model_endpoint_id=model_endpoint_id,
        dataset=dataset,
        statuses=frozenset(statuses) if statuses is not None else None,
        capability=capability,
        language=language,
        evaluation_type=evaluation_type,
        min_score=min_score,
        max_score=max_score,
        min_accuracy=min_accuracy,
        max_accuracy=max_accuracy,
        min_latency_ms=min_latency_ms,
        max_latency_ms=max_latency_ms,
        min_cost=min_cost,
        max_cost=max_cost,
        max_points=max_points,
    )
    try:
        return build_scatter_response(
            runs,
            endpoints,
            metrics_by_run,
            x_axis=x_axis,
            y_axis=y_axis,
            filters=filters,
        )
    except ScatterQueryError as error:
        raise HTTPException(422, str(error)) from error


def _latest_metrics_by_run(rows: list[Any]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(dict)
    for row in rows:
        run_id = str(_value(row, "run_id"))
        metric_name = str(_value(row, "metric_name"))
        grouped[run_id].setdefault(metric_name, row)
    return grouped


@router.get("/matrix")
def capability_matrix(
    request: Request,
    session: SessionDependency,
    baseline_run_id: str | None = None,
) -> dict[str, Any]:
    """Return auditable model, capability, metadata, and prompt comparison cells.

    Each cell includes the sample count, confidence interval, and (when selected)
    a direct baseline delta.  Older runs that predate sample metadata remain visible
    under the ``unknown`` dimension instead of being silently discarded.
    """

    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        runs = [item for item in store.list_documents("evaluation_runs", sort=[("completed_at", -1)]) if item.get("status") in {"completed", "completed_with_errors"}]
        records: list[dict[str, Any]] = []
        for run in runs:
            endpoint = store.get_document("model_endpoints", str(run["model_endpoint_id"]))
            definitions = store.list_documents("benchmark_definitions", query={"benchmark_id": run["benchmark_id"], "version": run["benchmark_version"]})
            manifest = definitions[0].get("manifest", {}) if definitions else {}
            records.append(_matrix_record(run, endpoint, manifest, _latest_mongo_attempts(store, str(run["id"]))))
        return _matrix_response(records, baseline_run_id)

    assert session is not None
    runs = list(session.scalars(select(EvaluationRun).where(EvaluationRun.status.in_(["completed", "completed_with_errors"])).order_by(EvaluationRun.completed_at.desc())))
    records = []
    for run in runs:
        endpoint = session.get(ModelEndpoint, run.model_endpoint_id)
        definition = session.scalar(select(BenchmarkDefinition).where(BenchmarkDefinition.benchmark_id == run.benchmark_id, BenchmarkDefinition.version == run.benchmark_version))
        records.append(_matrix_record(run, endpoint, definition.manifest if definition is not None else {}, _latest_sqlite_attempts(session, run)))
    return _matrix_response(records, baseline_run_id)


def _latest_sqlite_attempts(session: Session, run: EvaluationRun) -> list[Any]:
    from app.modules.evaluations.analysis import latest_attempts

    return latest_attempts(session, run.id)


def _latest_mongo_attempts(store: MongoDocumentStore, run_id: str) -> list[dict[str, Any]]:
    current: dict[str, dict[str, Any]] = {}
    for attempt in store.list_documents("sample_attempts", query={"run_id": run_id}, sort=[("sample_id", 1), ("attempt_number", -1)]):
        current.setdefault(str(attempt["sample_id"]), attempt)
    return list(current.values())


def _matrix_record(run: Any, endpoint: Any, manifest: object, attempts: list[Any]) -> dict[str, Any]:
    snapshot = _value(run, "configuration_snapshot", {})
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    prompt = snapshot.get("prompt_package")
    prompt_label = "Default prompt"
    if isinstance(prompt, dict):
        prompt_label = f"{prompt.get('name', 'Prompt')} v{prompt.get('version', '?')}"
    manifest = manifest if isinstance(manifest, dict) else {}
    required = [item for item in manifest.get("required_capabilities", []) if isinstance(item, str)] or ["custom"]
    return {
        "run_id": str(_value(run, "id")),
        "model_endpoint_id": str(_value(run, "model_endpoint_id")),
        "model_name": str(_value(endpoint, "model_name", "unknown")),
        "benchmark_id": str(_value(run, "benchmark_id")),
        "benchmark_version": str(_value(run, "benchmark_version")),
        "prompt_label": prompt_label,
        "currency": _value(endpoint, "currency"),
        "required_capabilities": required,
        "attempts": attempts,
    }


def _matrix_response(records: list[dict[str, Any]], baseline_run_id: str | None) -> dict[str, Any]:
    legacy_heatmap: list[dict[str, Any]] = []
    for record in records:
        metrics = _attempt_metrics(record["attempts"])
        legacy_heatmap.append({
            "run_id": record["run_id"], "model_endpoint_id": record["model_endpoint_id"], "model_name": record["model_name"],
            "benchmark_id": record["benchmark_id"], "benchmark_version": record["benchmark_version"],
            "accuracy": metrics["score"], "success_rate": metrics["success_rate"], "error_rate": metrics["error_rate"],
            "average_latency_ms": metrics["average_latency_ms"], "estimated_cost": metrics["estimated_cost"], "currency": record["currency"],
            "required_capabilities": record["required_capabilities"], "sample_count": metrics["sample_count"], "confidence_interval": metrics["confidence_interval"],
        })
    dimensions = {
        "model_benchmark": _dimension_cells(records, "model_benchmark", baseline_run_id),
        "model_capability": _dimension_cells(records, "model_capability", baseline_run_id),
        "model_language": _dimension_cells(records, "model_language", baseline_run_id),
        "model_difficulty": _dimension_cells(records, "model_difficulty", baseline_run_id),
        "prompt_benchmark": _dimension_cells(records, "prompt_benchmark", baseline_run_id),
        "model_modality": _dimension_cells(records, "model_modality", baseline_run_id),
    }
    declared_capabilities = {capability for record in records for capability in record["required_capabilities"]}
    capability_matrix = [
        {
            "model_endpoint_id": cell["x_key"], "capability": cell["y_key"], "run_count": len(cell["run_ids"]),
            "accuracy": cell["score"], "success_rate": cell["success_rate"], "error_rate": cell["error_rate"],
            "average_latency_ms": cell["average_latency_ms"], "estimated_cost": cell["estimated_cost"],
            "sample_count": cell["sample_count"], "confidence_interval": cell["confidence_interval"],
            "baseline_score": cell["baseline_score"], "delta": cell["delta"],
        }
        for cell in dimensions["model_capability"]
        if cell["y_key"] in declared_capabilities
    ]
    return {"baseline_run_id": baseline_run_id, "heatmap": legacy_heatmap, "capability_matrix": capability_matrix, "heatmaps": dimensions}


def _dimension_cells(records: list[dict[str, Any]], dimension: str, baseline_run_id: str | None) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        for y_key, attempts in _dimension_buckets(record, dimension):
            x_key = record["prompt_label"] if dimension == "prompt_benchmark" else record["model_endpoint_id"]
            x_label = record["prompt_label"] if dimension == "prompt_benchmark" else record["model_name"]
            key = (x_key, y_key)
            group = grouped.setdefault(key, {"x_key": x_key, "x_label": x_label, "y_key": y_key, "y_label": y_key, "attempts": [], "by_run": {}, "currencies": set()})
            group["attempts"].extend(attempts)
            group["by_run"].setdefault(record["run_id"], []).extend(attempts)
            if record["currency"]:
                group["currencies"].add(record["currency"])
    cells = []
    for group in grouped.values():
        metrics = _attempt_metrics(group["attempts"])
        baseline_attempts = group["by_run"].get(baseline_run_id, []) if baseline_run_id else []
        baseline_metrics = _attempt_metrics(baseline_attempts)
        baseline_score = baseline_metrics["score"] if baseline_attempts else None
        cells.append({
            "x_key": group["x_key"], "x_label": group["x_label"], "y_key": group["y_key"], "y_label": group["y_label"],
            "run_ids": sorted(group["by_run"]), "score": metrics["score"], "sample_count": metrics["sample_count"],
            "confidence_interval": metrics["confidence_interval"], "success_rate": metrics["success_rate"], "error_rate": metrics["error_rate"],
            "average_latency_ms": metrics["average_latency_ms"], "estimated_cost": metrics["estimated_cost"],
            "currency": next(iter(group["currencies"])) if len(group["currencies"]) == 1 else None,
            "baseline_score": baseline_score, "delta": _difference(metrics["score"], baseline_score),
        })
    return sorted(cells, key=lambda item: (item["y_label"], item["x_label"]))


def _dimension_buckets(record: dict[str, Any], dimension: str) -> list[tuple[str, list[Any]]]:
    attempts = record["attempts"]
    if dimension == "model_benchmark":
        return [(f"{record['benchmark_id']} v{record['benchmark_version']}", attempts)]
    if dimension == "prompt_benchmark":
        return [(f"{record['benchmark_id']} v{record['benchmark_version']}", attempts)]
    buckets: defaultdict[str, list[Any]] = defaultdict(list)
    for attempt in attempts:
        snapshot = _value(attempt, "input_snapshot", {})
        snapshot = snapshot if isinstance(snapshot, dict) else {}
        metadata = snapshot.get("metadata") if isinstance(snapshot.get("metadata"), dict) else {}
        if dimension == "model_capability":
            keys = {str(metadata.get("capability") or "custom"), *record["required_capabilities"]}
            for key in keys:
                buckets[key].append(attempt)
            continue
        elif dimension == "model_modality":
            key = str(snapshot.get("modality") or "unknown")
        elif dimension == "model_language":
            key = str(metadata.get("language") or "unknown")
        else:
            key = str(metadata.get("difficulty") or "unknown")
        buckets[key].append(attempt)
    return list(buckets.items())


def _attempt_metrics(attempts: list[Any]) -> dict[str, Any]:
    terminal = [item for item in attempts if _value(item, "status") in {"succeeded", "failed"}]
    scores = [float(value) for item in terminal if (value := _value(item, "score")) is not None]
    latencies = [float(value) for item in terminal if (value := _value(item, "latency_ms")) is not None]
    costs = [float(value) for item in terminal if (value := _value(item, "estimated_cost")) is not None]
    successful = sum(_value(item, "status") == "succeeded" for item in terminal)
    failed = sum(_value(item, "status") == "failed" for item in terminal)
    score = round(sum(scores) / len(scores), 6) if scores else None
    return {
        "score": score, "sample_count": len(scores), "confidence_interval": _confidence_interval(scores),
        "success_rate": _ratio(successful, len(terminal)), "error_rate": _ratio(failed, len(terminal)),
        "average_latency_ms": round(sum(latencies) / len(latencies), 6) if latencies else None,
        "estimated_cost": round(sum(costs), 12) if costs else None,
    }


def _confidence_interval(scores: list[float]) -> dict[str, object] | None:
    if not scores:
        return None
    average = sum(scores) / len(scores)
    margin = 1.96 * math.sqrt(max(0.0, average * (1 - average)) / len(scores))
    return {"method": "normal_95", "lower": round(max(0.0, average - margin), 6), "upper": round(min(1.0, average + margin), 6)}


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _difference(value: float | None, baseline: float | None) -> float | None:
    return round(value - baseline, 6) if value is not None and baseline is not None else None


def _value(item: Any, field: str, default: Any = None) -> Any:
    return item.get(field, default) if isinstance(item, dict) else getattr(item, field, default)
