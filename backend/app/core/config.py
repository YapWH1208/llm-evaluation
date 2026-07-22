from __future__ import annotations

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings for the SQLite-first deployment profile."""

    database_url: str
    application_name: str = "LLM/SLM Evaluation Platform"
    application_version: str = "0.1.0"

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            database_url=getenv("LLE_DATABASE_URL", "sqlite:///./data/llm_evaluation.db"),
        )

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")
