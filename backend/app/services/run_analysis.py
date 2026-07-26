from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EvaluationRun, ModelEndpoint, SampleAttempt, SampleAttemptStatus


def latest_attempts(session: Session, run_id: str) -> list[SampleAttempt]:
    """Return the current outcome for each sample while retaining retries elsewhere."""

    attempts = session.scalars(
        select(SampleAttempt)
        .where(SampleAttempt.run_id == run_id)
        .order_by(SampleAttempt.sample_id, SampleAttempt.attempt_number.desc())
    )
    latest_by_sample: dict[str, SampleAttempt] = {}
    for attempt in attempts:
        latest_by_sample.setdefault(attempt.sample_id, attempt)
    return [latest_by_sample[sample_id] for sample_id in sorted(latest_by_sample)]


def all_attempts(session: Session, run_id: str) -> list[SampleAttempt]:
    return list(
        session.scalars(
            select(SampleAttempt)
            .where(SampleAttempt.run_id == run_id)
            .order_by(SampleAttempt.sample_id, SampleAttempt.attempt_number)
        )
    )


def build_run_summary(session: Session, run: EvaluationRun) -> dict[str, Any]:
    endpoint = session.get(ModelEndpoint, run.model_endpoint_id)
    current_attempts = latest_attempts(session, run.id)
    return summarize_attempts(
        current_attempts,
        total_samples=run.total_samples,
        currency=endpoint.currency if endpoint is not None else None,
    )


def summarize_attempts(
    attempts: Iterable[SampleAttempt],
    *,
    total_samples: int | None = None,
    currency: str | None = None,
) -> dict[str, Any]:
    rows = list(attempts)
    terminal = [
        attempt
        for attempt in rows
        if attempt.status
        in {SampleAttemptStatus.SUCCEEDED.value, SampleAttemptStatus.FAILED.value}
    ]
    successful = [
        attempt for attempt in terminal if attempt.status == SampleAttemptStatus.SUCCEEDED.value
    ]
    failed = [attempt for attempt in terminal if attempt.status == SampleAttemptStatus.FAILED.value]
    scored = [attempt.score for attempt in successful if attempt.score is not None]
    latencies = [attempt.latency_ms for attempt in terminal if attempt.latency_ms is not None]
    input_tokens = [attempt.input_tokens for attempt in terminal if attempt.input_tokens is not None]
    output_tokens = [attempt.output_tokens for attempt in terminal if attempt.output_tokens is not None]
    costs = [attempt.estimated_cost for attempt in terminal if attempt.estimated_cost is not None]
    error_types: defaultdict[str, int] = defaultdict(int)
    for attempt in failed:
        error_types[attempt.error_type or "execution_error"] += 1

    api_errors = sum(
        count
        for error_type, count in error_types.items()
        if error_type.startswith("http_") or error_type in {"timeout", "connection_error"}
    )
    parser_errors = error_types.get("response_parse_error", 0)
    expected_total = total_samples if total_samples is not None else len(rows)
    completed = len(terminal)

    return {
        "samples": {
            "total": expected_total,
            "completed": completed,
            "successful": len(successful),
            "failed": len(failed),
            "completion_rate": _ratio(completed, expected_total),
            "success_rate": _ratio(len(successful), completed),
            "accuracy": _average(scored),
        },
        "errors": {
            "total": len(failed),
            "rate": _ratio(len(failed), completed),
            "api_errors": api_errors,
            "api_error_rate": _ratio(api_errors, completed),
            "parser_errors": parser_errors,
            "parser_error_rate": _ratio(parser_errors, completed),
            "by_type": dict(sorted(error_types.items())),
        },
        "latency_ms": {
            "measured_samples": len(latencies),
            "average": _average(latencies),
            "p50": _percentile(latencies, 50),
            "p95": _percentile(latencies, 95),
            "p99": _percentile(latencies, 99),
        },
        "tokens": {
            "measured_samples": len(
                {
                    attempt.id
                    for attempt in terminal
                    if attempt.input_tokens is not None or attempt.output_tokens is not None
                }
            ),
            "input": sum(input_tokens),
            "output": sum(output_tokens),
            "total": sum(input_tokens) + sum(output_tokens),
        },
        "cost": {
            "measured_samples": len(costs),
            "estimated": round(sum(costs), 12) if costs else None,
            "actual": None,
            "currency": currency,
        },
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _average(values: Iterable[float]) -> float | None:
    rows = list(values)
    if not rows:
        return None
    return round(sum(rows) / len(rows), 6)


def _percentile(values: Iterable[float], percentile: int) -> float | None:
    rows = sorted(values)
    if not rows:
        return None
    if len(rows) == 1:
        return round(rows[0], 6)
    position = (len(rows) - 1) * percentile / 100
    lower = int(position)
    upper = min(lower + 1, len(rows) - 1)
    fraction = position - lower
    return round(rows[lower] + (rows[upper] - rows[lower]) * fraction, 6)
