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
    "endpoint_second_rate_windows",
    "media_assets",
    "benchmark_definitions",
    "prompt_packages",
    "dataset_versions",
    "evaluation_suites",
    "evaluation_runs",
    "task_units",
    "sample_attempts",
    "aggregate_metrics",
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
    "model_endpoints": (
        ((("api_key_fingerprint", 1),), {"sparse": True}),
    ),
    "endpoint_rate_windows": (
        ((("model_endpoint_id", 1), ("window_started_at", 1)), {"unique": True}),
    ),
    "endpoint_second_rate_windows": (
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
    "evaluation_suites": (
        ((("name", 1), ("version", 1)), {"unique": True}),
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
    "aggregate_metrics": (
        ((("run_id", 1), ("metric_name", 1), ("aggregation_version", 1)), {"unique": True}),
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
        system_max_concurrency: int | None = None,
        worker_max_concurrency: int | None = None,
    ) -> dict[str, Any] | None:
        """Atomically claim one due task after applying every admission ceiling."""

        self.reclaim_expired_leases()
        now = _utc_now()
        query: dict[str, Any] = {
            "status": {"$in": ["pending", "retry_scheduled"]},
            "$or": [{"next_retry_at": {"$exists": False}}, {"next_retry_at": None}, {"next_retry_at": {"$lte": now}}],
        }
        if run_id is not None:
            query["run_id"] = run_id
        candidates = self.list_documents("task_units", query=query, sort=[("priority", -1), ("created_at", 1)])[:20]
        for task in candidates:
            if not task.get("run_id"):
                document = self.database["task_units"].find_one_and_update(
                    {"_id": task["id"], **query},
                    {"$set": {"status": "leased", "leased_by": worker_id, "lease_token": str(uuid4()), "lease_expires_at": now + timedelta(seconds=lease_seconds), "heartbeat_at": now, "updated_at": now}},
                    return_document=_return_document_after(),
                )
                if isinstance(document, dict):
                    return _public_document(document)
                continue
            run = self.get_document("evaluation_runs", str(task["run_id"]))
            if run is None:
                continue
            endpoint = self.get_document("model_endpoints", str(run["model_endpoint_id"]))
            if endpoint is None or not self._has_execution_capacity(
                task=task,
                run=run,
                endpoint=endpoint,
                worker_id=worker_id,
                system_max_concurrency=system_max_concurrency,
                worker_max_concurrency=worker_max_concurrency,
            ):
                continue
            if not self._reserve_endpoint_budget(endpoint=endpoint, task=task, now=now):
                continue
            document = self.database["task_units"].find_one_and_update(
                {"_id": task["id"], **query},
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
                return_document=_return_document_after(),
            )
            if isinstance(document, dict):
                return _public_document(document)
        return None

    def _has_execution_capacity(
        self,
        *,
        task: dict[str, Any],
        run: dict[str, Any],
        endpoint: dict[str, Any],
        worker_id: str,
        system_max_concurrency: int | None,
        worker_max_concurrency: int | None,
    ) -> bool:
        active = self.list_documents("task_units", query={"status": {"$in": ["leased", "running"]}})
        if system_max_concurrency is not None and len(active) >= system_max_concurrency:
            return False
        if worker_max_concurrency is not None and sum(task.get("leased_by") == worker_id for task in active) >= worker_max_concurrency:
            return False
        run_limit = _positive_limit(run.get("max_concurrency"))
        if run_limit is not None and sum(task.get("run_id") == run["id"] for task in active) >= run_limit:
            return False
        active_runs = [self.get_document("evaluation_runs", str(active_task["run_id"])) for active_task in active]
        created_by = run.get("created_by")
        if created_by:
            user = self.get_document("users", str(created_by))
            user_limit = _positive_limit(user.get("max_concurrency")) if user else None
            if user_limit is not None:
                if sum(item is not None and item.get("created_by") == created_by for item in active_runs) >= user_limit:
                    return False
        fingerprint = endpoint.get("api_key_fingerprint")
        credential_limit = _positive_limit(endpoint.get("api_key_max_concurrency"))
        if fingerprint and credential_limit is not None:
            active_endpoints = [self.get_document("model_endpoints", str(item["model_endpoint_id"])) for item in active_runs if item]
            if sum(item is not None and item.get("api_key_fingerprint") == fingerprint for item in active_endpoints) >= credential_limit:
                return False
        definitions = self.list_documents("benchmark_definitions", query={"benchmark_id": run["benchmark_id"], "version": run["benchmark_version"]})
        manifest = definitions[0].get("manifest") if definitions else {}
        benchmark_limit = _positive_limit(manifest.get("max_concurrency") if isinstance(manifest, dict) else None)
        if benchmark_limit is not None:
            if sum(item is not None and item.get("benchmark_id") == run["benchmark_id"] and item.get("benchmark_version") == run["benchmark_version"] for item in active_runs) >= benchmark_limit:
                return False
        endpoint_limit = _positive_limit(endpoint.get("max_concurrency")) or 1
        return sum(item is not None and item.get("model_endpoint_id") == endpoint["id"] for item in active_runs) < endpoint_limit

    def _reserve_endpoint_budget(self, *, endpoint: dict[str, Any], task: dict[str, Any], now: datetime) -> bool:
        limits = ("requests_per_second", "requests_per_minute", "tokens_per_minute", "input_tokens_per_minute", "output_tokens_per_minute")
        if not any(_positive_limit(endpoint.get(name)) is not None for name in limits):
            return True
        request_count, estimated_tokens, estimated_input_tokens, estimated_output_tokens = _task_budget(task)
        second_started_at = int(now.timestamp())
        minute_started_at = int(now.timestamp() // 60) * 60
        endpoint_id = str(endpoint["id"])
        second_rows = self.list_documents("endpoint_second_rate_windows", query={"model_endpoint_id": endpoint_id, "window_started_at": second_started_at})
        minute_rows = self.list_documents("endpoint_rate_windows", query={"model_endpoint_id": endpoint_id, "window_started_at": minute_started_at})
        second_row = second_rows[0] if second_rows else None
        minute_row = minute_rows[0] if minute_rows else None
        existing_requests = int(minute_row.get("request_count", 0)) if minute_row else 0
        existing_tokens = int(minute_row.get("estimated_token_count", 0)) if minute_row else 0
        existing_input = int(minute_row.get("estimated_input_token_count", 0)) if minute_row else 0
        existing_output = int(minute_row.get("estimated_output_token_count", 0)) if minute_row else 0
        existing_second = int(second_row.get("request_count", 0)) if second_row else 0
        if (_positive_limit(endpoint.get("requests_per_second")) is not None and existing_second + request_count > int(endpoint["requests_per_second"])):
            return False
        if (_positive_limit(endpoint.get("requests_per_minute")) is not None and existing_requests + request_count > int(endpoint["requests_per_minute"])):
            return False
        if (_positive_limit(endpoint.get("tokens_per_minute")) is not None and existing_tokens + estimated_tokens > int(endpoint["tokens_per_minute"])):
            return False
        if (_positive_limit(endpoint.get("input_tokens_per_minute")) is not None and existing_input + estimated_input_tokens > int(endpoint["input_tokens_per_minute"])):
            return False
        if (_positive_limit(endpoint.get("output_tokens_per_minute")) is not None and existing_output + estimated_output_tokens > int(endpoint["output_tokens_per_minute"])):
            return False
        if second_row is None:
            self.insert_document("endpoint_second_rate_windows", {"model_endpoint_id": endpoint_id, "window_started_at": second_started_at, "request_count": request_count})
        else:
            self.update_document("endpoint_second_rate_windows", str(second_row["id"]), {"request_count": existing_second + request_count})
        values = {"request_count": existing_requests + request_count, "estimated_token_count": existing_tokens + estimated_tokens, "estimated_input_token_count": existing_input + estimated_input_tokens, "estimated_output_token_count": existing_output + estimated_output_tokens}
        if minute_row is None:
            self.insert_document("endpoint_rate_windows", {"model_endpoint_id": endpoint_id, "window_started_at": minute_started_at, **values})
        else:
            self.update_document("endpoint_rate_windows", str(minute_row["id"]), values)
        return True

    def heartbeat_task(
        self,
        *,
        task_id: str,
        lease_token: str,
        lease_seconds: int = 60,
    ) -> dict[str, Any] | None:
        now = _utc_now()
        document = self.database["task_units"].find_one_and_update(
            {
                "_id": task_id,
                "lease_token": lease_token,
                "status": {"$in": ["leased", "running"]},
                "lease_expires_at": {"$gte": now},
            },
            {
                "$set": {
                    "heartbeat_at": now,
                    "lease_expires_at": now + timedelta(seconds=lease_seconds),
                    "updated_at": now,
                }
            },
            return_document=_return_document_after(),
        )
        return _public_document(document) if isinstance(document, dict) else None

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
    ) -> list[dict[str, Any]]:
        cursor = self.database[collection_name].find(query or {})
        if sort:
            cursor = cursor.sort(sort)
        return [_public_document(document) for document in cursor]

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


def _return_document_after() -> bool:
    """Request the post-update document without importing PyMongo's client package.

    PyMongo defines ``ReturnDocument.AFTER`` as the boolean ``True``.  Using the
    documented value directly keeps the document-store adapter usable when an
    optional TLS integration prevents importing the top-level PyMongo package.
    """

    return True


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _positive_limit(value: object) -> int | None:
    try:
        limit = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return limit if limit > 0 else None


def _task_budget(task: dict[str, Any]) -> tuple[int, int, int, int]:
    payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
    sample_ids = payload.get("retry_sample_ids") or payload.get("sample_ids") or []
    fallback_requests = len([item for item in sample_ids if isinstance(item, str)])
    try:
        request_count = max(1, int(payload.get("estimated_request_count", fallback_requests)))
    except (TypeError, ValueError):
        request_count = max(1, fallback_requests)
    try:
        estimated_tokens = max(0, int(payload.get("estimated_token_count", 0)))
    except (TypeError, ValueError):
        estimated_tokens = 0
    if payload.get("retry_sample_ids"):
        estimated_tokens = max(1, estimated_tokens // max(1, fallback_requests))
        request_count = fallback_requests
    estimated_output_tokens = min(estimated_tokens, request_count * 32)
    return request_count, estimated_tokens, max(0, estimated_tokens - estimated_output_tokens), estimated_output_tokens


def _public_document(document: dict[str, Any]) -> dict[str, Any]:
    value = dict(document)
    value["id"] = str(value.get("id") or value.get("_id"))
    value.pop("_id", None)
    return value
