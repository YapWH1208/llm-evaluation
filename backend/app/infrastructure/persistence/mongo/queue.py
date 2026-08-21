from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from app.db.mongo import MongoDocumentStore


class MongoQueueStore:
    """MongoDB atomic queue, lease, admission, and rate-window persistence."""

    def __init__(self, store: MongoDocumentStore) -> None:
        self._store = store
        self._database = store.database

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
        candidates = self._store.list_documents("task_units", query=query, sort=[("priority", -1), ("created_at", 1)])[
            :20
        ]
        for task in candidates:
            parent_task_id = task.get("parent_task_id")
            if parent_task_id:
                parent = self._store.get_document("task_units", str(parent_task_id))
                if parent is None or parent.get("status") != "succeeded":
                    continue
            if not task.get("run_id"):
                document = self._lease_task(task, query, worker_id, lease_seconds, now)
                if document is not None:
                    return document
                continue
            run = self._store.get_document("evaluation_runs", str(task["run_id"]))
            if run is None:
                continue
            endpoint = self._store.get_document("model_endpoints", str(run["model_endpoint_id"]))
            if endpoint is None or not self._has_execution_capacity(
                run=run,
                endpoint=endpoint,
                worker_id=worker_id,
                system_max_concurrency=system_max_concurrency,
                worker_max_concurrency=worker_max_concurrency,
            ):
                continue
            if not self._reserve_endpoint_budget(endpoint=endpoint, task=task, now=now):
                continue
            document = self._lease_task(task, query, worker_id, lease_seconds, now)
            if document is not None:
                return document
        return None

    def _lease_task(
        self,
        task: dict[str, Any],
        query: dict[str, Any],
        worker_id: str,
        lease_seconds: int,
        now: datetime,
    ) -> dict[str, Any] | None:
        lease_version = int(task.get("lease_version", 0))
        document = self._database["task_units"].find_one_and_update(
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
            return_document=True,
        )
        return _public_document(document) if isinstance(document, dict) else None

    def _has_execution_capacity(
        self,
        *,
        run: dict[str, Any],
        endpoint: dict[str, Any],
        worker_id: str,
        system_max_concurrency: int | None,
        worker_max_concurrency: int | None,
    ) -> bool:
        active = self._store.list_documents("task_units", query={"status": {"$in": ["leased", "running"]}})
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
        active_runs = [
            self._store.get_document("evaluation_runs", str(active_task["run_id"])) for active_task in active
        ]
        fingerprint = endpoint.get("api_key_fingerprint")
        credential_limit = _positive_limit(endpoint.get("api_key_max_concurrency"))
        if fingerprint and credential_limit is not None:
            active_endpoints = [
                self._store.get_document("model_endpoints", str(item["model_endpoint_id"]))
                for item in active_runs
                if item
            ]
            if (
                sum(item is not None and item.get("api_key_fingerprint") == fingerprint for item in active_endpoints)
                >= credential_limit
            ):
                return False
        definitions = self._store.list_documents(
            "benchmark_definitions", query={"benchmark_id": run["benchmark_id"], "version": run["benchmark_version"]}
        )
        manifest = definitions[0].get("manifest") if definitions else {}
        benchmark_limit = _positive_limit(manifest.get("max_concurrency") if isinstance(manifest, dict) else None)
        if benchmark_limit is not None and (
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
        second_rows = self._store.list_documents(
            "endpoint_second_rate_windows",
            query={"model_endpoint_id": endpoint_id, "window_started_at": second_started_at},
        )
        minute_rows = self._store.list_documents(
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
            self._store.insert_document(
                "endpoint_second_rate_windows",
                {
                    "model_endpoint_id": endpoint_id,
                    "window_started_at": second_started_at,
                    "request_count": request_count,
                },
            )
        else:
            self._store.update_document(
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
            self._store.insert_document(
                "endpoint_rate_windows",
                {"model_endpoint_id": endpoint_id, "window_started_at": minute_started_at, **values},
            )
        else:
            self._store.update_document("endpoint_rate_windows", str(minute_row["id"]), values)
        return True

    def heartbeat_task(
        self,
        *,
        task_id: str,
        lease_token: str,
        lease_seconds: int = 60,
    ) -> dict[str, Any] | None:
        now = _utc_now()
        current = self._database["task_units"].find_one({"_id": task_id})
        if not isinstance(current, dict):
            return None
        lease_version = int(current.get("lease_version", 0))
        document = self._database["task_units"].find_one_and_update(
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
            return_document=True,
        )
        return _public_document(document) if isinstance(document, dict) else None

    def update_task_if_current_lease(
        self, task: dict[str, Any], lease_token: str, values: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Apply a task transition only for the exact active lease generation."""

        now = _utc_now()
        lease_version = int(task.get("lease_version", 0))
        return self._store.update_document_if(
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
        leased = self._database["task_units"].find(
            {"status": {"$in": ["leased", "running"]}, "lease_expires_at": {"$lt": now}},
        )
        task_ids: list[str] = []
        for task in leased:
            lease_version = int(task.get("lease_version", 0))
            reclaimed = self._database["task_units"].find_one_and_update(
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
                return_document=True,
            )
            if isinstance(reclaimed, dict):
                task_ids.append(str(task["_id"]))
        if not task_ids:
            return 0
        self._database["sample_attempts"].update_many(
            {"task_id": {"$in": task_ids}, "status": "running"},
            {"$set": {"status": "pending", "updated_at": now}},
        )
        return len(task_ids)

    def _acquire_admission_lock(self) -> str | None:
        now = _utc_now()
        owner = str(uuid4())
        document = self._database["queue_admission_locks"].find_one_and_update(
            {
                "_id": "global",
                "$or": [
                    {"locked_until": {"$exists": False}},
                    {"locked_until": None},
                    {"locked_until": {"$lte": now}},
                ],
            },
            {"$set": {"owner": owner, "locked_until": now + timedelta(seconds=30), "updated_at": now}},
            return_document=True,
        )
        return owner if isinstance(document, dict) and document.get("owner") == owner else None

    def _release_admission_lock(self, owner: str) -> None:
        now = _utc_now()
        self._database["queue_admission_locks"].find_one_and_update(
            {"_id": "global", "owner": owner},
            {"$set": {"owner": None, "locked_until": now, "updated_at": now}},
            return_document=True,
        )


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
