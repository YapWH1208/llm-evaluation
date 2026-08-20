from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Engine, ForeignKeyConstraint, UniqueConstraint, create_engine, event, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.migrations import LATEST_SCHEMA_VERSION, MIGRATIONS, Migration
from app.db.models import Base, SchemaMigration, SchemaVersion


INITIALIZATION_MODES = frozenset({"auto_migrate", "validate", "preview"})
_LEGACY_UNENFORCEABLE_FOREIGN_KEYS = frozenset(
    {
        ("evaluation_runs", "model_endpoint_id"),
        ("evaluation_runs", "prompt_package_id"),
        ("evaluation_runs", "suite_id"),
    }
)


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
    missing_columns: tuple[str, ...] = ()
    missing_indexes: tuple[str, ...] = ()
    missing_constraints: tuple[str, ...] = ()
    missing_foreign_keys: tuple[str, ...] = ()
    missing_migrations: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return (
            self.current_version == self.expected_version
            and not self.missing_tables
            and not self.missing_columns
            and not self.missing_indexes
            and not self.missing_constraints
            and not self.missing_foreign_keys
            and not self.missing_migrations
        )


class Database:
    """Owns relational database setup, migrations, validation, and sessions."""

    CURRENT_SCHEMA_VERSION = LATEST_SCHEMA_VERSION

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if settings.database_kind == "mongodb":
            raise DatabaseConfigurationError(
                "MongoDB requires the optional document-store adapter, which is not configured in this relational deployment."
            )
        if settings.database_kind != "sqlite":
            raise DatabaseConfigurationError("Database URL must use the SQLite dialect.")
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
            current_version = (
                connection.scalar(select(SchemaVersion.version).order_by(SchemaVersion.version.desc()).limit(1)) or 0
            )
        return tuple(migration for migration in MIGRATIONS if migration.version > current_version)

    def validate_schema(self) -> DatabaseValidation:
        """Validate tables and schema version without creating or changing anything."""

        with self.engine.connect() as connection:
            inspector = inspect(connection)
            table_names = set(inspector.get_table_names())
            missing_tables = tuple(sorted(set(Base.metadata.tables) - table_names))
            missing_columns: list[str] = []
            missing_indexes: list[str] = []
            missing_constraints: list[str] = []
            missing_foreign_keys: list[str] = []
            for table in Base.metadata.sorted_tables:
                if table.name not in table_names:
                    continue
                actual_columns = {column["name"] for column in inspector.get_columns(table.name)}
                missing_columns.extend(
                    f"{table.name}.{column.name}" for column in table.columns if column.name not in actual_columns
                )
                actual_indexes = {index.get("name") for index in inspector.get_indexes(table.name)}
                missing_indexes.extend(
                    f"{table.name}.{index.name}"
                    for index in table.indexes
                    if index.name and index.name not in actual_indexes
                )
                actual_constraints = {
                    constraint.get("name") for constraint in inspector.get_unique_constraints(table.name)
                }
                missing_constraints.extend(
                    f"{table.name}.{constraint.name}"
                    for constraint in table.constraints
                    if isinstance(constraint, UniqueConstraint)
                    and constraint.name
                    and constraint.name not in actual_constraints
                )
                actual_foreign_keys = {
                    (
                        tuple(constraint.get("constrained_columns") or ()),
                        str(constraint.get("referred_table") or ""),
                        tuple(constraint.get("referred_columns") or ()),
                    )
                    for constraint in inspector.get_foreign_keys(table.name)
                }
                for constraint in table.constraints:
                    if not isinstance(constraint, ForeignKeyConstraint):
                        continue
                    expected = (
                        tuple(column.name for column in constraint.columns),
                        constraint.referred_table.name if constraint.referred_table is not None else "",
                        tuple(element.column.name for element in constraint.elements),
                    )
                    if (table.name, ",".join(expected[0])) in _LEGACY_UNENFORCEABLE_FOREIGN_KEYS:
                        continue
                    if expected not in actual_foreign_keys:
                        missing_foreign_keys.append(f"{table.name}.{','.join(expected[0])}")
            current_version = 0
            missing_migrations: list[str] = []
            if "schema_versions" in table_names:
                current_version = (
                    connection.scalar(select(SchemaVersion.version).order_by(SchemaVersion.version.desc()).limit(1))
                    or 0
                )
            if "schema_migrations" not in table_names:
                missing_migrations = [migration.migration_id for migration in MIGRATIONS]
            else:
                applied = {
                    int(version): str(migration_id)
                    for version, migration_id in connection.execute(
                        select(SchemaMigration.version, SchemaMigration.migration_id)
                    )
                }
                missing_migrations = [
                    migration.migration_id
                    for migration in MIGRATIONS
                    if applied.get(migration.version) != migration.migration_id
                ]
        return DatabaseValidation(
            database_kind=self.settings.database_kind,
            current_version=current_version,
            expected_version=self.CURRENT_SCHEMA_VERSION,
            missing_tables=missing_tables,
            missing_columns=tuple(sorted(missing_columns)),
            missing_indexes=tuple(sorted(missing_indexes)),
            missing_constraints=tuple(sorted(missing_constraints)),
            missing_foreign_keys=tuple(sorted(missing_foreign_keys)),
            missing_migrations=tuple(sorted(missing_migrations)),
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
                    f"missing tables: {', '.join(validation.missing_tables) or 'none'}; "
                    f"missing columns: {', '.join(validation.missing_columns) or 'none'}; "
                    f"missing indexes: {', '.join(validation.missing_indexes) or 'none'}; "
                    f"missing constraints: {', '.join(validation.missing_constraints) or 'none'}; "
                    f"missing foreign keys: {', '.join(validation.missing_foreign_keys) or 'none'}; "
                    f"missing migrations: {', '.join(validation.missing_migrations) or 'none'}."
                )
            return validation

        if self.settings.database_backup_before_migrate and self.migration_preview():
            self.backup_before_migration()
        with self.engine.connect() as connection:
            migration_ledger_existed = "schema_migrations" in set(connection.dialect.get_table_names(connection))
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            current_version = (
                connection.scalar(select(SchemaVersion.version).order_by(SchemaVersion.version.desc()).limit(1)) or 0
            )
            # v1-v21 deployments predate the migration ledger.  Their existing
            # schema_versions rows are the durable record that those canonical
            # upgrades completed, so restore the ledger before validation adds
            # newer entries. This is additive and never replays old DDL.
            if not migration_ledger_existed:
                for migration in MIGRATIONS:
                    if migration.version > current_version:
                        break
                    connection.execute(
                        SchemaMigration.__table__.insert().values(
                            version=migration.version,
                            migration_id=migration.migration_id,
                            description=migration.description,
                        )
                    )
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
            raise DatabaseValidationError(
                "Database initialization completed but schema validation did not pass: "
                f"tables={', '.join(validation.missing_tables) or 'none'}; "
                f"columns={', '.join(validation.missing_columns) or 'none'}; "
                f"indexes={', '.join(validation.missing_indexes) or 'none'}; "
                f"constraints={', '.join(validation.missing_constraints) or 'none'}; "
                f"foreign_keys={', '.join(validation.missing_foreign_keys) or 'none'}; "
                f"migrations={', '.join(validation.missing_migrations) or 'none'}."
            )
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
