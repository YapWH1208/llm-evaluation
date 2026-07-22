from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.models import Base, SchemaVersion


class Database:
    """Owns database setup and sessions for one application instance."""

    INITIAL_SCHEMA_VERSION = 1

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
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
        engine = create_engine(self.settings.database_url, connect_args=connect_args)

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

    def initialize(self) -> None:
        """Create the initial schema for a single-node startup."""

        Base.metadata.create_all(self.engine)
        with self.session_factory.begin() as session:
            current_version = session.scalar(
                select(SchemaVersion.version)
                .order_by(SchemaVersion.version.desc())
                .limit(1)
            )
            if current_version is None:
                session.add(SchemaVersion(version=self.INITIAL_SCHEMA_VERSION))

    def get_session(self) -> Session:
        return self.session_factory()

    def dispose(self) -> None:
        self.engine.dispose()
