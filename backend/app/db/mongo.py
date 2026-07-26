from __future__ import annotations

"""MongoDB document-store setup and lease queue primitives.

This module deliberately keeps MongoDB-specific collection/index and atomic
claim logic outside services.  The relational repository remains the active
application backend while repository migration is completed incrementally.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.core.config import Settings
from app.db.migrations import LATEST_SCHEMA_VERSION, MIGRATIONS, Migration


class MongoConfigurationError(ValueError):
    """Raised when the optional PyMongo runtime or MongoDB configuration is absent."""


class MongoValidationError(RuntimeError):
    """Raised when a MongoDB deployment does not match the expected document schema."""


@dataclass(frozen=True, slots=True)
class MongoValidation:
    database_kind: str
    current_version: int
    expected_version: int
    missing_collections: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return self.current_version == self.expected_version and not self.missing_collections


_COLLECTIONS = (
    "schema_versions",
    "schema_migrations",
    "users",
    "model_endpoints",
    "model_capabilities",
    "endpoint_rate_windows",
    "media_assets",
    "benchmark_definitions",
    "prompt_packages",
    "dataset_versions",
    "evaluation_runs",
    "task_units",
    "sample_attempts",
    "reports",
    "report_shares",
    "human_reviews",
    "judge_assessments",
    "audit_events",
)


# Collection references mirror the relational model while preserving JSON-like
# configuration and evidence fields as document subtrees.
_INDEXES: dict[str, tuple[tuple[Any, dict[str, Any]], ...]] = {
    "users": (
        ([("email", 1)], {"unique": True}),
        ([("api_token_hash", 1)], {"unique": True, "sparse": True}),
    ),
    "model_capabilities": (
        ((("model_endpoint_id", 1), ("capability_key", 1)), {"unique": True}),
    ),
    "endpoint_rate_windows": (
        ((("model_endpoint_id", 1), ("window_started_at", 1)), {"unique": True}),
    ),
    "media_assets": (
        ((("sha256", 1),), {"unique": True}),
    ),
    "benchmark_definitions": (
        ((("benchmark_id", 1), ("version", 1)), {"unique": True}),
    ),
    "prompt_packages": (
        ((("name", 1), ("version", 1)), {"unique": True}),
    ),
    "dataset_versions": (
        ((("dataset_id", 1), ("version", 1), ("revision", 1)), {"unique": True}),
    ),
    "report_shares": (
        ((("token_hash", 1),), {"unique": True}),
    ),
    "sample_attempts": (
        ((("run_id", 1), ("sample_id", 1), ("attempt_number", 1)), {"unique": True}),
        ((("run_id", 1), ("status", 1)), {}),
    ),
    "task_units": (
        ((("status", 1), ("next_retry_at", 1), ("priority", -1), ("created_at", 1)), {}),
    ),
}


class MongoDocumentStore:
    """Initializes MongoDB collections and provides atomic lease operations."""

    CURRENT_SCHEMA_VERSION = LATEST_SCHEMA_VERSION

    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        if settings.database_kind != "mongodb":
            raise MongoConfigurationError("MongoDocumentStore requires a MongoDB database URL.")
        self.settings = settings
        self.client = client or self._build_client()
        self.database = self.client[settings.mongodb_database_name]

    def _build_client(self) -> Any:
        try:
            from pymongo import MongoClient
        except ImportError as error:
            raise MongoConfigurationError(
                "MongoDB support requires the optional dependency: pip install '.[mongodb]'."
            ) from error
        return MongoClient(self.settings.database_url, serverSelectionTimeoutMS=5_000)

    def migration_preview(self) -> tuple[Migration, ...]:
        current_version = self._current_version()
        return tuple(migration for migration in MIGRATIONS if migration.version > current_version)

    def validate_schema(self) -> MongoValidation:
        collection_names = set(self.database.list_collection_names())
        missing_collections = tuple(sorted(set(_COLLECTIONS) - collection_names))
        return MongoValidation(
            database_kind="mongodb",
            current_version=self._current_version(),
            expected_version=self.CURRENT_SCHEMA_VERSION,
            missing_collections=missing_collections,
        )

    def initialize(self, mode: str = "auto_migrate") -> MongoValidation | tuple[Migration, ...]:
        selected_mode = mode.lower().strip()
        if selected_mode not in {"auto_migrate", "validate", "preview"}:
            raise MongoConfigurationError("Unsupported database initialization mode. Use auto_migrate, validate, or preview.")
        if selected_mode == "preview":
            return self.migration_preview()
        if selected_mode == "validate":
            validation = self.validate_schema()
            if not validation.is_valid:
                raise MongoValidationError(
                    f"MongoDB validation failed: version {validation.current_version}/{validation.expected_version}; "
                    f"missing collections: {', '.join(validation.missing_collections) or 'none'}."
                )
            return validation

        self.client.admin.command("ping")
        self._ensure_collections_and_indexes()
        current_version = self._current_version()
        for migration in MIGRATIONS:
            if migration.version <= current_version:
                continue
            self.database["schema_versions"].insert_one(
                {"_id": migration.version, "version": migration.version, "applied_at": _utc_now()}
            )
            self.database["schema_migrations"].insert_one(
                {
                    "_id": migration.version,
                    "version": migration.version,
                    "migration_id": migration.migration_id,
                    "description": migration.description,
                    "applied_at": _utc_now(),
                }
            )
            current_version = migration.version
        validation = self.validate_schema()
        if not validation.is_valid:
            raise MongoValidationError("MongoDB initialization completed but schema validation did not pass.")
        return validation

    def claim_task(
        self,
        *,
        worker_id: str,
        lease_seconds: int = 60,
        run_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Atomically claim one due task using MongoDB's find-and-update semantics."""

        now = _utc_now()
        query: dict[str, Any] = {
            "status": {"$in": ["pending", "retry_scheduled"]},
            "$or": [{"next_retry_at": {"$exists": False}}, {"next_retry_at": None}, {"next_retry_at": {"$lte": now}}],
        }
        if run_id is not None:
            query["run_id"] = run_id
        return self.database["task_units"].find_one_and_update(
            query,
            {
                "$set": {
                    "status": "leased",
                    "leased_by": worker_id,
                    "lease_token": str(uuid4()),
                    "lease_expires_at": now + timedelta(seconds=lease_seconds),
                    "heartbeat_at": now,
                    "updated_at": now,
                }
            },
            sort=[("priority", -1), ("created_at", 1)],
            return_document=_return_document_after(),
        )

    def reclaim_expired_leases(self) -> int:
        now = _utc_now()
        leased = self.database["task_units"].find(
            {"status": {"$in": ["leased", "running"]}, "lease_expires_at": {"$lt": now}},
            {"_id": 1},
        )
        task_ids = [document["_id"] for document in leased]
        if not task_ids:
            return 0
        self.database["task_units"].update_many(
            {"_id": {"$in": task_ids}},
            {
                "$set": {
                    "status": "pending",
                    "leased_by": None,
                    "lease_token": None,
                    "lease_expires_at": None,
                    "heartbeat_at": None,
                    "updated_at": now,
                }
            },
        )
        self.database["sample_attempts"].update_many(
            {"task_id": {"$in": task_ids}, "status": "running"},
            {"$set": {"status": "pending", "updated_at": now}},
        )
        return len(task_ids)

    def close(self) -> None:
        self.client.close()

    def _ensure_collections_and_indexes(self) -> None:
        existing = set(self.database.list_collection_names())
        for collection_name in _COLLECTIONS:
            if collection_name not in existing:
                self.database.create_collection(collection_name)
        for collection_name, definitions in _INDEXES.items():
            collection = self.database[collection_name]
            for keys, options in definitions:
                collection.create_index(keys, **options)

    def _current_version(self) -> int:
        document = self.database["schema_versions"].find_one(sort=[("version", -1)])
        version = document.get("version", 0) if isinstance(document, dict) else 0
        return int(version) if isinstance(version, int | float) else 0


def _return_document_after() -> Any:
    try:
        from pymongo import ReturnDocument
    except ImportError:
        return "after"
    return ReturnDocument.AFTER


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
