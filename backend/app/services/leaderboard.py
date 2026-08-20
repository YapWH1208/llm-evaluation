from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import cmp_to_key
import math
from typing import Any

from app.services.metric_profiles import metric_definition, metric_definitions
from app.modules.evaluations.names import resolve_run_display_name


MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 50
COMPLETED_STATUSES = frozenset({"completed", "completed_with_errors"})
SORT_FIELDS = frozenset({
    "default",
    "name",
    "model",
    "dataset",
    "status",
    "created_at",
    "score",
    "average_latency_ms",
    "p95_latency_ms",
    "estimated_cost",
    "sample_count",
    *(definition.metric_name for definition in metric_definitions()),
})
NUMERIC_SORT_FIELDS = frozenset({
    "score",
    "average_latency_ms",
    "p95_latency_ms",
    "estimated_cost",
    *(definition.metric_name for definition in metric_definitions()),
})


class LeaderboardQueryError(ValueError):
    """Raised when leaderboard filter, ordering, or pagination input is invalid."""


@dataclass(frozen=True, slots=True)
class LeaderboardFilters:
    dataset: str | None = None
    model_endpoint_id: str | None = None
    statuses: frozenset[str] | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    capability: str | None = None
    language: str | None = None
    evaluation_type: str | None = None
    available_metric: str | None = None


@dataclass(frozen=True, slots=True)
class LeaderboardQuery:
    filters: LeaderboardFilters = field(default_factory=LeaderboardFilters)
    sort: str = "default"
    direction: str = "desc"
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


def build_leaderboard(
    runs: list[Any],
    endpoints_by_id: dict[str, Any],
    metrics_by_run: dict[str, dict[str, Any]],
    query: LeaderboardQuery,
) -> dict[str, object]:
    """Build a bounded leaderboard response without exposing run evidence or credentials."""

    _validate_query(query)
    rows: list[dict[str, Any]] = []
    for run in runs:
        if _value(run, "archived_at") is not None:
            continue
        run_id = str(_value(run, "id"))
        endpoint = endpoints_by_id.get(str(_value(run, "model_endpoint_id")))
        row = _leaderboard_row(run, endpoint, metrics_by_run.get(run_id, {}))
        if _matches_filters(row, query.filters):
            rows.append(row)

    if query.sort == "default":
        rows.sort(key=cmp_to_key(_compare_default))
    else:
        rows.sort(key=cmp_to_key(lambda left, right: _compare_explicit(
            left, right, field=query.sort, direction=query.direction,
        )))

    total = len(rows)
    total_pages = math.ceil(total / query.page_size) if total else 0
    offset = (query.page - 1) * query.page_size
    return {
        "items": rows[offset:offset + query.page_size],
        "total": total,
        "page": query.page,
        "page_size": query.page_size,
        "total_pages": total_pages,
        "sort": query.sort,
        "direction": query.direction,
    }


def _leaderboard_row(
    run: Any,
    endpoint: Any,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    context = _run_context(run, endpoint)
    named_metrics = {
        name: _metric_payload(name, metric)
        for name, metric in sorted(metrics.items())
    }
    score = _metric_value(metrics, "score")
    primary_metric = "score"
    if score is None and _metric_value(metrics, "accuracy") is not None:
        score = _metric_value(metrics, "accuracy")
        primary_metric = "accuracy"
    created_at = _datetime(_value(run, "created_at"))
    completed_at = _optional_datetime(_value(run, "completed_at"))
    return {
        "run_id": str(_value(run, "id")),
        "display_name": resolve_run_display_name(run),
        "model_endpoint_id": context["model_endpoint_id"],
        "model_name": context["model_name"],
        "dataset": context["dataset"],
        "benchmark_id": str(_value(run, "benchmark_id")),
        "benchmark_version": str(_value(run, "benchmark_version")),
        "status": str(_value(run, "status")),
        "created_at": created_at.isoformat(),
        "completed_at": completed_at.isoformat() if completed_at is not None else None,
        "capabilities": context["capabilities"],
        "languages": context["languages"],
        "evaluation_type": context["evaluation_type"],
        "score": score,
        "primary_metric": primary_metric,
        "average_latency_ms": _metric_value(metrics, "average_latency_ms"),
        "p95_latency_ms": _metric_value(metrics, "p95_latency_ms"),
        "estimated_cost": _metric_value(metrics, "estimated_cost"),
        "sample_count": int(_value(run, "total_samples", 0) or 0),
        "completed_samples": int(_value(run, "completed_samples", 0) or 0),
        "successful_samples": int(_value(run, "successful_samples", 0) or 0),
        "failed_samples": int(_value(run, "failed_samples", 0) or 0),
        "available_metrics": sorted(
            name for name in metrics if _metric_value(metrics, name) is not None
        ),
        "named_metrics": named_metrics,
    }


def _run_context(run: Any, endpoint: Any) -> dict[str, object]:
    snapshot = _value(run, "configuration_snapshot", {})
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    profile = snapshot.get("dataset_profile")
    profile = profile if isinstance(profile, dict) else {}
    dataset_version = snapshot.get("dataset_version")
    dataset_version = dataset_version if isinstance(dataset_version, dict) else {}
    benchmark = snapshot.get("benchmark")
    benchmark = benchmark if isinstance(benchmark, dict) else {}
    manifest = benchmark.get("manifest")
    manifest = manifest if isinstance(manifest, dict) else {}
    capabilities = _string_values(profile.get("capabilities"))
    capabilities.update(_string_values(manifest.get("required_capabilities")))
    capabilities.update(_string_values(manifest.get("recommended_capabilities")))
    languages = _string_values(profile.get("languages"))
    languages.update(_string_values(manifest.get("languages")))
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


def _matches_filters(row: dict[str, Any], filters: LeaderboardFilters) -> bool:
    created_at = _datetime(row["created_at"])
    if filters.dataset is not None and row["dataset"] != filters.dataset:
        return False
    if filters.model_endpoint_id is not None and row["model_endpoint_id"] != filters.model_endpoint_id:
        return False
    if filters.statuses is not None and row["status"] not in filters.statuses:
        return False
    if filters.created_from is not None and created_at < _datetime(filters.created_from):
        return False
    if filters.created_to is not None and created_at > _datetime(filters.created_to):
        return False
    if filters.capability is not None and filters.capability not in row["capabilities"]:
        return False
    if filters.language is not None and filters.language not in row["languages"]:
        return False
    if filters.evaluation_type is not None and row["evaluation_type"] != filters.evaluation_type:
        return False
    if filters.available_metric is not None and filters.available_metric not in row["available_metrics"]:
        return False
    return True


def _compare_default(left: dict[str, Any], right: dict[str, Any]) -> int:
    left_ranked = left["status"] in COMPLETED_STATUSES and left["score"] is not None
    right_ranked = right["status"] in COMPLETED_STATUSES and right["score"] is not None
    if left_ranked != right_ranked:
        return -1 if left_ranked else 1
    if left_ranked:
        for field, direction in (
            ("score", "desc"),
            ("p95_latency_ms", "asc"),
            ("estimated_cost", "asc"),
            ("created_at", "desc"),
        ):
            comparison = _compare_values(left[field], right[field], direction=direction)
            if comparison:
                return comparison
    else:
        left_completed = left["status"] in COMPLETED_STATUSES
        right_completed = right["status"] in COMPLETED_STATUSES
        if left_completed != right_completed:
            return -1 if left_completed else 1
        comparison = _compare_values(left["created_at"], right["created_at"], direction="desc")
        if comparison:
            return comparison
    return _compare_values(left["run_id"], right["run_id"], direction="asc")


def _compare_explicit(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    field: str,
    direction: str,
) -> int:
    row_fields = {
        "name": "display_name",
        "model": "model_name",
        "dataset": "dataset",
        "status": "status",
        "created_at": "created_at",
        "sample_count": "sample_count",
        "score": "score",
        "average_latency_ms": "average_latency_ms",
        "p95_latency_ms": "p95_latency_ms",
        "estimated_cost": "estimated_cost",
    }
    if field in row_fields:
        left_value = left[row_fields[field]]
        right_value = right[row_fields[field]]
    else:
        left_value = left["named_metrics"].get(field, {}).get("value")
        right_value = right["named_metrics"].get(field, {}).get("value")
    comparison = _compare_values(left_value, right_value, direction=direction)
    return comparison or _compare_values(left["run_id"], right["run_id"], direction="asc")


def _compare_values(left: Any, right: Any, *, direction: str) -> int:
    if left is None or right is None:
        if left is None and right is None:
            return 0
        return 1 if left is None else -1
    normalized_left = left.casefold() if isinstance(left, str) else left
    normalized_right = right.casefold() if isinstance(right, str) else right
    if normalized_left == normalized_right:
        return 0
    result = -1 if normalized_left < normalized_right else 1
    return result if direction == "asc" else -result


def _metric_payload(name: str, metric: Any) -> dict[str, Any]:
    try:
        definition = metric_definition(name)
        label = definition.label
        unit = definition.unit
    except ValueError:
        label = name.replace("_", " ").title()
        unit = "value"
    return {
        "metric_name": name,
        "label": label,
        "unit": unit,
        "value": _finite_float(_value(metric, "metric_value")),
        "sample_count": int(_value(metric, "sample_count", 0) or 0),
        "availability_reason": _value(metric, "availability_reason"),
    }


def _metric_value(metrics: dict[str, Any], name: str) -> float | None:
    metric = metrics.get(name)
    return _finite_float(_value(metric, "metric_value")) if metric is not None else None


def _validate_query(query: LeaderboardQuery) -> None:
    if query.sort not in SORT_FIELDS:
        raise LeaderboardQueryError(
            f"Unknown leaderboard sort: {query.sort}. Available sorts: {', '.join(sorted(SORT_FIELDS))}."
        )
    if query.direction not in {"asc", "desc"}:
        raise LeaderboardQueryError("direction must be either asc or desc.")
    if query.page < 1:
        raise LeaderboardQueryError("page must be at least 1.")
    if not 1 <= query.page_size <= MAX_PAGE_SIZE:
        raise LeaderboardQueryError(f"page_size must be between 1 and {MAX_PAGE_SIZE}.")
    if query.filters.created_from is not None and query.filters.created_to is not None:
        if _datetime(query.filters.created_from) > _datetime(query.filters.created_to):
            raise LeaderboardQueryError("created_from must not be after created_to.")


def _finite_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    converted = float(value)
    return converted if math.isfinite(converted) else None


def _string_values(value: object) -> set[str]:
    return {item for item in value if isinstance(item, str)} if isinstance(value, list) else set()


def _optional_datetime(value: object) -> datetime | None:
    return _datetime(value) if value is not None else None


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
