from pathlib import Path

import pytest

from app.core.config import Settings
from app.db.database import Database, DatabaseValidationError
from app.db.migrations import MIGRATIONS


def test_database_preview_validation_and_sqlite_backup(tmp_path: Path) -> None:
    database_path = tmp_path / "platform.db"
    database = Database(
        Settings.local_development(
            database_url=f"sqlite:///{database_path}",
            data_root=str(tmp_path / "data"),
        )
    )
    try:
        assert database.initialize("preview") == MIGRATIONS
        with pytest.raises(DatabaseValidationError):
            database.initialize("validate")

        validation = database.initialize("auto_migrate")
        assert not isinstance(validation, tuple)
        assert validation.is_valid
        assert validation.database_kind == "sqlite"
        assert database.initialize("preview") == ()

        backup = database.backup_before_migration()
        assert backup is not None
        assert backup.is_file()
    finally:
        database.dispose()


def test_database_kind_recognizes_sqlite_and_mongodb_urls() -> None:
    assert Settings.local_development(database_url="sqlite:///./data/llm_evaluation.db").database_kind == "sqlite"
    assert Settings.local_development(database_url="mongodb://host/db").database_kind == "mongodb"
    assert Settings.local_development(database_url="postgresql+psycopg://user:pass@host/db").database_kind == "unknown"


def test_schema_validation_detects_missing_column_index_and_migration(tmp_path: Path) -> None:
    database = Database(Settings.local_development(database_url=f"sqlite:///{tmp_path / 'damaged.db'}"))
    try:
        database.initialize()
        with database.engine.begin() as connection:
            connection.exec_driver_sql("DROP INDEX ix_task_units_claimable")
            connection.exec_driver_sql("ALTER TABLE task_units DROP COLUMN lease_version")
            connection.exec_driver_sql("DELETE FROM schema_migrations WHERE version = 22")

        validation = database.validate_schema()
        assert "task_units.lease_version" in validation.missing_columns
        assert "task_units.ix_task_units_claimable" in validation.missing_indexes
        assert "20260729_add_remediation_persistence_contracts" in validation.missing_migrations
        with pytest.raises(DatabaseValidationError):
            database.initialize("validate")
    finally:
        database.dispose()
