from __future__ import annotations

from datetime import datetime, timezone
from math import sqrt
from types import SimpleNamespace
from typing import Any

from app.core.errors import NotFoundError
from app.db.models import SampleAttemptStatus
from app.modules.benchmarks.metrics import (
    MetricResult,
    compute_profile_metrics,
    evaluation_type_from_snapshot,
)
from app.modules.reviews.scoring import is_llm_judge_rule, is_valid_judge_score
from app.modules.evaluations.analysis import summarize_attempts
from app.modules.evaluations.ports import EvaluationRepository


AGGREGATION_VERSION = "2.0.0"


class AggregationService:
    """Compute metric materializations once and persist through an evaluation repository."""

    def __init__(self, repository: EvaluationRepository) -> None:
        self._repository = repository

    def list(self, run_id: str) -> list[dict[str, Any]]:
        self._require_run(run_id)
        return self._repository.list_metrics(run_id)

    def recompute(self, run_id: str) -> list[dict[str, Any]]:
        run = self._require_run(run_id)
        attempts_by_sample: dict[str, dict[str, Any]] = {}
        for attempt in self._repository.list_attempts(run_id):
            attempts_by_sample[str(attempt["sample_id"])] = attempt
        attempts = list(attempts_by_sample.values())
        metrics = _metrics_for_attempts(
            attempts,
            total_samples=int(run.get("total_samples", len(attempts))),
            evaluation_type=evaluation_type_from_snapshot(run.get("configuration_snapshot")),
            include_llm_judge=_run_uses_llm_judge(run.get("configuration_snapshot")),
        )
        now = datetime.now(timezone.utc)
        return self._repository.replace_metrics(
            run_id,
            [
                {
                    "run_id": run_id,
                    "benchmark_id": run["benchmark_id"],
                    "model_endpoint_id": run["model_endpoint_id"],
                    "metric_name": metric.metric_name,
                    "metric_value": metric.value,
                    "availability_reason": metric.availability_reason,
                    "sample_count": metric.sample_count,
                    "confidence_interval": metric.confidence_interval,
                    "aggregation_version": AGGREGATION_VERSION,
                    "created_at": now,
                }
                for metric in metrics
            ],
        )

    def _require_run(self, run_id: str) -> dict[str, Any]:
        run = self._repository.get_run(run_id)
        if run is None:
            raise NotFoundError("Evaluation run not found.", context={"run_id": run_id})
        return run


def _metrics_for_attempts(
    attempts: list[Any],
    *,
    total_samples: int,
    evaluation_type: str,
    include_llm_judge: bool = False,
) -> list[MetricResult]:
    summary_attempts = [SimpleNamespace(**attempt) if isinstance(attempt, dict) else attempt for attempt in attempts]
    summary = summarize_attempts(summary_attempts, total_samples=total_samples)
    terminal = [
        attempt
        for attempt in attempts
        if _value(attempt, "status") in {SampleAttemptStatus.SUCCEEDED.value, SampleAttemptStatus.FAILED.value}
    ]
    successful = [attempt for attempt in terminal if _value(attempt, "status") == SampleAttemptStatus.SUCCEEDED.value]
    scored = [float(score) for attempt in successful if (score := _value(attempt, "score")) is not None]
    judge_scores = [
        float(score)
        for attempt in successful
        if isinstance(evidence := _value(attempt, "metric_evidence"), dict)
        and isinstance(judge := evidence.get("llm_judge"), dict)
        and judge.get("status") == "succeeded"
        and is_valid_judge_score(score := judge.get("score"))
    ]
    latencies = [float(value) for attempt in terminal if (value := _value(attempt, "latency_ms")) is not None]
    input_tokens = [float(value) for attempt in terminal if (value := _value(attempt, "input_tokens")) is not None]
    output_tokens = [float(value) for attempt in terminal if (value := _value(attempt, "output_tokens")) is not None]
    costs = [float(value) for attempt in terminal if (value := _value(attempt, "estimated_cost")) is not None]
    completed = len(terminal)
    failed = len(terminal) - len(successful)

    profile_metrics = compute_profile_metrics(
        attempts,
        evaluation_type=evaluation_type,
        include_llm_judge=include_llm_judge,
    )
    profile_names = {metric.metric_name for metric in profile_metrics}
    score_interval = _mean_confidence_interval(scored)
    judge_interval = _mean_confidence_interval(judge_scores)
    profile_metrics = [
        MetricResult(
            metric.metric_name,
            metric.value,
            metric.sample_count,
            metric.availability_reason,
            _profile_confidence_interval(
                metric,
                evaluation_type=evaluation_type,
                score_interval=score_interval,
                judge_interval=judge_interval,
            ),
        )
        for metric in profile_metrics
    ]
    if "accuracy" not in profile_names:
        profile_metrics.append(
            MetricResult(
                "accuracy",
                _as_float(summary["samples"]["accuracy"]),
                len(scored),
                None if scored else "No successful samples contain a compatibility score.",
                score_interval,
            )
        )
    return profile_metrics + [
        MetricResult(
            "completion_rate",
            _as_float(summary["samples"]["completion_rate"]),
            total_samples,
            None,
            _binomial_confidence_interval(completed, total_samples),
        ),
        MetricResult(
            "success_rate",
            _as_float(summary["samples"]["success_rate"]),
            completed,
            None,
            _binomial_confidence_interval(len(successful), completed),
        ),
        MetricResult(
            "error_rate",
            _as_float(summary["errors"]["rate"]),
            completed,
            None,
            _binomial_confidence_interval(failed, completed),
        ),
        MetricResult(
            "average_latency_ms",
            _as_float(summary["latency_ms"]["average"]),
            len(latencies),
            None,
            _mean_confidence_interval(latencies),
        ),
        MetricResult("p50_latency_ms", _as_float(summary["latency_ms"]["p50"]), len(latencies)),
        MetricResult("p95_latency_ms", _as_float(summary["latency_ms"]["p95"]), len(latencies)),
        MetricResult("p99_latency_ms", _as_float(summary["latency_ms"]["p99"]), len(latencies)),
        MetricResult("input_tokens", _as_float(summary["tokens"]["input"]), len(input_tokens)),
        MetricResult("output_tokens", _as_float(summary["tokens"]["output"]), len(output_tokens)),
        MetricResult("estimated_cost", _as_float(summary["cost"]["estimated"]), len(costs)),
    ]


def _run_uses_llm_judge(snapshot: object) -> bool:
    return isinstance(snapshot, dict) and is_llm_judge_rule(snapshot.get("scoring_rule"))


def _profile_confidence_interval(
    metric: MetricResult,
    *,
    evaluation_type: str,
    score_interval: dict[str, object] | None,
    judge_interval: dict[str, object] | None,
) -> dict[str, object] | None:
    if metric.value is None:
        return metric.confidence_interval
    if metric.metric_name == "llm_judge":
        return judge_interval
    if metric.metric_name == "score" or (metric.metric_name == "accuracy" and evaluation_type != "classification"):
        return score_interval
    return metric.confidence_interval


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
    return {
        "method": "wilson_95",
        "lower": round(max(0.0, centre - margin), 6),
        "upper": round(min(1.0, centre + margin), 6),
    }
