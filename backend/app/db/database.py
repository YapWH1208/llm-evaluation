from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.migrations import LATEST_SCHEMA_VERSION, MIGRATIONS, Migration
from app.db.models import Base, SchemaMigration, SchemaVersion


INITIALIZATION_MODES = frozenset({"auto_migrate", "validate", "preview"})


class DatabaseConfigurationError(ValueError):
    pass


class DatabaseValidationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DatabaseValidation:
    database_kind: str
    current_version: int
    expected_version: int
    missing_tables: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return self.current_version == self.expected_version and not self.missing_tables


class Database:
    """Owns relational database setup, migrations, validation, and sessions."""

    CURRENT_SCHEMA_VERSION = LATEST_SCHEMA_VERSION

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if settings.database_kind == "mongodb":
            raise DatabaseConfigurationError(
                "MongoDB requires the optional document-store adapter, which is not configured in this relational deployment."
            )
        if settings.database_kind not in {"sqlite", "postgresql"}:
            raise DatabaseConfigurationError("Database URL must use a SQLite or PostgreSQL dialect.")
        self._ensure_sqlite_parent_directory()
        self.engine = self._build_engine()
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    def _ensure_sqlite_parent_directory(self) -> None:
        if not self.settings.is_sqlite:
            return
        database_name = make_url(self.settings.database_url).database
        if database_name and database_name != ":memory:":
            Path(database_name).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

    def _build_engine(self) -> Engine:
        connect_args = {"check_same_thread": False} if self.settings.is_sqlite else {}
        engine = create_engine(self.settings.database_url, connect_args=connect_args, pool_pre_ping=True)
        if self.settings.is_sqlite:
            event.listen(engine, "connect", self._configure_sqlite_connection)
        return engine

    @staticmethod
    def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    def migration_preview(self) -> tuple[Migration, ...]:
        """Return pending forward-only migrations without changing the database."""

        with self.engine.connect() as connection:
            table_names = set(connection.dialect.get_table_names(connection))
            if "schema_versions" not in table_names:
                return MIGRATIONS
            current_version = connection.scalar(
                select(SchemaVersion.version).order_by(SchemaVersion.version.desc()).limit(1)
            ) or 0
        return tuple(migration for migration in MIGRATIONS if migration.version > current_version)

    def validate_schema(self) -> DatabaseValidation:
        """Validate tables and schema version without creating or changing anything."""

        with self.engine.connect() as connection:
            table_names = set(connection.dialect.get_table_names(connection))
            missing_tables = tuple(sorted(set(Base.metadata.tables) - table_names))
            current_version = 0
            if "schema_versions" in table_names:
                current_version = connection.scalar(
                    select(SchemaVersion.version).order_by(SchemaVersion.version.desc()).limit(1)
                ) or 0
        return DatabaseValidation(
            database_kind=self.settings.database_kind,
            current_version=current_version,
            expected_version=self.CURRENT_SCHEMA_VERSION,
            missing_tables=missing_tables,
        )

    def initialize(self, mode: str | None = None) -> DatabaseValidation | tuple[Migration, ...]:
        """Initialize safely, validate-only, or preview migrations based on deployment mode."""

        selected_mode = (mode or self.settings.database_init_mode).lower().strip()
        if selected_mode not in INITIALIZATION_MODES:
            allowed = ", ".join(sorted(INITIALIZATION_MODES))
            raise DatabaseConfigurationError(f"Unsupported database initialization mode. Use one of: {allowed}.")
        if selected_mode == "preview":
            return self.migration_preview()
        if selected_mode == "validate":
            validation = self.validate_schema()
            if not validation.is_valid:
                raise DatabaseValidationError(
                    f"Database validation failed: version {validation.current_version}/{validation.expected_version}; "
                    f"missing tables: {', '.join(validation.missing_tables) or 'none'}."
                )
            return validation

        if self.settings.database_backup_before_migrate and self.migration_preview():
            self.backup_before_migration()
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            current_version = connection.scalar(
                select(SchemaVersion.version)
                .order_by(SchemaVersion.version.desc())
                .limit(1)
            ) or 0
            for migration in MIGRATIONS:
                if migration.version <= current_version:
                    continue
                migration.upgrade(connection)
                Base.metadata.create_all(connection)
                connection.execute(SchemaVersion.__table__.insert().values(version=migration.version))
                connection.execute(
                    SchemaMigration.__table__.insert().values(
                        version=migration.version,
                        migration_id=migration.migration_id,
                        description=migration.description,
                    )
                )
                current_version = migration.version
        validation = self.validate_schema()
        if not validation.is_valid:
            raise DatabaseValidationError("Database initialization completed but schema validation did not pass.")
        return validation

    def backup_before_migration(self) -> Path | None:
        """Create a consistent SQLite backup before applying pending migrations."""

        if not self.settings.is_sqlite:
            return None
        database_name = make_url(self.settings.database_url).database
        if not database_name or database_name == ":memory:":
            return None
        source_path = Path(database_name).expanduser().resolve()
        if not source_path.is_file():
            return None
        backup_root = Path(self.settings.data_root).resolve() / "backups"
        backup_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target_path = backup_root / f"{source_path.stem}-{timestamp}.sqlite"
        with sqlite3.connect(source_path) as source, sqlite3.connect(target_path) as target:
            source.backup(target)
        return target_path

    def get_session(self) -> Session:
        return self.session_factory()

    def dispose(self) -> None:
        self.engine.dispose()
