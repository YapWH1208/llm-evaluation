from pathlib import Path

from sqlalchemy import create_engine, inspect, select

from app.core.config import Settings
from app.db.database import Database
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

    database = Database(Settings(database_url=f"sqlite:///{database_path}"))
    assert [migration.version for migration in database.migration_preview()] == [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    database.initialize()
    database.initialize()

    columns = {column["name"] for column in inspect(database.engine).get_columns("evaluation_runs")}
    assert "prompt_package_id" in columns
    with database.get_session() as session:
        assert session.scalar(select(SchemaVersion.version).order_by(SchemaVersion.version.desc())) == 12
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
    assert database.migration_preview() == ()
    database.dispose()
