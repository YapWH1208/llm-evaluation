from __future__ import annotations

from datetime import datetime, timezone
from math import sqrt
from types import SimpleNamespace
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import AggregateMetric, EvaluationRun, SampleAttempt, SampleAttemptStatus
from app.db.mongo import MongoDocumentStore
from app.services.run_analysis import latest_attempts, summarize_attempts


AGGREGATION_VERSION = "1.0.0"


class AggregationError(ValueError):
    """Raised when a run cannot be aggregated."""


def recompute_aggregate_metrics(
    session: Session,
    run_id: str,
    *,
    commit: bool = True,
) -> list[AggregateMetric]:
    """Replace a run's versioned metric materialization from immutable attempts."""

    run = session.get(EvaluationRun, run_id)
    if run is None:
        raise AggregationError("Evaluation run not found.")
    attempts = latest_attempts(session, run.id)
    metrics = _metrics_for_attempts(attempts, total_samples=run.total_samples)
    session.execute(
        delete(AggregateMetric).where(
            AggregateMetric.run_id == run.id,
            AggregateMetric.aggregation_version == AGGREGATION_VERSION,
        )
    )
    rows = [
        AggregateMetric(
            run_id=run.id,
            benchmark_id=run.benchmark_id,
            model_endpoint_id=run.model_endpoint_id,
            metric_name=metric_name,
            metric_value=value,
            sample_count=sample_count,
            confidence_interval=confidence_interval,
            aggregation_version=AGGREGATION_VERSION,
        )
        for metric_name, value, sample_count, confidence_interval in metrics
    ]
    session.add_all(rows)
    if commit:
        session.commit()
        for row in rows:
            session.refresh(row)
    else:
        session.flush()
    return rows


def list_aggregate_metrics(session: Session, run_id: str) -> list[AggregateMetric]:
    return list(
        session.scalars(
            select(AggregateMetric)
            .where(AggregateMetric.run_id == run_id)
            .order_by(AggregateMetric.metric_name, AggregateMetric.aggregation_version.desc())
        )
    )


def recompute_mongo_aggregate_metrics(
    store: MongoDocumentStore,
    run_id: str,
) -> list[dict[str, Any]]:
    """Materialize the same aggregate contract for the document-store adapter."""

    run = store.get_document("evaluation_runs", run_id)
    if run is None:
        raise AggregationError("Evaluation run not found.")
    attempts = store.list_documents(
        "sample_attempts", query={"run_id": run_id}, sort=[("sample_id", 1), ("attempt_number", -1)]
    )
    latest: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        latest.setdefault(str(attempt["sample_id"]), attempt)
    metrics = _metrics_for_attempts(list(latest.values()), total_samples=int(run.get("total_samples", len(latest))))
    store.delete_documents(
        "aggregate_metrics",
        {"run_id": run_id, "aggregation_version": AGGREGATION_VERSION},
    )
    return [
        store.insert_document(
            "aggregate_metrics",
            {
                "run_id": run_id,
                "benchmark_id": run["benchmark_id"],
                "model_endpoint_id": run["model_endpoint_id"],
                "metric_name": metric_name,
                "metric_value": value,
                "sample_count": sample_count,
                "confidence_interval": confidence_interval,
                "aggregation_version": AGGREGATION_VERSION,
                "created_at": datetime.now(timezone.utc),
            },
        )
        for metric_name, value, sample_count, confidence_interval in metrics
    ]


def list_mongo_aggregate_metrics(store: MongoDocumentStore, run_id: str) -> list[dict[str, Any]]:
    return store.list_documents(
        "aggregate_metrics", query={"run_id": run_id}, sort=[("metric_name", 1), ("aggregation_version", -1)]
    )


def _metrics_for_attempts(
    attempts: list[Any],
    *,
    total_samples: int,
) -> list[tuple[str, float | None, int, dict[str, object] | None]]:
    summary_attempts = [
        SimpleNamespace(**attempt) if isinstance(attempt, dict) else attempt
        for attempt in attempts
    ]
    summary = summarize_attempts(summary_attempts, total_samples=total_samples)
    terminal = [
        attempt
        for attempt in attempts
        if _value(attempt, "status") in {SampleAttemptStatus.SUCCEEDED.value, SampleAttemptStatus.FAILED.value}
    ]
    successful = [attempt for attempt in terminal if _value(attempt, "status") == SampleAttemptStatus.SUCCEEDED.value]
    scored = [float(score) for attempt in successful if (score := _value(attempt, "score")) is not None]
    latencies = [float(value) for attempt in terminal if (value := _value(attempt, "latency_ms")) is not None]
    input_tokens = [float(value) for attempt in terminal if (value := _value(attempt, "input_tokens")) is not None]
    output_tokens = [float(value) for attempt in terminal if (value := _value(attempt, "output_tokens")) is not None]
    costs = [float(value) for attempt in terminal if (value := _value(attempt, "estimated_cost")) is not None]
    completed = len(terminal)
    failed = len(terminal) - len(successful)

    return [
        ("accuracy", _as_float(summary["samples"]["accuracy"]), len(scored), _mean_confidence_interval(scored)),
        ("completion_rate", _as_float(summary["samples"]["completion_rate"]), total_samples, _binomial_confidence_interval(completed, total_samples)),
        ("success_rate", _as_float(summary["samples"]["success_rate"]), completed, _binomial_confidence_interval(len(successful), completed)),
        ("error_rate", _as_float(summary["errors"]["rate"]), completed, _binomial_confidence_interval(failed, completed)),
        ("average_latency_ms", _as_float(summary["latency_ms"]["average"]), len(latencies), _mean_confidence_interval(latencies)),
        ("p50_latency_ms", _as_float(summary["latency_ms"]["p50"]), len(latencies), None),
        ("p95_latency_ms", _as_float(summary["latency_ms"]["p95"]), len(latencies), None),
        ("p99_latency_ms", _as_float(summary["latency_ms"]["p99"]), len(latencies), None),
        ("input_tokens", _as_float(summary["tokens"]["input"]), len(input_tokens), None),
        ("output_tokens", _as_float(summary["tokens"]["output"]), len(output_tokens), None),
        ("estimated_cost", _as_float(summary["cost"]["estimated"]), len(costs), None),
    ]


def _value(attempt: Any, key: str) -> Any:
    return attempt.get(key) if isinstance(attempt, dict) else getattr(attempt, key)


def _as_float(value: object) -> float | None:
    return round(float(value), 12) if isinstance(value, int | float) else None


def _mean_confidence_interval(values: list[float]) -> dict[str, object] | None:
    if not values:
        return None
    average = sum(values) / len(values)
    if len(values) == 1:
        return {"method": "normal_95", "lower": round(average, 6), "upper": round(average, 6)}
    variance = sum((value - average) ** 2 for value in values) / (len(values) - 1)
    margin = 1.96 * sqrt(variance / len(values))
    return {"method": "normal_95", "lower": round(average - margin, 6), "upper": round(average + margin, 6)}


def _binomial_confidence_interval(successes: int, total: int) -> dict[str, object] | None:
    if total <= 0:
        return None
    z = 1.96
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = z * sqrt((proportion * (1 - proportion) + z * z / (4 * total)) / total) / denominator
    return {"method": "wilson_95", "lower": round(max(0.0, centre - margin), 6), "upper": round(min(1.0, centre + margin), 6)}
