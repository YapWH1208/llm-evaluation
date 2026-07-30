from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from os import getenv
from types import MappingProxyType
from collections.abc import Mapping
from urllib.parse import urlparse

DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
DEFAULT_DATASET_DOWNLOAD_MAX_BYTES = 64 * 1024 * 1024
DEFAULT_PROVIDER_RESPONSE_MAX_BYTES = 4 * 1024 * 1024
_BINDING_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")
_ENVIRONMENT_VARIABLE_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]{0,127}$")


@dataclass(frozen=True, slots=True)
class DatasetCredentialBinding:
    """An administrator-owned reference to one dataset download credential."""

    environment_variable: str
    allowed_hosts: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings for the SQLite-first deployment profile."""

    database_url: str
    secret_encryption_key: str | None = None
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    data_root: str = "./data"
    public_web_url: str | None = None
    admin_token: str | None = None
    allow_insecure_local_auth: bool = False
    database_init_mode: str = "auto_migrate"
    database_backup_before_migrate: bool = False
    mongodb_database: str | None = None
    application_name: str = "LLM/SLM Evaluation Platform"
    application_version: str = "0.1.0"
    system_max_concurrency: int | None = None
    worker_max_concurrency: int | None = None
    dataset_credential_bindings: Mapping[str, DatasetCredentialBinding] = field(default_factory=dict)
    dataset_allowed_hosts: tuple[str, ...] = ()
    dataset_download_max_bytes: int = DEFAULT_DATASET_DOWNLOAD_MAX_BYTES
    provider_response_max_bytes: int = DEFAULT_PROVIDER_RESPONSE_MAX_BYTES

    @classmethod
    def from_environment(cls) -> "Settings":
        configured_origins = getenv("LLE_CORS_ORIGINS")
        return cls(
            database_url=getenv("LLE_DATABASE_URL", "sqlite:///./data/llm_evaluation.db"),
            secret_encryption_key=getenv("LLE_SECRET_ENCRYPTION_KEY"),
            cors_origins=tuple(configured_origins.split(",")) if configured_origins else DEFAULT_CORS_ORIGINS,
            data_root=getenv("LLE_DATA_ROOT", "./data"),
            public_web_url=_optional_public_web_url(getenv("LLE_PUBLIC_WEB_URL")),
            admin_token=getenv("LLE_ADMIN_TOKEN"),
            allow_insecure_local_auth=_environment_bool("LLE_ALLOW_INSECURE_LOCAL_AUTH"),
            database_init_mode=getenv("LLE_DATABASE_INIT_MODE", "auto_migrate"),
            database_backup_before_migrate=getenv("LLE_DATABASE_BACKUP_BEFORE_MIGRATE", "false").lower() in {"1", "true", "yes"},
            mongodb_database=getenv("LLE_MONGODB_DATABASE"),
            system_max_concurrency=_optional_positive_int(getenv("LLE_SYSTEM_MAX_CONCURRENCY")),
            worker_max_concurrency=_optional_positive_int(getenv("LLE_WORKER_MAX_CONCURRENCY")),
            dataset_credential_bindings=_dataset_credential_bindings_from_environment(),
            dataset_allowed_hosts=_comma_separated_hosts(getenv("LLE_DATASET_ALLOWED_HOSTS")),
            dataset_download_max_bytes=_positive_environment_int(
                "LLE_DATASET_DOWNLOAD_MAX_BYTES", DEFAULT_DATASET_DOWNLOAD_MAX_BYTES
            ),
            provider_response_max_bytes=_positive_environment_int(
                "LLE_PROVIDER_RESPONSE_MAX_BYTES", DEFAULT_PROVIDER_RESPONSE_MAX_BYTES
            ),
        )

    @classmethod
    def local_development(cls, **kwargs: object) -> "Settings":
        """Create an explicitly unauthenticated configuration for local tools and tests."""

        return cls(allow_insecure_local_auth=True, **kwargs)

    def validate_authentication(self) -> None:
        if self.admin_token or self.allow_insecure_local_auth:
            return
        raise ValueError(
            "LLE_ADMIN_TOKEN is required unless LLE_ALLOW_INSECURE_LOCAL_AUTH=true is explicitly set for local development."
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


def _optional_public_web_url(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("LLE_PUBLIC_WEB_URL must be an absolute HTTP(S) URL without a query or fragment.")
    return value.strip().rstrip("/")


def _optional_positive_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError("Concurrency environment settings must be positive integers.") from error
    if parsed < 1:
        raise ValueError("Concurrency environment settings must be positive integers.")
    return parsed


def _environment_bool(name: str) -> bool:
    value = getenv(name)
    if value is None or not value.strip():
        return False
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise ValueError(f"{name} must be a boolean value.")


def _positive_environment_int(name: str, default: int) -> int:
    value = getenv(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer.") from error
    if parsed < 1:
        raise ValueError(f"{name} must be a positive integer.")
    return parsed


def _comma_separated_hosts(value: str | None) -> tuple[str, ...]:
    return tuple(
        host
        for item in (value or "").split(",")
        if item.strip() and (host := _normalize_allowed_host(item))
    )


def _dataset_credential_bindings_from_environment() -> Mapping[str, DatasetCredentialBinding]:
    raw = getenv("LLE_DATASET_CREDENTIAL_BINDINGS_JSON")
    if raw is None or not raw.strip():
        return MappingProxyType({})
    try:
        configured = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("LLE_DATASET_CREDENTIAL_BINDINGS_JSON must be a JSON object.") from error
    if not isinstance(configured, dict):
        raise ValueError("LLE_DATASET_CREDENTIAL_BINDINGS_JSON must be a JSON object.")

    bindings: dict[str, DatasetCredentialBinding] = {}
    for binding_id, definition in configured.items():
        if not isinstance(binding_id, str) or not _BINDING_ID_PATTERN.fullmatch(binding_id):
            raise ValueError("Dataset credential binding IDs must contain only letters, digits, underscores, or hyphens.")
        if not isinstance(definition, dict):
            raise ValueError(f"Dataset credential binding {binding_id!r} must be an object.")
        environment_variable = definition.get("environment_variable")
        allowed_hosts = definition.get("allowed_hosts")
        if not isinstance(environment_variable, str) or not _ENVIRONMENT_VARIABLE_PATTERN.fullmatch(environment_variable):
            raise ValueError(f"Dataset credential binding {binding_id!r} must define a valid environment_variable.")
        if not isinstance(allowed_hosts, list) or not all(isinstance(host, str) for host in allowed_hosts):
            raise ValueError(f"Dataset credential binding {binding_id!r} must define allowed_hosts as a string list.")
        normalized_hosts = tuple(
            host
            for item in allowed_hosts
            if item.strip() and (host := _normalize_allowed_host(item))
        )
        if not normalized_hosts:
            raise ValueError(f"Dataset credential binding {binding_id!r} must allow at least one host.")
        bindings[binding_id] = DatasetCredentialBinding(
            environment_variable=environment_variable,
            allowed_hosts=normalized_hosts,
        )
    return MappingProxyType(bindings)


def _normalize_allowed_host(value: str) -> str:
    host = value.strip().lower().rstrip(".")
    if not host or "://" in host or "/" in host or "@" in host or ":" in host:
        raise ValueError("Dataset allowed hosts must be bare hostnames without ports or paths.")
    return host
