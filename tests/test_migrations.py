from pathlib import Path

from sqlalchemy import create_engine, inspect, select

from app.core.config import Settings
from app.db.database import Database
from app.db.migrations import MIGRATIONS
from app.db.models import SchemaMigration, SchemaVersion


def test_initialize_upgrades_a_v1_sqlite_database_without_losing_its_run_table(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.db"
    legacy_engine = create_engine(f"sqlite:///{database_path}")
    with legacy_engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE schema_versions (version INTEGER PRIMARY KEY, applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        connection.exec_driver_sql("INSERT INTO schema_versions (version) VALUES (1)")
        connection.exec_driver_sql(
            """
            CREATE TABLE evaluation_runs (
                id VARCHAR(36) PRIMARY KEY,
                model_endpoint_id VARCHAR(36) NOT NULL,
                benchmark_id VARCHAR(128) NOT NULL,
                benchmark_version VARCHAR(64) NOT NULL,
                configuration_snapshot JSON NOT NULL,
                status VARCHAR(32) NOT NULL,
                total_samples INTEGER NOT NULL,
                completed_samples INTEGER NOT NULL DEFAULT 0,
                successful_samples INTEGER NOT NULL DEFAULT 0,
                failed_samples INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                started_at DATETIME,
                completed_at DATETIME
            )
            """
        )
    legacy_engine.dispose()

    database = Database(Settings.local_development(database_url=f"sqlite:///{database_path}"))
    assert [migration.version for migration in database.migration_preview()] == list(range(2, 28))
    database.initialize()
    database.initialize()

    columns = {column["name"] for column in inspect(database.engine).get_columns("evaluation_runs")}
    assert "prompt_package_id" in columns
    assert "archived_at" in columns
    assert "display_name" in columns
    task_columns = {column["name"] for column in inspect(database.engine).get_columns("task_units")}
    assert "parent_task_id" in task_columns
    assert "aggregate_metrics" in inspect(database.engine).get_table_names()
    judge_columns = {column["name"] for column in inspect(database.engine).get_columns("judge_assessments")}
    assert {"comparison_sample_attempt_id", "answer_order", "swap_test_group_id", "selected_answer"} <= judge_columns
    assert {"input_tokens", "output_tokens", "estimated_cost"} <= judge_columns
    dataset_columns = {column["name"] for column in inspect(database.engine).get_columns("dataset_versions")}
    assert {
        "size_bytes",
        "prepared_path",
        "credential_binding_id",
        "input_field",
        "reference_field",
        "capabilities",
        "languages",
        "evaluation_type",
    } <= dataset_columns
    attempt_columns = {column["name"] for column in inspect(database.engine).get_columns("sample_attempts")}
    assert "metric_evidence" in attempt_columns
    aggregate_columns = {column["name"] for column in inspect(database.engine).get_columns("aggregate_metrics")}
    assert "availability_reason" in aggregate_columns
    report_columns = {column["name"] for column in inspect(database.engine).get_columns("reports")}
    assert "artifact_sha256" in report_columns
    with database.get_session() as session:
        assert session.scalar(select(SchemaVersion.version).order_by(SchemaVersion.version.desc())) == 27
        applied = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 2))
        assert applied is not None
        assert applied.migration_id == "20260722_add_prompt_package_reference"
        rate_window_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 3))
        assert rate_window_migration is not None
        assert rate_window_migration.migration_id == "20260722_add_endpoint_rate_windows"
        media_asset_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 4))
        assert media_asset_migration is not None
        assert media_asset_migration.migration_id == "20260722_add_media_assets"
        benchmark_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 5))
        assert benchmark_migration is not None
        assert benchmark_migration.migration_id == "20260722_add_benchmark_definitions"
        user_token_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 6))
        assert user_token_migration is not None
        assert user_token_migration.migration_id == "20260722_add_user_api_tokens"
        judge_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 7))
        assert judge_migration is not None
        assert judge_migration.migration_id == "20260726_add_judge_assessments"
        usage_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 8))
        assert usage_migration is not None
        assert usage_migration.migration_id == "20260726_add_usage_and_cost_evidence"
        share_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 9))
        assert share_migration is not None
        assert share_migration.migration_id == "20260726_add_report_shares"
        metadata_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 10))
        assert metadata_migration is not None
        assert metadata_migration.migration_id == "20260726_add_endpoint_metadata"
        suite_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 11))
        assert suite_migration is not None
        assert suite_migration.migration_id == "20260726_add_evaluation_suites"
        reference_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 12))
        assert reference_migration is not None
        assert reference_migration.migration_id == "20260726_add_run_suite_reference"
        limits_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 13))
        assert limits_migration is not None
        assert limits_migration.migration_id == "20260726_add_extended_rate_limits"
        hierarchy_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 14))
        assert hierarchy_migration is not None
        assert hierarchy_migration.migration_id == "20260726_add_hierarchical_concurrency_limits"
        dataset_credential_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 15))
        assert dataset_credential_migration is not None
        assert dataset_credential_migration.migration_id == "20260726_add_dataset_source_credentials"
        archive_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 16))
        assert archive_migration is not None
        assert archive_migration.migration_id == "20260726_add_run_archiving"
        review_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 17))
        assert review_migration is not None
        assert review_migration.migration_id == "20260726_add_structured_human_review"
        aggregate_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 18))
        assert aggregate_migration is not None
        assert aggregate_migration.migration_id == "20260728_add_task_hierarchy_and_aggregate_metrics"
        remediation_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 22))
        assert remediation_migration is not None
        assert remediation_migration.migration_id == "20260729_add_remediation_persistence_contracts"
        password_limit_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 23))
        assert password_limit_migration is not None
        assert password_limit_migration.migration_id == "20260730_add_report_share_password_limits"
        field_default_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 24))
        assert field_default_migration is not None
        assert field_default_migration.migration_id == "20260807_add_dataset_field_defaults"
        experience_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 25))
        assert experience_migration is not None
        assert experience_migration.migration_id == "20260811_add_evaluation_experience_persistence"
        judge_usage_migration = session.scalar(select(SchemaMigration).where(SchemaMigration.version == 26))
        assert judge_usage_migration is not None
        assert judge_usage_migration.migration_id == "20260812_add_judge_usage_and_cost"
    assert database.migration_preview() == ()
    database.dispose()


def test_initialize_backfills_a_missing_legacy_migration_ledger_before_upgrading(tmp_path: Path) -> None:
    database = Database(Settings.local_development(database_url=f"sqlite:///{tmp_path / 'legacy-v21.db'}"))
    database.initialize()
    with database.engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE schema_migrations")
        connection.exec_driver_sql("DELETE FROM schema_versions WHERE version > 21")

    validation = database.initialize()
    assert validation.is_valid
    with database.get_session() as session:
        assert session.scalar(select(SchemaVersion.version).order_by(SchemaVersion.version.desc())) == 27
        applied_versions = list(session.scalars(select(SchemaMigration.version).order_by(SchemaMigration.version)))
    assert applied_versions == [migration.version for migration in MIGRATIONS]
    assert database.initialize("validate").is_valid
    database.dispose()
