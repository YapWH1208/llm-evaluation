from __future__ import annotations

from dataclasses import dataclass
from os import getenv
from urllib.parse import urlparse

DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")

@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings for the SQLite-first deployment profile."""

    database_url: str
    secret_encryption_key: str | None = None
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    data_root: str = "./data"
    admin_token: str | None = None
    database_init_mode: str = "auto_migrate"
    database_backup_before_migrate: bool = False
    mongodb_database: str | None = None
    application_name: str = "LLM/SLM Evaluation Platform"
    application_version: str = "0.1.0"

    @classmethod
    def from_environment(cls) -> "Settings":
        configured_origins = getenv("LLE_CORS_ORIGINS")
        return cls(
            database_url=getenv("LLE_DATABASE_URL", "sqlite:///./data/llm_evaluation.db"),
            secret_encryption_key=getenv("LLE_SECRET_ENCRYPTION_KEY"),
            cors_origins=tuple(configured_origins.split(",")) if configured_origins else DEFAULT_CORS_ORIGINS,
            data_root=getenv("LLE_DATA_ROOT", "./data"),
            admin_token=getenv("LLE_ADMIN_TOKEN"),
            database_init_mode=getenv("LLE_DATABASE_INIT_MODE", "auto_migrate"),
            database_backup_before_migrate=getenv("LLE_DATABASE_BACKUP_BEFORE_MIGRATE", "false").lower() in {"1", "true", "yes"},
            mongodb_database=getenv("LLE_MONGODB_DATABASE"),
        )

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def database_kind(self) -> str:
        if self.is_sqlite:
            return "sqlite"
        if self.database_url.startswith(("postgresql", "postgres")):
            return "postgresql"
        if self.database_url.startswith(("mongodb", "mongo")):
            return "mongodb"
        return "unknown"

    @property
    def mongodb_database_name(self) -> str:
        """Use an explicit name or the database segment of a MongoDB URI."""

        if self.database_kind != "mongodb":
            raise ValueError("MongoDB database name requested for a non-MongoDB URL.")
        if self.mongodb_database:
            return self.mongodb_database
        path = urlparse(self.database_url).path.strip("/")
        return path.split("/", 1)[0] or "llm_evaluation"
