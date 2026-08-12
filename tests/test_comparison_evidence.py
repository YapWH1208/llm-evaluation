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


def test_comparison_extension_exposes_llm_judge_as_a_named_ratio_metric() -> None:
    run = {
        "id": "judge-run-a",
        "model_endpoint_id": "model-a",
        "benchmark_id": "dataset-evaluation",
        "status": "completed",
        "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "configuration_snapshot": {"endpoint": {"model_name": "judge-target"}},
    }
    extension = build_comparison_extension(
        run,
        {**run, "id": "judge-run-b", "model_endpoint_id": "model-b"},
        None,
        None,
        [{"metric_name": "llm_judge", "metric_value": 0.75, "sample_count": 2}],
        [{"metric_name": "llm_judge", "metric_value": 0.5, "sample_count": 1}],
        {},
    )

    judge_metric = extension["named_metrics"][0]
    assert judge_metric["metric_name"] == "llm_judge"
    assert judge_metric["label"] == "LLM-as-judge"
    assert judge_metric["unit"] == "ratio"
    assert judge_metric["run_a"] == {"value": 0.75, "availability_reason": None, "sample_count": 2}
    assert judge_metric["run_b"] == {"value": 0.5, "availability_reason": None, "sample_count": 1}
    assert judge_metric["delta"] == 0.25
