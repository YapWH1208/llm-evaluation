from __future__ import annotations

from typing import Any

from app.core.errors import ConflictError, NotFoundError
from app.modules.analytics.comparison_evidence import build_comparison_extension
from app.modules.evaluations.analysis import build_repository_run_summary
from app.modules.evaluations.ports import EvaluationRepository


class ComparisonService:
    """Run comparison behavior independent of persistence backend."""

    def __init__(self, repository: EvaluationRepository) -> None:
        self._repository = repository

    def compare(self, run_a: str, run_b: str) -> dict[str, Any]:
        if run_a == run_b:
            raise ConflictError("Comparison requires two distinct evaluation runs")
        first = self._repository.get_run(run_a)
        second = self._repository.get_run(run_b)
        if first is None or second is None:
            raise NotFoundError("One or both evaluation runs were not found")
        if (first["benchmark_id"], first["benchmark_version"]) != (
            second["benchmark_id"],
            second["benchmark_version"],
        ):
            raise ConflictError("Runs must use the same benchmark version")
        attempts_a = _latest_attempts(self._repository.list_attempts(run_a))
        attempts_b = _latest_attempts(self._repository.list_attempts(run_b))
        shared_ids = sorted(set(attempts_a) & set(attempts_b))
        outcome_counts = {
            "both_correct": 0,
            "run_a_only_correct": 0,
            "run_b_only_correct": 0,
            "both_incorrect": 0,
        }
        outcomes: list[dict[str, Any]] = []
        for sample_id in shared_ids:
            first_attempt = attempts_a[sample_id]
            second_attempt = attempts_b[sample_id]
            if _is_correct(first_attempt) and _is_correct(second_attempt):
                outcome = "both_correct"
            elif _is_correct(first_attempt):
                outcome = "run_a_only_correct"
            elif _is_correct(second_attempt):
                outcome = "run_b_only_correct"
            else:
                outcome = "both_incorrect"
            outcome_counts[outcome] += 1
            outcomes.append(
                {
                    "sample_id": sample_id,
                    "outcome": outcome,
                    "run_a": _attempt_evidence(first_attempt),
                    "run_b": _attempt_evidence(second_attempt),
                }
            )
        summary_a = build_repository_run_summary(self._repository, run_a)
        summary_b = build_repository_run_summary(self._repository, run_b)
        endpoint_a = self._repository.get_endpoint(str(first["model_endpoint_id"]))
        endpoint_b = self._repository.get_endpoint(str(second["model_endpoint_id"]))
        extension = build_comparison_extension(
            first,
            second,
            endpoint_a,
            endpoint_b,
            self._repository.list_metrics(run_a),
            self._repository.list_metrics(run_b),
            outcome_counts,
        )
        return {
            "run_a": run_a,
            "run_b": run_b,
            "benchmark": {"id": first["benchmark_id"], "version": first["benchmark_version"]},
            "shared_samples": len(shared_ids),
            "outcomes": outcome_counts,
            "run_a_summary": summary_a,
            "run_b_summary": summary_b,
            "differences": {
                "accuracy": _difference(summary_a["samples"]["accuracy"], summary_b["samples"]["accuracy"]),
                "success_rate": _difference(summary_a["samples"]["success_rate"], summary_b["samples"]["success_rate"]),
                "error_rate": _difference(summary_a["errors"]["rate"], summary_b["errors"]["rate"]),
                "average_latency_ms": _difference(
                    summary_a["latency_ms"]["average"], summary_b["latency_ms"]["average"]
                ),
                "p95_latency_ms": _difference(summary_a["latency_ms"]["p95"], summary_b["latency_ms"]["p95"]),
                "estimated_cost": _difference(summary_a["cost"]["estimated"], summary_b["cost"]["estimated"]),
                "output_tokens": summary_a["tokens"]["output"] - summary_b["tokens"]["output"],
            },
            "sample_outcomes": outcomes,
            **extension,
        }


def _latest_attempts(attempts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        latest[str(attempt["sample_id"])] = attempt
    return latest


def _is_correct(attempt: dict[str, Any]) -> bool:
    return attempt.get("status") == "succeeded" and attempt.get("score") == 1


def _attempt_evidence(attempt: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": attempt.get("status"),
        "score": attempt.get("score"),
        "prediction": attempt.get("parsed_prediction"),
        "latency_ms": attempt.get("latency_ms"),
        "input_tokens": attempt.get("input_tokens"),
        "output_tokens": attempt.get("output_tokens"),
        "estimated_cost": attempt.get("estimated_cost"),
        "error_type": attempt.get("error_type"),
    }


def _difference(first: float | None, second: float | None) -> float | None:
    if first is None or second is None:
        return None
    return round(first - second, 12)
