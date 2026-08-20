from __future__ import annotations

"""MongoDB connection, schema validation, and normalized document primitives."""

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
    missing_indexes: tuple[str, ...] = ()
    missing_validators: tuple[str, ...] = ()
    missing_migrations: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return (
            self.current_version == self.expected_version
            and not self.missing_collections
            and not self.missing_indexes
            and not self.missing_validators
            and not self.missing_migrations
        )


_COLLECTIONS = (
    "schema_versions",
    "schema_migrations",
    "model_endpoints",
    "model_capabilities",
    "endpoint_rate_windows",
    "endpoint_second_rate_windows",
    "media_assets",
    "benchmark_definitions",
    "prompt_packages",
    "dataset_versions",
    "evaluation_suites",
    "evaluation_runs",
    "task_units",
    "queue_admission_locks",
    "sample_attempts",
    "aggregate_metrics",
    "reports",
    "report_shares",
    "report_share_password_attempts",
    "human_reviews",
    "judge_assessments",
)


# Collection references mirror the relational model while preserving JSON-like
# configuration and evidence fields as document subtrees.
_INDEXES: dict[str, tuple[tuple[Any, dict[str, Any]], ...]] = {
    "model_capabilities": (((("model_endpoint_id", 1), ("capability_key", 1)), {"unique": True}),),
    "model_endpoints": (((("api_key_fingerprint", 1),), {"sparse": True}),),
    "endpoint_rate_windows": (((("model_endpoint_id", 1), ("window_started_at", 1)), {"unique": True}),),
    "endpoint_second_rate_windows": (((("model_endpoint_id", 1), ("window_started_at", 1)), {"unique": True}),),
    "media_assets": (((("sha256", 1),), {"unique": True}),),
    "benchmark_definitions": (((("benchmark_id", 1), ("version", 1)), {"unique": True}),),
    "prompt_packages": (((("name", 1), ("version", 1)), {"unique": True}),),
    "dataset_versions": (((("dataset_id", 1), ("version", 1), ("revision", 1)), {"unique": True}),),
    "evaluation_suites": (((("name", 1), ("version", 1)), {"unique": True}),),
    "report_shares": (((("token_hash", 1),), {"unique": True}),),
    "report_share_password_attempts": (
        ((("share_id", 1), ("client_key", 1)), {"unique": True}),
        ((("expires_at", 1),), {"expireAfterSeconds": 0}),
    ),
    "sample_attempts": (
        ((("run_id", 1), ("sample_id", 1), ("attempt_number", 1)), {"unique": True}),
        ((("run_id", 1), ("status", 1)), {}),
    ),
    "task_units": (((("status", 1), ("next_retry_at", 1), ("priority", -1), ("created_at", 1)), {}),),
    "aggregate_metrics": (((("run_id", 1), ("metric_name", 1), ("aggregation_version", 1)), {"unique": True}),),
}

_VALIDATOR_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "schema_versions": ("version", "applied_at"),
    "schema_migrations": ("version", "migration_id", "description", "applied_at"),
    "model_endpoints": ("id", "base_url", "model_name", "status", "created_at"),
    "model_capabilities": ("id", "model_endpoint_id", "capability_key"),
    "endpoint_rate_windows": ("id", "model_endpoint_id", "window_started_at"),
    "endpoint_second_rate_windows": ("id", "model_endpoint_id", "window_started_at"),
    "media_assets": ("id", "sha256", "mime_type", "created_at"),
    "benchmark_definitions": ("id", "benchmark_id", "version", "manifest", "created_at"),
    "prompt_packages": ("id", "name", "version", "created_at"),
    "dataset_versions": ("id", "dataset_id", "version", "revision", "status", "created_at"),
    "evaluation_suites": ("id", "name", "version", "created_at"),
    "evaluation_runs": ("id", "model_endpoint_id", "status", "created_at"),
    "task_units": ("id", "run_id", "task_type", "status", "priority", "created_at"),
    "queue_admission_locks": ("id", "owner", "locked_until"),
    "sample_attempts": ("id", "run_id", "sample_id", "status", "created_at"),
    "aggregate_metrics": ("id", "run_id", "metric_name", "created_at"),
    "reports": ("id", "run_id", "format", "artifact_path", "generated_at"),
    "report_shares": ("id", "report_id", "token_hash", "expires_at", "created_at"),
    "report_share_password_attempts": ("id", "share_id", "client_key", "failure_count", "expires_at"),
    "human_reviews": ("id", "sample_attempt_id", "reviewer_id", "created_at"),
    "judge_assessments": ("id", "sample_attempt_id", "judge_endpoint_id", "status", "created_at"),
    "audit_events": ("id", "action", "entity_type", "created_at"),
}
_VALIDATORS = {
    name: {"$jsonSchema": {"bsonType": "object", "required": list(required)}}
    for name, required in _VALIDATOR_REQUIRED_FIELDS.items()
}


class MongoDocumentStore:
    """Initialize MongoDB and expose normalized document persistence primitives."""

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
        missing_indexes: list[str] = []
        missing_validators: list[str] = []
        for collection_name, definitions in _INDEXES.items():
            if collection_name not in collection_names:
                continue
            existing_indexes = _existing_index_signatures(self.database[collection_name])
            for keys, _options in definitions:
                if _index_signature(keys) not in existing_indexes:
                    missing_indexes.append(f"{collection_name}.{_index_name(keys)}")
        for collection_name, validator in _VALIDATORS.items():
            if (
                collection_name in collection_names
                and _collection_validator(self.database[collection_name]) != validator
            ):
                missing_validators.append(collection_name)
        applied = (
            {
                int(document.get("version", 0)): str(document.get("migration_id", ""))
                for document in self.database["schema_migrations"].find({})
                if isinstance(document, dict)
            }
            if "schema_migrations" in collection_names
            else {}
        )
        missing_migrations = [
            migration.migration_id
            for migration in MIGRATIONS
            if applied.get(migration.version) != migration.migration_id
        ]
        return MongoValidation(
            database_kind="mongodb",
            current_version=self._current_version(),
            expected_version=self.CURRENT_SCHEMA_VERSION,
            missing_collections=missing_collections,
            missing_indexes=tuple(sorted(missing_indexes)),
            missing_validators=tuple(sorted(missing_validators)),
            missing_migrations=tuple(sorted(missing_migrations)),
        )

    def initialize(self, mode: str = "auto_migrate") -> MongoValidation | tuple[Migration, ...]:
        selected_mode = mode.lower().strip()
        if selected_mode not in {"auto_migrate", "validate", "preview"}:
            raise MongoConfigurationError(
                "Unsupported database initialization mode. Use auto_migrate, validate, or preview."
            )
        if selected_mode == "preview":
            return self.migration_preview()
        if selected_mode == "validate":
            validation = self.validate_schema()
            if not validation.is_valid:
                raise MongoValidationError(
                    f"MongoDB validation failed: version {validation.current_version}/{validation.expected_version}; "
                    f"missing collections: {', '.join(validation.missing_collections) or 'none'}; "
                    f"missing indexes: {', '.join(validation.missing_indexes) or 'none'}; "
                    f"missing validators: {', '.join(validation.missing_validators) or 'none'}; "
                    f"missing migrations: {', '.join(validation.missing_migrations) or 'none'}."
                )
            return validation

        self.client.admin.command("ping")
        migration_ledger_existed = "schema_migrations" in set(self.database.list_collection_names())
        self._ensure_collections_and_indexes()
        current_version = self._current_version()
        # Older Mongo installations track completed versions but do not have
        # the later migration ledger collection. Backfill its canonical rows
        # before recording new versions, without replaying historical work.
        if not migration_ledger_existed:
            for migration in MIGRATIONS:
                if migration.version > current_version:
                    break
                self.database["schema_migrations"].insert_one(
                    {
                        "_id": migration.version,
                        "version": migration.version,
                        "migration_id": migration.migration_id,
                        "description": migration.description,
                        "applied_at": _utc_now(),
                    }
                )
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
            raise MongoValidationError(
                "MongoDB initialization completed but schema validation did not pass: "
                f"collections={', '.join(validation.missing_collections) or 'none'}; "
                f"indexes={', '.join(validation.missing_indexes) or 'none'}; "
                f"validators={', '.join(validation.missing_validators) or 'none'}; "
                f"migrations={', '.join(validation.missing_migrations) or 'none'}."
            )
        return validation

    def insert_document(self, collection_name: str, document: dict[str, Any]) -> dict[str, Any]:
        """Insert a normalized platform document and return the persisted mapping."""

        value = dict(document)
        value.setdefault("_id", value.get("id") or str(uuid4()))
        value.setdefault("id", str(value["_id"]))
        self.database[collection_name].insert_one(value)
        return _public_document(value)

    def get_document(self, collection_name: str, document_id: str) -> dict[str, Any] | None:
        document = self.database[collection_name].find_one({"_id": document_id})
        return _public_document(document) if isinstance(document, dict) else None

    def list_documents(
        self,
        collection_name: str,
        *,
        query: dict[str, Any] | None = None,
        sort: list[tuple[str, int]] | None = None,
        offset: int | None = None,
        limit: int | None = None,
        projection: dict[str, int] | None = None,
    ) -> list[dict[str, Any]]:
        cursor = (
            self.database[collection_name].find(query or {}, projection)
            if projection is not None
            else self.database[collection_name].find(query or {})
        )
        if sort:
            cursor = cursor.sort(sort)
        if offset:
            cursor = cursor.skip(offset) if hasattr(cursor, "skip") else cursor[offset:]
        if limit is not None:
            cursor = cursor.limit(limit) if hasattr(cursor, "limit") else cursor[:limit]
        return [_public_document(document) for document in cursor]

    def count_documents(self, collection_name: str, query: dict[str, Any] | None = None) -> int:
        collection = self.database[collection_name]
        count_documents = getattr(collection, "count_documents", None)
        if callable(count_documents):
            return int(count_documents(query or {}))
        return len(self.list_documents(collection_name, query=query))

    def distinct_values(
        self, collection_name: str, field: str, query: dict[str, Any] | None = None, *, limit: int = 500
    ) -> list[Any]:
        collection = self.database[collection_name]
        distinct = getattr(collection, "distinct", None)
        if callable(distinct):
            return list(distinct(field, query or {}))[:limit]
        return list(
            {
                item.get(field)
                for item in self.list_documents(collection_name, query=query, limit=limit)
                if item.get(field) is not None
            }
        )

    def update_document(
        self,
        collection_name: str,
        document_id: str,
        values: dict[str, Any],
    ) -> dict[str, Any] | None:
        document = self.database[collection_name].find_one_and_update(
            {"_id": document_id},
            {"$set": {**values, "updated_at": _utc_now()}},
            return_document=_return_document_after(),
        )
        return _public_document(document) if isinstance(document, dict) else None

    def update_document_if(
        self,
        collection_name: str,
        document_id: str,
        conditions: dict[str, Any],
        values: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Conditionally persist a document transition and return its post-image."""

        document = self.database[collection_name].find_one_and_update(
            {"_id": document_id, **conditions},
            {"$set": {**values, "updated_at": _utc_now()}},
            return_document=_return_document_after(),
        )
        return _public_document(document) if isinstance(document, dict) else None

    def report_share_password_attempt_limit_reached(
        self, *, share_id: str, client_key: str, now: datetime, limit: int
    ) -> bool:
        document = self.database["report_share_password_attempts"].find_one(
            {"share_id": share_id, "client_key": client_key, "expires_at": {"$gt": now}}
        )
        return bool(isinstance(document, dict) and int(document.get("failure_count", 0)) >= limit)

    def record_report_share_password_failure(
        self, *, share_id: str, client_key: str, now: datetime, window: timedelta, limit: int
    ) -> bool:
        """Atomically consume one permitted failure from a durable expiry window.

        The compare-and-increment predicate makes concurrent web workers stop at
        the configured limit; the TTL index removes expired MongoDB windows.
        """

        collection = self.database["report_share_password_attempts"]
        document = collection.find_one_and_update(
            {
                "share_id": share_id,
                "client_key": client_key,
                "expires_at": {"$gt": now},
                "failure_count": {"$lt": limit},
            },
            {"$inc": {"failure_count": 1}, "$set": {"updated_at": now}},
            return_document=_return_document_after(),
        )
        if isinstance(document, dict):
            return True
        document = collection.find_one_and_update(
            {
                "share_id": share_id,
                "client_key": client_key,
                "expires_at": {"$lte": now},
            },
            {
                "$set": {
                    "failure_count": 1,
                    "expires_at": now + window,
                    "updated_at": now,
                }
            },
            return_document=_return_document_after(),
        )
        if isinstance(document, dict):
            return True
        if self.report_share_password_attempt_limit_reached(
            share_id=share_id, client_key=client_key, now=now, limit=limit
        ):
            return False
        try:
            self.insert_document(
                "report_share_password_attempts",
                {
                    "share_id": share_id,
                    "client_key": client_key,
                    "failure_count": 1,
                    "expires_at": now + window,
                    "updated_at": now,
                },
            )
            return True
        except Exception as error:
            # A concurrent unique-index winner is the only recoverable insert
            # conflict. Re-check the shared row rather than masking DB failures.
            if type(error).__name__ != "DuplicateKeyError":
                raise
            return self.record_report_share_password_failure(
                share_id=share_id, client_key=client_key, now=now, window=window, limit=limit
            )

    def delete_document(self, collection_name: str, document_id: str) -> bool:
        result = self.database[collection_name].delete_one({"_id": document_id})
        return bool(getattr(result, "deleted_count", 0))

    def delete_documents(self, collection_name: str, query: dict[str, Any]) -> int:
        """Delete scoped documents for a completed cascading operation."""

        collection = self.database[collection_name]
        delete_many = getattr(collection, "delete_many", None)
        if callable(delete_many):
            result = delete_many(query)
            return int(getattr(result, "deleted_count", 0))
        document_ids = [str(item["id"]) for item in self.list_documents(collection_name, query=query)]
        return sum(self.delete_document(collection_name, document_id) for document_id in document_ids)

    def close(self) -> None:
        self.client.close()

    def _ensure_collections_and_indexes(self) -> None:
        existing = set(self.database.list_collection_names())
        for collection_name in _COLLECTIONS:
            if collection_name not in existing:
                self.database.create_collection(collection_name, validator=_VALIDATORS[collection_name])
            else:
                self._set_collection_validator(collection_name, _VALIDATORS[collection_name])
        for collection_name, definitions in _INDEXES.items():
            collection = self.database[collection_name]
            for keys, options in definitions:
                collection.create_index(keys, **options)
        lock = self.database["queue_admission_locks"]
        if lock.find_one({"_id": "global"}) is None:
            try:
                lock.insert_one(
                    {
                        "_id": "global",
                        "id": "global",
                        "owner": None,
                        "locked_until": datetime(1970, 1, 1, tzinfo=timezone.utc),
                    }
                )
            except Exception:
                pass

    def _set_collection_validator(self, collection_name: str, validator: dict[str, Any]) -> None:
        command = getattr(self.database, "command", None)
        if callable(command):
            command({"collMod": collection_name, "validator": validator})
            return
        collection = self.database[collection_name]
        if hasattr(collection, "validator"):
            collection.validator = validator

    def _current_version(self) -> int:
        document = self.database["schema_versions"].find_one(sort=[("version", -1)])
        version = document.get("version", 0) if isinstance(document, dict) else 0
        return int(version) if isinstance(version, int | float) else 0


def _index_signature(keys: Any) -> tuple[tuple[str, int], ...]:
    return tuple((str(key), int(direction)) for key, direction in keys)


def _index_name(keys: Any) -> str:
    return "_".join(f"{key}_{direction}" for key, direction in _index_signature(keys))


def _existing_index_signatures(collection: Any) -> set[tuple[tuple[str, int], ...]]:
    list_indexes = getattr(collection, "list_indexes", None)
    if callable(list_indexes):
        return {
            tuple((str(key), int(direction)) for key, direction in dict(index.get("key", {})).items())
            for index in list_indexes()
            if isinstance(index, dict)
        }
    return {_index_signature(keys) for keys, _options in getattr(collection, "indexes", ())}


def _collection_validator(collection: Any) -> dict[str, Any] | None:
    options = getattr(collection, "options", None)
    if callable(options):
        value = options()
        return value.get("validator") if isinstance(value, dict) else None
    value = getattr(collection, "validator", None)
    return value if isinstance(value, dict) else None


def _return_document_after() -> bool:
    """Request the post-update document without importing PyMongo's client package.

    PyMongo defines ``ReturnDocument.AFTER`` as the boolean ``True``.  Using the
    documented value directly keeps the document-store adapter usable when an
    optional TLS integration prevents importing the top-level PyMongo package.
    """

    return True


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _public_document(document: dict[str, Any]) -> dict[str, Any]:
    value = dict(document)
    value["id"] = str(value.get("id") or value.get("_id"))
    value.pop("_id", None)
    return value
