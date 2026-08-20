from __future__ import annotations

from collections import defaultdict
import math
from typing import Any

from app.modules.evaluations.ports import EvaluationRepository


class MatrixService:
    """Build comparison heatmaps from repository-neutral run evidence."""

    def __init__(self, repository: EvaluationRepository) -> None:
        self._repository = repository

    def build(self, baseline_run_id: str | None = None) -> dict[str, Any]:
        runs = [
            run
            for run in self._repository.list_runs(include_archived=True)
            if run.get("status") in {"completed", "completed_with_errors"}
        ]
        records = []
        for run in runs:
            endpoint = self._repository.get_endpoint(str(run["model_endpoint_id"]))
            definition = self._repository.get_benchmark_definition(
                str(run["benchmark_id"]), str(run["benchmark_version"])
            )
            manifest = definition.get("manifest", {}) if definition is not None else {}
            records.append(
                _matrix_record(
                    run, endpoint, manifest, _latest_attempts(self._repository.list_attempts(str(run["id"])))
                )
            )
        return _matrix_response(records, baseline_run_id)


def _latest_attempts(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        current[str(attempt["sample_id"])] = attempt
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
        legacy_heatmap.append(
            {
                "run_id": record["run_id"],
                "model_endpoint_id": record["model_endpoint_id"],
                "model_name": record["model_name"],
                "benchmark_id": record["benchmark_id"],
                "benchmark_version": record["benchmark_version"],
                "accuracy": metrics["score"],
                "success_rate": metrics["success_rate"],
                "error_rate": metrics["error_rate"],
                "average_latency_ms": metrics["average_latency_ms"],
                "estimated_cost": metrics["estimated_cost"],
                "currency": record["currency"],
                "required_capabilities": record["required_capabilities"],
                "sample_count": metrics["sample_count"],
                "confidence_interval": metrics["confidence_interval"],
            }
        )
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
            "model_endpoint_id": cell["x_key"],
            "capability": cell["y_key"],
            "run_count": len(cell["run_ids"]),
            "accuracy": cell["score"],
            "success_rate": cell["success_rate"],
            "error_rate": cell["error_rate"],
            "average_latency_ms": cell["average_latency_ms"],
            "estimated_cost": cell["estimated_cost"],
            "sample_count": cell["sample_count"],
            "confidence_interval": cell["confidence_interval"],
            "baseline_score": cell["baseline_score"],
            "delta": cell["delta"],
        }
        for cell in dimensions["model_capability"]
        if cell["y_key"] in declared_capabilities
    ]
    return {
        "baseline_run_id": baseline_run_id,
        "heatmap": legacy_heatmap,
        "capability_matrix": capability_matrix,
        "heatmaps": dimensions,
    }


def _dimension_cells(
    records: list[dict[str, Any]], dimension: str, baseline_run_id: str | None
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        for y_key, attempts in _dimension_buckets(record, dimension):
            x_key = record["prompt_label"] if dimension == "prompt_benchmark" else record["model_endpoint_id"]
            x_label = record["prompt_label"] if dimension == "prompt_benchmark" else record["model_name"]
            key = (x_key, y_key)
            group = grouped.setdefault(
                key,
                {
                    "x_key": x_key,
                    "x_label": x_label,
                    "y_key": y_key,
                    "y_label": y_key,
                    "attempts": [],
                    "by_run": {},
                    "currencies": set(),
                },
            )
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
        cells.append(
            {
                "x_key": group["x_key"],
                "x_label": group["x_label"],
                "y_key": group["y_key"],
                "y_label": group["y_label"],
                "run_ids": sorted(group["by_run"]),
                "score": metrics["score"],
                "sample_count": metrics["sample_count"],
                "confidence_interval": metrics["confidence_interval"],
                "success_rate": metrics["success_rate"],
                "error_rate": metrics["error_rate"],
                "average_latency_ms": metrics["average_latency_ms"],
                "estimated_cost": metrics["estimated_cost"],
                "currency": next(iter(group["currencies"])) if len(group["currencies"]) == 1 else None,
                "baseline_score": baseline_score,
                "delta": _difference(metrics["score"], baseline_score),
            }
        )
    return sorted(cells, key=lambda item: (item["y_label"], item["x_label"]))


def _dimension_buckets(record: dict[str, Any], dimension: str) -> list[tuple[str, list[Any]]]:
    attempts = record["attempts"]
    if dimension in {"model_benchmark", "prompt_benchmark"}:
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
        if dimension == "model_modality":
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
        "score": score,
        "sample_count": len(scores),
        "confidence_interval": _confidence_interval(scores),
        "success_rate": _ratio(successful, len(terminal)),
        "error_rate": _ratio(failed, len(terminal)),
        "average_latency_ms": round(sum(latencies) / len(latencies), 6) if latencies else None,
        "estimated_cost": round(sum(costs), 12) if costs else None,
    }


def _confidence_interval(scores: list[float]) -> dict[str, object] | None:
    if not scores:
        return None
    average = sum(scores) / len(scores)
    margin = 1.96 * math.sqrt(max(0.0, average * (1 - average)) / len(scores))
    return {
        "method": "normal_95",
        "lower": round(max(0.0, average - margin), 6),
        "upper": round(min(1.0, average + margin), 6),
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _difference(value: float | None, baseline: float | None) -> float | None:
    return round(value - baseline, 6) if value is not None and baseline is not None else None


def _value(item: Any, field: str, default: Any = None) -> Any:
    return item.get(field, default) if isinstance(item, dict) else getattr(item, field, default)
