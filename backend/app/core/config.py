from __future__ import annotations

from dataclasses import dataclass
from os import getenv

DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")

@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings for the SQLite-first deployment profile."""

    database_url: str
    secret_encryption_key: str | None = None
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    data_root: str = "./data"
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
        )

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")
