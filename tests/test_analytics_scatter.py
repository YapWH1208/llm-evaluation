from datetime import datetime, timezone

import pytest

from app.modules.analytics.scatter import ScatterFilters, ScatterQueryError, build_scatter_response


def _run(
    run_id: str,
    *,
    model_id: str,
    dataset_id: str,
    status: str = "completed",
    capabilities: list[str] | None = None,
    languages: list[str] | None = None,
    evaluation_type: str = "custom",
    created_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "id": run_id,
        "display_name": f"display-{run_id}",
        "model_endpoint_id": model_id,
        "benchmark_id": "dataset-evaluation",
        "benchmark_version": "1.0.0",
        "status": status,
        "created_at": created_at or datetime(2026, 8, 1, tzinfo=timezone.utc),
        "archived_at": None,
        "configuration_snapshot": {
            "dataset_version": {"dataset_id": dataset_id},
            "dataset_profile": {
                "capabilities": capabilities or [],
                "languages": languages or [],
                "evaluation_type": evaluation_type,
            },
        },
    }


def _metrics(score: float | None, latency: float | None) -> dict[str, dict[str, object]]:
    return {
        "score": {
            "metric_name": "score",
            "metric_value": score,
            "availability_reason": None if score is not None else "No score evidence.",
        },
        "average_latency_ms": {
            "metric_name": "average_latency_ms",
            "metric_value": latency,
            "availability_reason": None if latency is not None else "No latency evidence.",
        },
        "accuracy": {
            "metric_name": "accuracy",
            "metric_value": score,
            "availability_reason": None if score is not None else "No accuracy evidence.",
        },
        "estimated_cost": {
            "metric_name": "estimated_cost",
            "metric_value": score / 10 if score is not None else None,
            "availability_reason": None if score is not None else "No cost evidence.",
        },
    }


def test_scatter_filters_are_combinable_and_default_to_all_eligible_runs() -> None:
    runs = [
        _run(
            "r1",
            model_id="m1",
            dataset_id="dataset-a",
            capabilities=["reasoning"],
            languages=["en-US"],
            evaluation_type="classification",
            created_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
        ),
        _run(
            "r2",
            model_id="m2",
            dataset_id="dataset-b",
            status="completed_with_errors",
            capabilities=["generation"],
            languages=["fr"],
            evaluation_type="generation",
            created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        ),
    ]
    endpoints = {
        "m1": {"id": "m1", "model_name": "model-a"},
        "m2": {"id": "m2", "model_name": "model-b"},
    }
    metrics = {"r1": _metrics(0.9, 100), "r2": _metrics(0.4, 300)}

    default = build_scatter_response(
        runs,
        endpoints,
        metrics,
        x_axis="score",
        y_axis="average_latency_ms",
        filters=ScatterFilters(),
    )
    assert [point["run_id"] for point in default["points"]] == ["r1", "r2"]
    assert default["selected_run_ids"] == ["r1", "r2"]

    filters = ScatterFilters(
        run_ids=frozenset({"r1", "r2"}),
        created_from=datetime(2026, 8, 1, tzinfo=timezone.utc),
        created_to=datetime(2026, 8, 3, tzinfo=timezone.utc),
        model_endpoint_id="m1",
        dataset="dataset-a",
        statuses=frozenset({"completed"}),
        capability="reasoning",
        language="en-US",
        evaluation_type="classification",
        min_score=0.8,
        max_score=1.0,
        min_accuracy=0.8,
        max_accuracy=1.0,
        min_latency_ms=50,
        max_latency_ms=150,
        min_cost=0.08,
        max_cost=0.1,
    )
    combined = build_scatter_response(
        runs,
        endpoints,
        metrics,
        x_axis="score",
        y_axis="average_latency_ms",
        filters=filters,
    )
    assert [point["run_id"] for point in combined["points"]] == ["r1"]
    assert combined["eligible_run_count"] == 1


@pytest.mark.parametrize(
    "filters",
    [
        ScatterFilters(run_ids=frozenset({"r1"})),
        ScatterFilters(created_from=datetime(2026, 8, 1, tzinfo=timezone.utc)),
        ScatterFilters(model_endpoint_id="m1"),
        ScatterFilters(dataset="dataset-a"),
        ScatterFilters(statuses=frozenset({"completed"})),
        ScatterFilters(capability="reasoning"),
        ScatterFilters(language="en-US"),
        ScatterFilters(evaluation_type="classification"),
        ScatterFilters(min_score=0.8),
        ScatterFilters(min_accuracy=0.8),
        ScatterFilters(max_latency_ms=150),
        ScatterFilters(min_cost=0.08),
    ],
)
def test_scatter_each_filter_selects_the_expected_run(filters: ScatterFilters) -> None:
    runs = [
        _run(
            "r1",
            model_id="m1",
            dataset_id="dataset-a",
            capabilities=["reasoning"],
            languages=["en-US"],
            evaluation_type="classification",
            created_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
        ),
        _run(
            "r2",
            model_id="m2",
            dataset_id="dataset-b",
            status="failed",
            capabilities=["generation"],
            languages=["fr"],
            evaluation_type="generation",
            created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        ),
    ]
    response = build_scatter_response(
        runs,
        {"m1": {"model_name": "model-a"}, "m2": {"model_name": "model-b"}},
        {"r1": _metrics(0.9, 100), "r2": _metrics(0.4, 300)},
        x_axis="score",
        y_axis="average_latency_ms",
        filters=filters,
    )
    assert [point["run_id"] for point in response["points"]] == ["r1"]


def test_scatter_counts_unavailable_axes_and_caps_visible_points() -> None:
    runs = [_run(f"r{index:03}", model_id="m1", dataset_id="dataset-a") for index in range(502)]
    metrics = {run["id"]: _metrics(0.5, None if run["id"] == "r501" else 100) for run in runs}
    response = build_scatter_response(
        runs,
        {"m1": {"model_name": "model"}},
        metrics,
        x_axis="score",
        y_axis="average_latency_ms",
        filters=ScatterFilters(),
    )

    assert response["eligible_run_count"] == 502
    assert response["plotted_count"] == 500
    assert response["unavailable_count"] == 1
    assert response["truncated_count"] == 1
    assert response["unavailable_by_axis"] == {"x": 0, "y": 1, "both": 0}
    assert response["unavailable_reasons"] == [{"axis": "y", "reason": "No latency evidence.", "count": 1}]
    assert len(response["points"]) == 500


def test_scatter_rejects_unknown_axes_with_available_metric_context() -> None:
    with pytest.raises(ScatterQueryError, match="Unknown scatter axis") as error:
        build_scatter_response(
            [],
            {},
            {},
            x_axis="made_up",
            y_axis="score",
            filters=ScatterFilters(),
        )
    assert "score" in str(error.value)


def test_scatter_keeps_legacy_runs_with_name_and_score_fallbacks() -> None:
    legacy = _run("legacy", model_id="m1", dataset_id="legacy-dataset")
    legacy["display_name"] = None
    legacy["configuration_snapshot"] = {
        "endpoint": {"model_name": "legacy-model"},
        "dataset_version": {"dataset_id": "legacy-dataset"},
    }
    response = build_scatter_response(
        [legacy],
        {},
        {
            "legacy": {
                "accuracy": {"metric_name": "accuracy", "metric_value": 0.7},
                "average_latency_ms": {"metric_name": "average_latency_ms", "metric_value": 42},
            }
        },
        x_axis="score",
        y_axis="average_latency_ms",
        filters=ScatterFilters(),
    )

    assert response["points"][0]["x"] == 0.7
    assert response["points"][0]["display_name"].startswith("legacy-model_legacy-dataset_")
    assert response["points"][0]["evaluation_type"] == "custom"
