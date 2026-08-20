from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Any

from app.modules.benchmarks.metrics import metric_definition, metric_definitions
from app.modules.evaluations.names import resolve_run_display_name


MAX_SCATTER_POINTS = 500


class ScatterQueryError(ValueError):
    """Raised when scatter axes or numeric ranges are invalid."""


@dataclass(frozen=True, slots=True)
class ScatterFilters:
    run_ids: frozenset[str] | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    model_endpoint_id: str | None = None
    dataset: str | None = None
    statuses: frozenset[str] | None = None
    capability: str | None = None
    language: str | None = None
    evaluation_type: str | None = None
    min_score: float | None = None
    max_score: float | None = None
    min_accuracy: float | None = None
    max_accuracy: float | None = None
    min_latency_ms: float | None = None
    max_latency_ms: float | None = None
    min_cost: float | None = None
    max_cost: float | None = None
    max_points: int = field(default=MAX_SCATTER_POINTS)


def build_scatter_response(
    runs: list[Any],
    endpoints_by_id: dict[str, Any],
    metrics_by_run: dict[str, dict[str, Any]],
    *,
    x_axis: str,
    y_axis: str,
    filters: ScatterFilters,
) -> dict[str, object]:
    axes = _axis_registry()
    unknown = [axis for axis in (x_axis, y_axis) if axis not in axes]
    if unknown:
        raise ScatterQueryError(
            "Unknown scatter axis: "
            + ", ".join(unknown)
            + ". Available axes: "
            + ", ".join(sorted(axes))
            + "."
        )
    _validate_filters(filters)

    eligible: list[dict[str, object]] = []
    for run in runs:
        if _value(run, "archived_at") is not None:
            continue
        run_id = str(_value(run, "id"))
        endpoint_id = str(_value(run, "model_endpoint_id"))
        endpoint = endpoints_by_id.get(endpoint_id)
        context = _run_context(run, endpoint)
        run_metrics = metrics_by_run.get(run_id, {})
        if not _matches_filters(run, context, run_metrics, filters):
            continue
        eligible.append({"run": run, "context": context, "metrics": run_metrics})

    eligible.sort(key=_scatter_sort_key)
    points: list[dict[str, object]] = []
    unavailable = {"x": 0, "y": 0, "both": 0}
    unavailable_reasons: dict[tuple[str, str], int] = {}
    total_plottable = 0
    for item in eligible:
        run = item["run"]
        context = item["context"]
        run_metrics = item["metrics"]
        assert isinstance(context, dict) and isinstance(run_metrics, dict)
        x_value, x_reason = _axis_value(run_metrics, x_axis)
        y_value, y_reason = _axis_value(run_metrics, y_axis)
        if x_value is None or y_value is None:
            key = "both" if x_value is None and y_value is None else "x" if x_value is None else "y"
            unavailable[key] += 1
            if x_value is None:
                reason = x_reason or f"{axes[x_axis]['label']} is unavailable."
                unavailable_reasons[("x", reason)] = unavailable_reasons.get(("x", reason), 0) + 1
            if y_value is None:
                reason = y_reason or f"{axes[y_axis]['label']} is unavailable."
                unavailable_reasons[("y", reason)] = unavailable_reasons.get(("y", reason), 0) + 1
            continue
        total_plottable += 1
        if len(points) >= filters.max_points:
            continue
        points.append({
            "run_id": str(_value(run, "id")),
            "display_name": resolve_run_display_name(run),
            "model_endpoint_id": context["model_endpoint_id"],
            "model_name": context["model_name"],
            "dataset": context["dataset"],
            "benchmark_id": str(_value(run, "benchmark_id")),
            "benchmark_version": str(_value(run, "benchmark_version")),
            "status": str(_value(run, "status")),
            "created_at": _datetime(_value(run, "created_at")).isoformat(),
            "capabilities": context["capabilities"],
            "languages": context["languages"],
            "evaluation_type": context["evaluation_type"],
            "x": x_value,
            "y": y_value,
            "x_metric": x_axis,
            "y_metric": y_axis,
            "x_availability_reason": x_reason,
            "y_availability_reason": y_reason,
        })

    selected_run_ids = [str(_value(item["run"], "id")) for item in eligible]
    unavailable_count = sum(unavailable.values())
    return {
        "x_axis": axes[x_axis],
        "y_axis": axes[y_axis],
        "selected_run_ids": selected_run_ids,
        "eligible_run_count": len(eligible),
        "plottable_count": total_plottable,
        "plotted_count": len(points),
        "unavailable_count": unavailable_count,
        "unavailable_by_axis": unavailable,
        "unavailable_reasons": [
            {"axis": axis, "reason": reason, "count": count}
            for (axis, reason), count in sorted(unavailable_reasons.items())
        ],
        "truncated_count": max(0, total_plottable - len(points)),
        "max_points": filters.max_points,
        "points": points,
    }


def _axis_registry() -> dict[str, dict[str, str]]:
    return {
        definition.metric_name: {
            "metric_name": definition.metric_name,
            "label": definition.label,
            "unit": definition.unit,
            "profile": definition.profile,
        }
        for definition in metric_definitions()
    }


def _run_context(run: Any, endpoint: Any) -> dict[str, object]:
    snapshot = _value(run, "configuration_snapshot", {})
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    profile = snapshot.get("dataset_profile")
    profile = profile if isinstance(profile, dict) else {}
    benchmark = snapshot.get("benchmark")
    benchmark = benchmark if isinstance(benchmark, dict) else {}
    manifest = benchmark.get("manifest")
    manifest = manifest if isinstance(manifest, dict) else {}
    capabilities = _string_values(profile.get("capabilities"))
    capabilities.update(_string_values(manifest.get("required_capabilities")))
    capabilities.update(_string_values(manifest.get("recommended_capabilities")))
    languages = _string_values(profile.get("languages"))
    languages.update(_string_values(manifest.get("languages")))
    dataset_version = snapshot.get("dataset_version")
    dataset_version = dataset_version if isinstance(dataset_version, dict) else {}
    dataset = dataset_version.get("dataset_id")
    if not isinstance(dataset, str) or not dataset:
        dataset = str(_value(run, "benchmark_id"))
    model_name = _value(endpoint, "model_name")
    if not isinstance(model_name, str) or not model_name:
        frozen_endpoint = snapshot.get("endpoint")
        model_name = frozen_endpoint.get("model_name") if isinstance(frozen_endpoint, dict) else None
    evaluation_type = profile.get("evaluation_type")
    return {
        "model_endpoint_id": str(_value(run, "model_endpoint_id")),
        "model_name": model_name if isinstance(model_name, str) and model_name else "unknown",
        "dataset": dataset,
        "capabilities": sorted(capabilities),
        "languages": sorted(languages),
        "evaluation_type": evaluation_type if isinstance(evaluation_type, str) else "custom",
    }


def _matches_filters(
    run: Any,
    context: dict[str, object],
    metrics: dict[str, Any],
    filters: ScatterFilters,
) -> bool:
    run_id = str(_value(run, "id"))
    created_at = _datetime(_value(run, "created_at"))
    if filters.run_ids is not None and run_id not in filters.run_ids:
        return False
    if filters.created_from is not None and created_at < _datetime(filters.created_from):
        return False
    if filters.created_to is not None and created_at > _datetime(filters.created_to):
        return False
    if filters.model_endpoint_id is not None and context["model_endpoint_id"] != filters.model_endpoint_id:
        return False
    if filters.dataset is not None and context["dataset"] != filters.dataset:
        return False
    if filters.statuses is not None and str(_value(run, "status")) not in filters.statuses:
        return False
    if filters.capability is not None and filters.capability not in context["capabilities"]:
        return False
    if filters.language is not None and filters.language not in context["languages"]:
        return False
    if filters.evaluation_type is not None and context["evaluation_type"] != filters.evaluation_type:
        return False
    score, _score_reason = _axis_value(metrics, "score")
    accuracy, _accuracy_reason = _axis_value(metrics, "accuracy")
    latency, _latency_reason = _axis_value(metrics, "average_latency_ms")
    cost, _cost_reason = _axis_value(metrics, "estimated_cost")
    if filters.min_score is not None and (score is None or score < filters.min_score):
        return False
    if filters.max_score is not None and (score is None or score > filters.max_score):
        return False
    if filters.min_accuracy is not None and (accuracy is None or accuracy < filters.min_accuracy):
        return False
    if filters.max_accuracy is not None and (accuracy is None or accuracy > filters.max_accuracy):
        return False
    if filters.min_latency_ms is not None and (latency is None or latency < filters.min_latency_ms):
        return False
    if filters.max_latency_ms is not None and (latency is None or latency > filters.max_latency_ms):
        return False
    if filters.min_cost is not None and (cost is None or cost < filters.min_cost):
        return False
    if filters.max_cost is not None and (cost is None or cost > filters.max_cost):
        return False
    return True


def _axis_value(metrics: dict[str, Any], metric_name: str) -> tuple[float | None, str | None]:
    metric = metrics.get(metric_name)
    if metric is None and metric_name == "score":
        metric = metrics.get("accuracy")
    value = _value(metric, "metric_value") if metric is not None else None
    reason = _value(metric, "availability_reason") if metric is not None else None
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None, str(reason) if reason else f"{metric_definition(metric_name).label} is unavailable for this run."
    return float(value), str(reason) if reason else None


def _validate_filters(filters: ScatterFilters) -> None:
    if not 1 <= filters.max_points <= MAX_SCATTER_POINTS:
        raise ScatterQueryError(f"max_points must be between 1 and {MAX_SCATTER_POINTS}.")
    for minimum, maximum, label in (
        (filters.min_score, filters.max_score, "score"),
        (filters.min_accuracy, filters.max_accuracy, "accuracy"),
        (filters.min_latency_ms, filters.max_latency_ms, "latency"),
        (filters.min_cost, filters.max_cost, "cost"),
    ):
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ScatterQueryError(f"Minimum {label} must not exceed maximum {label}.")
        if any(value is not None and not math.isfinite(value) for value in (minimum, maximum)):
            raise ScatterQueryError(f"{label.title()} ranges must contain finite values.")
    if any(
        value is not None and value < 0
        for value in (filters.min_latency_ms, filters.max_latency_ms)
    ):
        raise ScatterQueryError("Latency ranges must not be negative.")
    if any(value is not None and value < 0 for value in (filters.min_cost, filters.max_cost)):
        raise ScatterQueryError("Cost ranges must not be negative.")
    if filters.created_from is not None and filters.created_to is not None:
        if _datetime(filters.created_from) > _datetime(filters.created_to):
            raise ScatterQueryError("created_from must not be after created_to.")


def _scatter_sort_key(item: dict[str, object]) -> tuple[float, str]:
    run = item["run"]
    created_at = _datetime(_value(run, "created_at"))
    return (-created_at.timestamp(), str(_value(run, "id")))


def _string_values(value: object) -> set[str]:
    return {item for item in value if isinstance(item, str)} if isinstance(value, list) else set()


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _value(item: Any, field: str, default: Any = None) -> Any:
    if item is None:
        return default
    return item.get(field, default) if isinstance(item, dict) else getattr(item, field, default)
