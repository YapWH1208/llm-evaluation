from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.services.metric_profiles import metric_definition
from app.services.run_names import resolve_run_display_name


_OUTCOME_ORDER = (
    "both_correct",
    "run_a_only_correct",
    "run_b_only_correct",
    "both_incorrect",
)


def build_comparison_extension(
    run_a: Any,
    run_b: Any,
    endpoint_a: Any,
    endpoint_b: Any,
    metrics_a: list[Any],
    metrics_b: list[Any],
    outcomes: dict[str, int],
) -> dict[str, object]:
    named_metrics = _named_metric_rows(metrics_a, metrics_b)
    grouped: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for metric in named_metrics:
        grouped[str(metric["unit"])].append(metric)
    return {
        "runs": {
            "a": _run_descriptor(run_a, endpoint_a),
            "b": _run_descriptor(run_b, endpoint_b),
        },
        "named_metrics": named_metrics,
        "metric_groups": [
            {"unit": unit, "metrics": rows}
            for unit, rows in sorted(grouped.items())
        ],
        "outcome_distribution": [
            {"outcome": outcome, "count": int(outcomes.get(outcome, 0))}
            for outcome in _OUTCOME_ORDER
        ],
    }


def _run_descriptor(run: Any, endpoint: Any) -> dict[str, object]:
    created_at = _value(run, "created_at")
    if isinstance(created_at, datetime):
        created_at_value = (
            created_at.replace(tzinfo=timezone.utc)
            if created_at.tzinfo is None
            else created_at.astimezone(timezone.utc)
        ).isoformat()
    else:
        created_at_value = str(created_at) if created_at is not None else None
    model_name = _value(endpoint, "model_name")
    if not isinstance(model_name, str) or not model_name:
        snapshot = _value(run, "configuration_snapshot", {})
        frozen_endpoint = snapshot.get("endpoint") if isinstance(snapshot, dict) else None
        model_name = frozen_endpoint.get("model_name") if isinstance(frozen_endpoint, dict) else None
    return {
        "id": str(_value(run, "id")),
        "display_name": resolve_run_display_name(run),
        "model_endpoint_id": str(_value(run, "model_endpoint_id")),
        "model_name": model_name if isinstance(model_name, str) and model_name else "unknown",
        "status": str(_value(run, "status")),
        "created_at": created_at_value,
    }


def _named_metric_rows(metrics_a: list[Any], metrics_b: list[Any]) -> list[dict[str, object]]:
    by_name_a = {str(_value(metric, "metric_name")): metric for metric in metrics_a}
    by_name_b = {str(_value(metric, "metric_name")): metric for metric in metrics_b}
    rows: list[dict[str, object]] = []
    for metric_name in sorted(set(by_name_a) | set(by_name_b)):
        first = by_name_a.get(metric_name)
        second = by_name_b.get(metric_name)
        try:
            definition = metric_definition(metric_name)
            label = definition.label
            unit = definition.unit
            profile = definition.profile
        except ValueError:
            label = metric_name.replace("_", " ").title()
            unit = "value"
            profile = "custom"
        first_payload = _metric_side(first)
        second_payload = _metric_side(second)
        rows.append({
            "metric_name": metric_name,
            "label": label,
            "unit": unit,
            "profile": profile,
            "run_a": first_payload,
            "run_b": second_payload,
            "delta": _difference(first_payload["value"], second_payload["value"]),
        })
    return rows


def _metric_side(metric: Any | None) -> dict[str, object]:
    if metric is None:
        return {
            "value": None,
            "availability_reason": "Metric was not materialized for this run.",
            "sample_count": 0,
        }
    value = _value(metric, "metric_value")
    reason = _value(metric, "availability_reason")
    return {
        "value": float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None,
        "availability_reason": str(reason) if reason else None,
        "sample_count": int(_value(metric, "sample_count", 0) or 0),
    }


def _difference(first: object, second: object) -> float | None:
    if not isinstance(first, int | float) or isinstance(first, bool):
        return None
    if not isinstance(second, int | float) or isinstance(second, bool):
        return None
    return round(float(first) - float(second), 12)


def _value(item: Any, field: str, default: Any = None) -> Any:
    if item is None:
        return default
    return item.get(field, default) if isinstance(item, dict) else getattr(item, field, default)
