from __future__ import annotations

from datetime import datetime, timezone
import re
import unicodedata
from typing import Any


MAX_RUN_DISPLAY_NAME_LENGTH = 500
MAX_RUN_NAME_COMPONENT_LENGTH = 200
_UNSAFE_COMPONENT = re.compile(r"[^A-Za-z0-9-]+")
_REPEATED_DASH = re.compile(r"-+")


def format_run_display_name(
    model_name: str,
    dataset_or_benchmark_name: str,
    created_at: datetime,
) -> str:
    """Build the immutable, URL-safe display label for one run snapshot."""

    model = _safe_component(model_name, fallback="model")
    source = _safe_component(dataset_or_benchmark_name, fallback="evaluation")
    timestamp = _as_utc(created_at).strftime("%Y%m%dT%H%M%SZ")
    return f"{model}_{source}_{timestamp}"[:MAX_RUN_DISPLAY_NAME_LENGTH]


def resolve_run_display_name(run: Any) -> str:
    """Return a persisted name or a deterministic fallback for one legacy run."""

    persisted = _value(run, "display_name")
    if isinstance(persisted, str) and persisted.strip():
        return persisted.strip()
    snapshot = _value(run, "configuration_snapshot")
    frozen = snapshot if isinstance(snapshot, dict) else {}
    endpoint = frozen.get("endpoint") if isinstance(frozen.get("endpoint"), dict) else {}
    model_name = endpoint.get("model_name") if isinstance(endpoint.get("model_name"), str) else "model"
    source_name = _frozen_source_name(frozen, _value(run, "benchmark_id"))
    created_at = _value(run, "created_at")
    if not isinstance(created_at, datetime):
        created_at = _parse_datetime(created_at)
    return format_run_display_name(model_name, source_name, created_at)


def _safe_component(value: str, *, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip()).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.replace("_", "-")
    normalized = _UNSAFE_COMPONENT.sub("-", normalized)
    normalized = _REPEATED_DASH.sub("-", normalized).strip("-")
    return (normalized or fallback)[:MAX_RUN_NAME_COMPONENT_LENGTH].rstrip("-") or fallback


def _frozen_source_name(snapshot: dict[str, Any], benchmark_id: object) -> str:
    dataset_version = snapshot.get("dataset_version")
    if isinstance(dataset_version, dict) and isinstance(dataset_version.get("dataset_id"), str):
        return dataset_version["dataset_id"]
    datasets = snapshot.get("datasets")
    if isinstance(datasets, list):
        for dataset in datasets:
            if isinstance(dataset, dict) and isinstance(dataset.get("dataset_id"), str):
                return dataset["dataset_id"]
    benchmark = snapshot.get("benchmark")
    if isinstance(benchmark, dict):
        if isinstance(benchmark.get("id"), str):
            return benchmark["id"]
        manifest = benchmark.get("manifest")
        if isinstance(manifest, dict) and isinstance(manifest.get("display_name"), str):
            return manifest["display_name"]
    return str(benchmark_id) if benchmark_id else "evaluation"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _value(item: Any, key: str) -> Any:
    return item.get(key) if isinstance(item, dict) else getattr(item, key, None)
