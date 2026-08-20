from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.modules.analytics.leaderboard import (
    LeaderboardFilters,
    LeaderboardQuery,
    LeaderboardQueryError,
    build_leaderboard,
)


NOW = datetime(2026, 8, 11, 8, 0, tzinfo=timezone.utc)


def _run(
    run_id: str,
    *,
    model_endpoint_id: str = "endpoint-a",
    display_name: str | None = None,
    dataset: str = "dataset-a",
    status: str = "completed",
    created_at: datetime = NOW,
    archived: bool = False,
    capabilities: tuple[str, ...] = ("reasoning",),
    languages: tuple[str, ...] = ("en",),
    evaluation_type: str = "classification",
    total_samples: int = 10,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=run_id,
        model_endpoint_id=model_endpoint_id,
        benchmark_id="benchmark-a",
        benchmark_version="1.0.0",
        display_name=display_name or run_id,
        configuration_snapshot={
            "dataset_version": {
                "dataset_id": dataset,
            },
            "dataset_profile": {
                "capabilities": list(capabilities),
                "languages": list(languages),
                "evaluation_type": evaluation_type,
            },
            "endpoint": {"model_name": f"snapshot-{model_endpoint_id}"},
        },
        status=status,
        total_samples=total_samples,
        completed_samples=total_samples if status.startswith("completed") else 0,
        successful_samples=total_samples if status.startswith("completed") else 0,
        failed_samples=0,
        created_at=created_at,
        completed_at=created_at + timedelta(minutes=1) if status.startswith("completed") else None,
        archived_at=created_at if archived else None,
    )


def _metric(name: str, value: float | None, *, sample_count: int = 10) -> SimpleNamespace:
    return SimpleNamespace(
        metric_name=name,
        metric_value=value,
        availability_reason=None if value is not None else "Evidence unavailable.",
        sample_count=sample_count,
    )


def _metrics(
    *,
    score: float | None,
    average_latency_ms: float | None = 100,
    p95_latency_ms: float | None = 150,
    estimated_cost: float | None = 0.01,
    sample_count: int = 10,
) -> dict[str, SimpleNamespace]:
    return {
        item.metric_name: item
        for item in (
            _metric("score", score, sample_count=sample_count),
            _metric("average_latency_ms", average_latency_ms, sample_count=sample_count),
            _metric("p95_latency_ms", p95_latency_ms, sample_count=sample_count),
            _metric("estimated_cost", estimated_cost, sample_count=sample_count),
        )
    }


def _build(
    runs: list[SimpleNamespace],
    metrics: dict[str, dict[str, SimpleNamespace]],
    query: LeaderboardQuery | None = None,
) -> dict[str, object]:
    endpoints = {
        "endpoint-a": SimpleNamespace(id="endpoint-a", model_name="Alpha"),
        "endpoint-b": SimpleNamespace(id="endpoint-b", model_name="Beta"),
    }
    return build_leaderboard(runs, endpoints, metrics, query or LeaderboardQuery())


def test_default_order_prioritizes_scored_completed_runs_with_stable_tiebreakers() -> None:
    runs = [
        _run("queued", status="queued", created_at=NOW + timedelta(minutes=5)),
        _run("unscored", created_at=NOW + timedelta(minutes=4)),
        _run("low", created_at=NOW + timedelta(minutes=3)),
        _run("high-slow", created_at=NOW + timedelta(minutes=2)),
        _run("high-fast", created_at=NOW + timedelta(minutes=1)),
    ]
    metrics = {
        "queued": _metrics(score=None),
        "unscored": _metrics(score=None),
        "low": _metrics(score=0.7, p95_latency_ms=80, estimated_cost=0.001),
        "high-slow": _metrics(score=0.9, p95_latency_ms=200, estimated_cost=0.002),
        "high-fast": _metrics(score=0.9, p95_latency_ms=100, estimated_cost=0.003),
    }

    result = _build(runs, metrics)

    assert [item["run_id"] for item in result["items"]] == [
        "high-fast", "high-slow", "low", "unscored", "queued",
    ]
    assert result["total"] == 5
    assert result["page"] == 1
    assert result["page_size"] == 50
    assert result["total_pages"] == 1


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        (LeaderboardFilters(dataset="dataset-b"), ["match"]),
        (LeaderboardFilters(model_endpoint_id="endpoint-b"), ["match"]),
        (LeaderboardFilters(statuses=frozenset({"running"})), ["match"]),
        (LeaderboardFilters(created_from=NOW + timedelta(minutes=1)), ["match"]),
        (LeaderboardFilters(created_to=NOW + timedelta(minutes=1)), ["other"]),
        (LeaderboardFilters(capability="coding"), ["match"]),
        (LeaderboardFilters(language="ms"), ["match"]),
        (LeaderboardFilters(evaluation_type="generation"), ["match"]),
        (LeaderboardFilters(available_metric="precision_macro"), ["match"]),
    ],
)
def test_filters_use_frozen_run_metadata_and_available_metric(
    filters: LeaderboardFilters,
    expected: list[str],
) -> None:
    runs = [
        _run(
            "match",
            dataset="dataset-b",
            model_endpoint_id="endpoint-b",
            status="running",
            created_at=NOW + timedelta(minutes=2),
            capabilities=("coding",),
            languages=("ms",),
            evaluation_type="generation",
        ),
        _run("other", created_at=NOW),
    ]
    metrics = {
        "match": {**_metrics(score=0.8), "precision_macro": _metric("precision_macro", 0.75)},
        "other": {**_metrics(score=0.9), "precision_macro": _metric("precision_macro", None)},
    }

    result = _build(runs, metrics, LeaderboardQuery(filters=filters))

    assert [item["run_id"] for item in result["items"]] == expected


@pytest.mark.parametrize(
    ("sort", "ascending", "descending"),
    [
        ("name", ["alpha", "zulu"], ["zulu", "alpha"]),
        ("model", ["alpha", "zulu"], ["zulu", "alpha"]),
        ("dataset", ["alpha", "zulu"], ["zulu", "alpha"]),
        ("status", ["alpha", "zulu"], ["zulu", "alpha"]),
        ("created_at", ["alpha", "zulu"], ["zulu", "alpha"]),
        ("score", ["alpha", "zulu"], ["zulu", "alpha"]),
        ("average_latency_ms", ["alpha", "zulu"], ["zulu", "alpha"]),
        ("p95_latency_ms", ["alpha", "zulu"], ["zulu", "alpha"]),
        ("estimated_cost", ["alpha", "zulu"], ["zulu", "alpha"]),
        ("sample_count", ["alpha", "zulu"], ["zulu", "alpha"]),
    ],
)
def test_explicit_sorts_support_both_directions(
    sort: str,
    ascending: list[str],
    descending: list[str],
) -> None:
    runs = [
        _run(
            "alpha",
            display_name="Alpha",
            model_endpoint_id="endpoint-a",
            dataset="a-dataset",
            status="completed",
            created_at=NOW,
            total_samples=5,
        ),
        _run(
            "zulu",
            display_name="Zulu",
            model_endpoint_id="endpoint-b",
            dataset="z-dataset",
            status="running",
            created_at=NOW + timedelta(minutes=1),
            total_samples=10,
        ),
        _run("missing", display_name="Missing", created_at=NOW + timedelta(minutes=2)),
    ]
    metrics = {
        "alpha": _metrics(score=0.1, average_latency_ms=10, p95_latency_ms=20, estimated_cost=0.001, sample_count=5),
        "zulu": _metrics(score=0.9, average_latency_ms=90, p95_latency_ms=100, estimated_cost=0.009, sample_count=10),
        "missing": _metrics(score=None, average_latency_ms=None, p95_latency_ms=None, estimated_cost=None, sample_count=0),
    }

    asc = _build(runs, metrics, LeaderboardQuery(sort=sort, direction="asc"))
    desc = _build(runs, metrics, LeaderboardQuery(sort=sort, direction="desc"))

    asc_ids = [item["run_id"] for item in asc["items"]]
    desc_ids = [item["run_id"] for item in desc["items"]]
    assert asc_ids.index(ascending[0]) < asc_ids.index(ascending[1])
    assert desc_ids.index(descending[0]) < desc_ids.index(descending[1])
    if sort in {"score", "average_latency_ms", "p95_latency_ms", "estimated_cost"}:
        assert asc["items"][-1]["run_id"] == "missing"
        assert desc["items"][-1]["run_id"] == "missing"


def test_archived_runs_are_excluded_and_results_are_paginated() -> None:
    runs = [_run(f"run-{index:03}", created_at=NOW + timedelta(minutes=index)) for index in range(121)]
    runs.append(_run("archived", archived=True))
    metrics = {run.id: _metrics(score=0.5) for run in runs}

    result = _build(runs, metrics, LeaderboardQuery(page=3, page_size=50))

    assert result["total"] == 121
    assert result["total_pages"] == 3
    assert len(result["items"]) == 21
    assert all(item["run_id"] != "archived" for item in result["items"])


@pytest.mark.parametrize(
    "query",
    [
        LeaderboardQuery(sort="unknown"),
        LeaderboardQuery(direction="sideways"),
        LeaderboardQuery(page=0),
        LeaderboardQuery(page_size=0),
        LeaderboardQuery(page_size=101),
    ],
)
def test_invalid_queries_are_rejected(query: LeaderboardQuery) -> None:
    with pytest.raises(LeaderboardQueryError):
        _build([], {}, query)
