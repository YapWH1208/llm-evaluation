from datetime import datetime, timezone
from types import SimpleNamespace

from app.modules.evaluations.names import format_run_display_name, resolve_run_display_name


def test_format_run_display_name_is_safe_bounded_and_uses_utc() -> None:
    created_at = datetime(2026, 8, 11, 9, 7, 6, tzinfo=timezone.utc)

    assert format_run_display_name(
        "  Módèl_Name/v2  ",
        "  Data Set_01  ",
        created_at,
    ) == "Model-Name-v2_Data-Set-01_20260811T090706Z"
    assert len(format_run_display_name("x" * 800, "y" * 800, created_at)) <= 500


def test_resolve_run_display_name_preserves_persisted_names_and_falls_back_deterministically() -> None:
    created_at = datetime(2026, 8, 11, 9, 7, 6, tzinfo=timezone.utc)
    persisted = {
        "display_name": "persisted-name",
        "created_at": created_at,
        "benchmark_id": "ignored",
        "configuration_snapshot": {},
    }
    assert resolve_run_display_name(persisted) == "persisted-name"

    legacy_dataset = {
        "created_at": created_at,
        "benchmark_id": "dataset-evaluation",
        "configuration_snapshot": {
            "endpoint": {"model_name": "legacy/model"},
            "dataset_version": {"dataset_id": "legacy_data"},
        },
    }
    assert resolve_run_display_name(legacy_dataset) == (
        "legacy-model_legacy-data_20260811T090706Z"
    )

    legacy_benchmark = SimpleNamespace(
        display_name=None,
        created_at=created_at,
        benchmark_id="text-quick-check",
        configuration_snapshot={"endpoint": {"model_name": "model"}},
    )
    assert resolve_run_display_name(legacy_benchmark) == (
        "model_text-quick-check_20260811T090706Z"
    )
