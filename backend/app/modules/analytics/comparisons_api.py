from __future__ import annotations

from collections.abc import Generator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.models import EvaluationRun, ModelEndpoint, SampleAttempt
from app.db.mongo import MongoDocumentStore
from app.modules.evaluations.analysis import build_repository_run_summary, latest_attempts, summarize_attempts
from app.infrastructure.persistence.mongo.evaluations import MongoEvaluationRepository
from app.modules.analytics.aggregation import list_aggregate_metrics, list_mongo_aggregate_metrics
from app.modules.analytics.comparison_evidence import build_comparison_extension


router = APIRouter(prefix="/api/v1/comparisons", tags=["comparisons"])


def get_session(request: Request) -> Generator[Session | None, None, None]:
    if getattr(request.app.state, "document_store", None) is not None:
        yield None
        return
    session = request.app.state.database.get_session()
    try:
        yield session
    finally:
        session.close()


@router.get("")
def compare(
    run_a: str,
    run_b: str,
    request: Request,
    session: Session | None = Depends(get_session),
) -> dict[str, Any]:
    if run_a == run_b:
        raise HTTPException(409, "Comparison requires two distinct evaluation runs")
    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        return _compare_documents(store, run_a, run_b)
    assert session is not None
    first = session.get(EvaluationRun, run_a)
    second = session.get(EvaluationRun, run_b)
    if first is None or second is None:
        raise HTTPException(404, "One or both evaluation runs were not found")
    if (first.benchmark_id, first.benchmark_version) != (
        second.benchmark_id,
        second.benchmark_version,
    ):
        raise HTTPException(409, "Runs must use the same benchmark version")

    endpoint_a = session.get(ModelEndpoint, first.model_endpoint_id)
    endpoint_b = session.get(ModelEndpoint, second.model_endpoint_id)
    attempts_a = {attempt.sample_id: attempt for attempt in latest_attempts(session, run_a)}
    attempts_b = {attempt.sample_id: attempt for attempt in latest_attempts(session, run_b)}
    shared_ids = sorted(set(attempts_a) & set(attempts_b))

    both_correct = run_a_only_correct = run_b_only_correct = both_incorrect = 0
    outcomes: list[dict[str, Any]] = []
    for sample_id in shared_ids:
        first_attempt = attempts_a[sample_id]
        second_attempt = attempts_b[sample_id]
        first_correct = _is_correct(first_attempt)
        second_correct = _is_correct(second_attempt)
        if first_correct and second_correct:
            both_correct += 1
            outcome = "both_correct"
        elif first_correct:
            run_a_only_correct += 1
            outcome = "run_a_only_correct"
        elif second_correct:
            run_b_only_correct += 1
            outcome = "run_b_only_correct"
        else:
            both_incorrect += 1
            outcome = "both_incorrect"
        outcomes.append(
            {
                "sample_id": sample_id,
                "outcome": outcome,
                "run_a": _attempt_evidence(first_attempt),
                "run_b": _attempt_evidence(second_attempt),
            }
        )

    summary_a = summarize_attempts(
        attempts_a.values(),
        total_samples=first.total_samples,
        currency=endpoint_a.currency if endpoint_a else None,
    )
    summary_b = summarize_attempts(
        attempts_b.values(),
        total_samples=second.total_samples,
        currency=endpoint_b.currency if endpoint_b else None,
    )
    outcome_counts = {
        "both_correct": both_correct,
        "run_a_only_correct": run_a_only_correct,
        "run_b_only_correct": run_b_only_correct,
        "both_incorrect": both_incorrect,
    }
    extension = build_comparison_extension(
        first,
        second,
        endpoint_a,
        endpoint_b,
        list_aggregate_metrics(session, run_a),
        list_aggregate_metrics(session, run_b),
        outcome_counts,
    )
    return {
        "run_a": run_a,
        "run_b": run_b,
        "benchmark": {"id": first.benchmark_id, "version": first.benchmark_version},
        "shared_samples": len(shared_ids),
        "outcomes": outcome_counts,
        "run_a_summary": summary_a,
        "run_b_summary": summary_b,
        "differences": {
            "accuracy": _difference(summary_a["samples"]["accuracy"], summary_b["samples"]["accuracy"]),
            "success_rate": _difference(summary_a["samples"]["success_rate"], summary_b["samples"]["success_rate"]),
            "error_rate": _difference(summary_a["errors"]["rate"], summary_b["errors"]["rate"]),
            "average_latency_ms": _difference(summary_a["latency_ms"]["average"], summary_b["latency_ms"]["average"]),
            "p95_latency_ms": _difference(summary_a["latency_ms"]["p95"], summary_b["latency_ms"]["p95"]),
            "estimated_cost": _difference(summary_a["cost"]["estimated"], summary_b["cost"]["estimated"]),
            "output_tokens": summary_a["tokens"]["output"] - summary_b["tokens"]["output"],
        },
        "sample_outcomes": outcomes,
        **extension,
    }


def _is_correct(attempt: SampleAttempt) -> bool:
    return attempt.status == "succeeded" and attempt.score == 1


def _attempt_evidence(attempt: SampleAttempt) -> dict[str, Any]:
    return {
        "status": attempt.status,
        "score": attempt.score,
        "prediction": attempt.parsed_prediction,
        "latency_ms": attempt.latency_ms,
        "input_tokens": attempt.input_tokens,
        "output_tokens": attempt.output_tokens,
        "estimated_cost": attempt.estimated_cost,
        "error_type": attempt.error_type,
    }


def _difference(first: float | None, second: float | None) -> float | None:
    if first is None or second is None:
        return None
    return round(first - second, 12)


def _compare_documents(store: MongoDocumentStore, run_a: str, run_b: str) -> dict[str, Any]:
    evaluation_repository = MongoEvaluationRepository(store)
    first = store.get_document("evaluation_runs", run_a)
    second = store.get_document("evaluation_runs", run_b)
    if first is None or second is None:
        raise HTTPException(404, "One or both evaluation runs were not found")
    if (first["benchmark_id"], first["benchmark_version"]) != (
        second["benchmark_id"],
        second["benchmark_version"],
    ):
        raise HTTPException(409, "Runs must use the same benchmark version")
    attempts_a = _document_latest_attempts(store, run_a)
    attempts_b = _document_latest_attempts(store, run_b)
    shared_ids = sorted(set(attempts_a) & set(attempts_b))
    both_correct = run_a_only_correct = run_b_only_correct = both_incorrect = 0
    outcomes: list[dict[str, Any]] = []
    for sample_id in shared_ids:
        first_attempt = attempts_a[sample_id]
        second_attempt = attempts_b[sample_id]
        first_correct = _document_is_correct(first_attempt)
        second_correct = _document_is_correct(second_attempt)
        if first_correct and second_correct:
            both_correct += 1
            outcome = "both_correct"
        elif first_correct:
            run_a_only_correct += 1
            outcome = "run_a_only_correct"
        elif second_correct:
            run_b_only_correct += 1
            outcome = "run_b_only_correct"
        else:
            both_incorrect += 1
            outcome = "both_incorrect"
        outcomes.append(
            {
                "sample_id": sample_id,
                "outcome": outcome,
                "run_a": _document_attempt_evidence(first_attempt),
                "run_b": _document_attempt_evidence(second_attempt),
            }
        )
    summary_a = build_repository_run_summary(evaluation_repository, run_a)
    summary_b = build_repository_run_summary(evaluation_repository, run_b)
    endpoint_a = store.get_document("model_endpoints", str(first["model_endpoint_id"]))
    endpoint_b = store.get_document("model_endpoints", str(second["model_endpoint_id"]))
    outcome_counts = {
        "both_correct": both_correct,
        "run_a_only_correct": run_a_only_correct,
        "run_b_only_correct": run_b_only_correct,
        "both_incorrect": both_incorrect,
    }
    extension = build_comparison_extension(
        first,
        second,
        endpoint_a,
        endpoint_b,
        list_mongo_aggregate_metrics(store, run_a),
        list_mongo_aggregate_metrics(store, run_b),
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
            "average_latency_ms": _difference(summary_a["latency_ms"]["average"], summary_b["latency_ms"]["average"]),
            "p95_latency_ms": _difference(summary_a["latency_ms"]["p95"], summary_b["latency_ms"]["p95"]),
            "estimated_cost": _difference(summary_a["cost"]["estimated"], summary_b["cost"]["estimated"]),
            "output_tokens": summary_a["tokens"]["output"] - summary_b["tokens"]["output"],
        },
        "sample_outcomes": outcomes,
        **extension,
    }


def _document_latest_attempts(store: MongoDocumentStore, run_id: str) -> dict[str, dict[str, Any]]:
    attempts = store.list_documents(
        "sample_attempts",
        query={"run_id": run_id},
        sort=[("sample_id", 1), ("attempt_number", -1)],
    )
    latest: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        latest.setdefault(str(attempt["sample_id"]), attempt)
    return latest


def _document_is_correct(attempt: dict[str, Any]) -> bool:
    return attempt.get("status") == "succeeded" and attempt.get("score") == 1


def _document_attempt_evidence(attempt: dict[str, Any]) -> dict[str, Any]:
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
