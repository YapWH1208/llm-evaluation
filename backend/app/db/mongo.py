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

        lock_owner = self._acquire_admission_lock()
        if lock_owner is None:
            return None
        try:
            return self._claim_task_locked(
                worker_id=worker_id,
                lease_seconds=lease_seconds,
                run_id=run_id,
                system_max_concurrency=system_max_concurrency,
                worker_max_concurrency=worker_max_concurrency,
            )
        finally:
            self._release_admission_lock(lock_owner)

    def _claim_task_locked(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
        run_id: str | None,
        system_max_concurrency: int | None,
        worker_max_concurrency: int | None,
    ) -> dict[str, Any] | None:
        self.reclaim_expired_leases(lock_held=True)
        now = _utc_now()
        query: dict[str, Any] = {
            "status": {"$in": ["pending", "retry_scheduled"]},
            "$or": [{"next_retry_at": {"$exists": False}}, {"next_retry_at": None}, {"next_retry_at": {"$lte": now}}],
        }
        if run_id is not None:
            query["run_id"] = run_id
        candidates = self.list_documents("task_units", query=query, sort=[("priority", -1), ("created_at", 1)])[:20]
        for task in candidates:
            parent_task_id = task.get("parent_task_id")
            if parent_task_id:
                parent = self.get_document("task_units", str(parent_task_id))
                if parent is None or parent.get("status") != "succeeded":
                    continue
            if not task.get("run_id"):
                lease_version = int(task.get("lease_version", 0))
                document = self.database["task_units"].find_one_and_update(
                    {"_id": task["id"], **query, **_lease_version_query(task, lease_version)},
                    {
                        "$set": {
                            "status": "leased",
                            "leased_by": worker_id,
                            "lease_token": str(uuid4()),
                            "lease_version": lease_version + 1,
                            "lease_expires_at": now + timedelta(seconds=lease_seconds),
                            "heartbeat_at": now,
                            "updated_at": now,
                        }
                    },
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
            lease_version = int(task.get("lease_version", 0))
            document = self.database["task_units"].find_one_and_update(
                {"_id": task["id"], **query, **_lease_version_query(task, lease_version)},
                {
                    "$set": {
                        "status": "leased",
                        "leased_by": worker_id,
                        "lease_token": str(uuid4()),
                        "lease_version": lease_version + 1,
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
        if (
            worker_max_concurrency is not None
            and sum(task.get("leased_by") == worker_id for task in active) >= worker_max_concurrency
        ):
            return False
        run_limit = _positive_limit(run.get("max_concurrency"))
        if run_limit is not None and sum(task.get("run_id") == run["id"] for task in active) >= run_limit:
            return False
        active_runs = [self.get_document("evaluation_runs", str(active_task["run_id"])) for active_task in active]
        fingerprint = endpoint.get("api_key_fingerprint")
        credential_limit = _positive_limit(endpoint.get("api_key_max_concurrency"))
        if fingerprint and credential_limit is not None:
            active_endpoints = [
                self.get_document("model_endpoints", str(item["model_endpoint_id"])) for item in active_runs if item
            ]
            if (
                sum(item is not None and item.get("api_key_fingerprint") == fingerprint for item in active_endpoints)
                >= credential_limit
            ):
                return False
        definitions = self.list_documents(
            "benchmark_definitions", query={"benchmark_id": run["benchmark_id"], "version": run["benchmark_version"]}
        )
        manifest = definitions[0].get("manifest") if definitions else {}
        benchmark_limit = _positive_limit(manifest.get("max_concurrency") if isinstance(manifest, dict) else None)
        if benchmark_limit is not None:
            if (
                sum(
                    item is not None
                    and item.get("benchmark_id") == run["benchmark_id"]
                    and item.get("benchmark_version") == run["benchmark_version"]
                    for item in active_runs
                )
                >= benchmark_limit
            ):
                return False
        endpoint_limit = _positive_limit(endpoint.get("max_concurrency")) or 1
        return (
            sum(item is not None and item.get("model_endpoint_id") == endpoint["id"] for item in active_runs)
            < endpoint_limit
        )

    def _reserve_endpoint_budget(self, *, endpoint: dict[str, Any], task: dict[str, Any], now: datetime) -> bool:
        if task.get("task_type") != "evaluation_shard":
            return True
        limits = (
            "requests_per_second",
            "requests_per_minute",
            "tokens_per_minute",
            "input_tokens_per_minute",
            "output_tokens_per_minute",
        )
        if not any(_positive_limit(endpoint.get(name)) is not None for name in limits):
            return True
        request_count, estimated_tokens, estimated_input_tokens, estimated_output_tokens = _task_budget(task)
        second_started_at = int(now.timestamp())
        minute_started_at = int(now.timestamp() // 60) * 60
        endpoint_id = str(endpoint["id"])
        second_rows = self.list_documents(
            "endpoint_second_rate_windows",
            query={"model_endpoint_id": endpoint_id, "window_started_at": second_started_at},
        )
        minute_rows = self.list_documents(
            "endpoint_rate_windows", query={"model_endpoint_id": endpoint_id, "window_started_at": minute_started_at}
        )
        second_row = second_rows[0] if second_rows else None
        minute_row = minute_rows[0] if minute_rows else None
        existing_requests = int(minute_row.get("request_count", 0)) if minute_row else 0
        existing_tokens = int(minute_row.get("estimated_token_count", 0)) if minute_row else 0
        existing_input = int(minute_row.get("estimated_input_token_count", 0)) if minute_row else 0
        existing_output = int(minute_row.get("estimated_output_token_count", 0)) if minute_row else 0
        existing_second = int(second_row.get("request_count", 0)) if second_row else 0
        if _positive_limit(endpoint.get("requests_per_second")) is not None and existing_second + request_count > int(
            endpoint["requests_per_second"]
        ):
            return False
        if _positive_limit(endpoint.get("requests_per_minute")) is not None and existing_requests + request_count > int(
            endpoint["requests_per_minute"]
        ):
            return False
        if _positive_limit(endpoint.get("tokens_per_minute")) is not None and existing_tokens + estimated_tokens > int(
            endpoint["tokens_per_minute"]
        ):
            return False
        if _positive_limit(
            endpoint.get("input_tokens_per_minute")
        ) is not None and existing_input + estimated_input_tokens > int(endpoint["input_tokens_per_minute"]):
            return False
        if _positive_limit(
            endpoint.get("output_tokens_per_minute")
        ) is not None and existing_output + estimated_output_tokens > int(endpoint["output_tokens_per_minute"]):
            return False
        if second_row is None:
            self.insert_document(
                "endpoint_second_rate_windows",
                {
                    "model_endpoint_id": endpoint_id,
                    "window_started_at": second_started_at,
                    "request_count": request_count,
                },
            )
        else:
            self.update_document(
                "endpoint_second_rate_windows",
                str(second_row["id"]),
                {"request_count": existing_second + request_count},
            )
        values = {
            "request_count": existing_requests + request_count,
            "estimated_token_count": existing_tokens + estimated_tokens,
            "estimated_input_token_count": existing_input + estimated_input_tokens,
            "estimated_output_token_count": existing_output + estimated_output_tokens,
        }
        if minute_row is None:
            self.insert_document(
                "endpoint_rate_windows",
                {"model_endpoint_id": endpoint_id, "window_started_at": minute_started_at, **values},
            )
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
        current = self.database["task_units"].find_one({"_id": task_id})
        if not isinstance(current, dict):
            return None
        lease_version = int(current.get("lease_version", 0))
        document = self.database["task_units"].find_one_and_update(
            {
                "_id": task_id,
                "lease_token": lease_token,
                **_lease_version_query(current, lease_version),
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

    def update_task_if_current_lease(
        self, task: dict[str, Any], lease_token: str, values: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Apply a task transition only for the exact active lease generation."""

        now = _utc_now()
        lease_version = int(task.get("lease_version", 0))
        return self.update_document_if(
            "task_units",
            str(task["id"]),
            {
                "lease_token": lease_token,
                **_lease_version_query(task, lease_version),
                "status": {"$in": ["leased", "running"]},
                "lease_expires_at": {"$gte": now},
            },
            {"heartbeat_at": now, **(values or {})},
        )

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

    def invalidate_run_tasks(self, run_id: str) -> int:
        """Fence every active task in a run before pause/cancel returns."""

        active = {"pending", "retry_scheduled", "leased", "running"}
        invalidated = 0
        now = _utc_now()
        for task in self.database["task_units"].find({"run_id": run_id, "status": {"$in": list(active)}}):
            lease_version = int(task.get("lease_version", 0))
            document = self.database["task_units"].find_one_and_update(
                {
                    "_id": task["_id"],
                    "status": {"$in": list(active)},
                    **_lease_version_query(task, lease_version),
                },
                {
                    "$set": {
                        "status": "cancelled",
                        "leased_by": None,
                        "lease_token": None,
                        "lease_expires_at": None,
                        "heartbeat_at": None,
                        "updated_at": now,
                    },
                    "$inc": {"lease_version": 1},
                },
                return_document=_return_document_after(),
            )
            if isinstance(document, dict):
                invalidated += 1
        return invalidated

    def reclaim_expired_leases(self, *, lock_held: bool = False) -> int:
        lock_owner = None if lock_held else self._acquire_admission_lock()
        if not lock_held and lock_owner is None:
            return 0
        try:
            return self._reclaim_expired_leases_locked()
        finally:
            if lock_owner is not None:
                self._release_admission_lock(lock_owner)

    def _reclaim_expired_leases_locked(self) -> int:
        now = _utc_now()
        leased = self.database["task_units"].find(
            {"status": {"$in": ["leased", "running"]}, "lease_expires_at": {"$lt": now}},
        )
        task_ids: list[str] = []
        for task in leased:
            lease_version = int(task.get("lease_version", 0))
            reclaimed = self.database["task_units"].find_one_and_update(
                {
                    "_id": task["_id"],
                    "status": {"$in": ["leased", "running"]},
                    "lease_expires_at": {"$lt": now},
                    **_lease_version_query(task, lease_version),
                },
                {
                    "$set": {
                        "status": "pending",
                        "leased_by": None,
                        "lease_token": None,
                        "lease_version": lease_version + 1,
                        "lease_expires_at": None,
                        "heartbeat_at": None,
                        "updated_at": now,
                    }
                },
                return_document=_return_document_after(),
            )
            if isinstance(reclaimed, dict):
                task_ids.append(str(task["_id"]))
        if not task_ids:
            return 0
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

    def _acquire_admission_lock(self) -> str | None:
        now = _utc_now()
        owner = str(uuid4())
        document = self.database["queue_admission_locks"].find_one_and_update(
            {
                "_id": "global",
                "$or": [
                    {"locked_until": {"$exists": False}},
                    {"locked_until": None},
                    {"locked_until": {"$lte": now}},
                ],
            },
            {"$set": {"owner": owner, "locked_until": now + timedelta(seconds=30), "updated_at": now}},
            return_document=_return_document_after(),
        )
        return owner if isinstance(document, dict) and document.get("owner") == owner else None

    def _release_admission_lock(self, owner: str) -> None:
        now = _utc_now()
        self.database["queue_admission_locks"].find_one_and_update(
            {"_id": "global", "owner": owner},
            {"$set": {"owner": None, "locked_until": now, "updated_at": now}},
            return_document=_return_document_after(),
        )

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
        per_sample = payload.get("sample_token_estimates")
        if isinstance(per_sample, dict):
            selected = [sample_id for sample_id in sample_ids if isinstance(sample_id, str)]
            selected_estimates = [per_sample.get(sample_id) for sample_id in selected]
            if all(
                isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in selected_estimates
            ):
                estimated_tokens = sum(int(value) for value in selected_estimates)
            else:
                estimated_tokens = max(1, estimated_tokens // max(1, request_count)) * fallback_requests
        else:
            estimated_tokens = max(1, estimated_tokens // max(1, request_count)) * fallback_requests
        request_count = fallback_requests
    estimated_output_tokens = min(estimated_tokens, request_count * 32)
    return request_count, estimated_tokens, max(0, estimated_tokens - estimated_output_tokens), estimated_output_tokens


def _lease_version_query(task: dict[str, Any], lease_version: int) -> dict[str, Any]:
    return {"lease_version": lease_version} if "lease_version" in task else {"lease_version": {"$exists": False}}


def _public_document(document: dict[str, Any]) -> dict[str, Any]:
    value = dict(document)
    value["id"] = str(value.get("id") or value.get("_id"))
    value.pop("_id", None)
    return value
