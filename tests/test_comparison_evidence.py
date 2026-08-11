from datetime import datetime, timezone

from app.services.comparison_evidence import build_comparison_extension


def test_comparison_extension_preserves_legacy_names_and_missing_metric_reasons() -> None:
    first = {
        "id": "run-a",
        "display_name": None,
        "model_endpoint_id": "model-a",
        "benchmark_id": "dataset-evaluation",
        "status": "completed",
        "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "configuration_snapshot": {
            "endpoint": {"model_name": "legacy-a"},
            "dataset_version": {"dataset_id": "dataset-a"},
        },
    }
    second = {
        **first,
        "id": "run-b",
        "model_endpoint_id": "model-b",
        "configuration_snapshot": {
            "endpoint": {"model_name": "legacy-b"},
            "dataset_version": {"dataset_id": "dataset-a"},
        },
    }
    extension = build_comparison_extension(
        first,
        second,
        None,
        None,
        [{"metric_name": "score", "metric_value": 0.8, "sample_count": 10}],
        [],
        {"both_correct": 3, "run_a_only_correct": 2},
    )

    assert extension["runs"]["a"]["display_name"].startswith("legacy-a_dataset-a_")
    assert extension["runs"]["b"]["display_name"].startswith("legacy-b_dataset-a_")
    score = extension["named_metrics"][0]
    assert score["metric_name"] == "score"
    assert score["run_a"]["value"] == 0.8
    assert score["run_b"]["value"] is None
    assert score["run_b"]["availability_reason"] == "Metric was not materialized for this run."
    assert score["delta"] is None
    assert extension["outcome_distribution"] == [
        {"outcome": "both_correct", "count": 3},
        {"outcome": "run_a_only_correct", "count": 2},
        {"outcome": "run_b_only_correct", "count": 0},
        {"outcome": "both_incorrect", "count": 0},
    ]
