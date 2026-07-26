from pathlib import Path

import pytest

from app.core.config import Settings
from app.db.database import Database, DatabaseValidationError
from app.db.migrations import MIGRATIONS


def test_database_preview_validation_and_sqlite_backup(tmp_path: Path) -> None:
    database_path = tmp_path / "platform.db"
    database = Database(
        Settings(
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


def test_database_kind_recognizes_postgresql_and_mongodb_urls() -> None:
    assert Settings(database_url="postgresql+psycopg://user:pass@host/db").database_kind == "postgresql"
    assert Settings(database_url="mongodb://host/db").database_kind == "mongodb"
