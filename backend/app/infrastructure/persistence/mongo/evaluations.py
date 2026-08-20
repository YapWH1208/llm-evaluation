from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.core.config import Settings
from app.db.mongo import MongoDocumentStore
from app.modules.datasets.preparation import DatasetError


class MongoEvaluationRepository:
    def __init__(self, store: MongoDocumentStore) -> None:
        self._store = store

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self._store.get_document("evaluation_runs", run_id)

    def list_runs(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        runs = self._store.list_documents("evaluation_runs", sort=[("created_at", -1)])
        return runs if include_archived else [run for run in runs if run.get("archived_at") is None]

    def update_run(self, run_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        return self._store.update_document("evaluation_runs", run_id, values)

    def update_tasks(
        self,
        run_id: str,
        *,
        statuses: Iterable[str],
        values: dict[str, Any],
        increment_lease_version: bool = False,
    ) -> int:
        selected = set(statuses)
        updated = 0
        for task in self._store.list_documents("task_units", query={"run_id": run_id}):
            if task.get("status") not in selected:
                continue
            persisted = dict(values)
            if increment_lease_version:
                persisted["lease_version"] = int(task.get("lease_version", 0)) + 1
            if self._store.update_document("task_units", str(task["id"]), persisted) is not None:
                updated += 1
        return updated

    def update_attempts(
        self,
        run_id: str,
        *,
        statuses: Iterable[str],
        values: dict[str, Any],
    ) -> int:
        selected = set(statuses)
        updated = 0
        for attempt in self._store.list_documents("sample_attempts", query={"run_id": run_id}):
            if attempt.get("status") not in selected:
                continue
            if self._store.update_document("sample_attempts", str(attempt["id"]), values) is not None:
                updated += 1
        return updated

    def list_tasks(self, run_id: str) -> list[dict[str, Any]]:
        return self._store.list_documents("task_units", query={"run_id": run_id}, sort=[("created_at", 1)])

    def list_attempts(self, run_id: str) -> list[dict[str, Any]]:
        return self._store.list_documents(
            "sample_attempts",
            query={"run_id": run_id},
            sort=[("sample_id", 1), ("attempt_number", 1)],
        )

    def list_reviews(self, attempt_ids: Iterable[str]) -> list[dict[str, Any]]:
        ids = tuple(attempt_ids)
        return self._store.list_documents("human_reviews", query={"sample_attempt_id": {"$in": ids}}) if ids else []

    def list_judge_assessments(self, attempt_ids: Iterable[str]) -> list[dict[str, Any]]:
        ids = tuple(attempt_ids)
        return self._store.list_documents("judge_assessments", query={"sample_attempt_id": {"$in": ids}}) if ids else []

    def list_metrics(self, run_id: str) -> list[dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for metric in self._store.list_documents(
            "aggregate_metrics",
            query={"run_id": run_id},
            sort=[("metric_name", 1), ("aggregation_version", -1)],
        ):
            latest.setdefault(str(metric["metric_name"]), metric)
        return list(latest.values())

    def replace_metrics(self, run_id: str, values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self._store.delete_documents("aggregate_metrics", {"run_id": run_id})
        return [self._store.insert_document("aggregate_metrics", item) for item in values]

    def get_endpoint(self, endpoint_id: str) -> dict[str, Any] | None:
        return self._store.get_document("model_endpoints", endpoint_id)

    def get_prompt_package(self, prompt_package_id: str) -> dict[str, Any] | None:
        return self._store.get_document("prompt_packages", prompt_package_id)

    def get_benchmark_definition(self, benchmark_id: str, benchmark_version: str) -> dict[str, Any] | None:
        definitions = self._store.list_documents(
            "benchmark_definitions",
            query={"benchmark_id": benchmark_id, "version": benchmark_version},
        )
        return definitions[0] if definitions else None

    def list_capabilities(self, endpoint_id: str) -> list[dict[str, Any]]:
        return self._store.list_documents("model_capabilities", query={"model_endpoint_id": endpoint_id})

    def get_dataset(self, dataset_version_id: str) -> dict[str, Any] | None:
        return self._store.get_document("dataset_versions", dataset_version_id)

    def get_media_asset(self, asset_id: str) -> dict[str, Any] | None:
        return self._store.get_document("media_assets", asset_id)

    def find_dataset(self, *, dataset_id: str, version: str | None, revision: str | None) -> dict[str, Any] | None:
        query: dict[str, Any] = {"dataset_id": dataset_id}
        if version is not None:
            query["version"] = version
        if revision is not None:
            query["revision"] = revision
        datasets = self._store.list_documents("dataset_versions", query=query, sort=[("created_at", -1)])
        return datasets[0] if datasets else None

    def create_dataset(self, values: dict[str, Any]) -> dict[str, Any]:
        return self._store.insert_document("dataset_versions", values)

    def get_suite(self, suite_id: str) -> dict[str, Any] | None:
        return self._store.get_document("evaluation_suites", suite_id)

    def list_suites(self) -> list[dict[str, Any]]:
        return self._store.list_documents("evaluation_suites", sort=[("created_at", -1)])

    def create_suite(self, values: dict[str, Any]) -> dict[str, Any]:
        if self._store.list_documents(
            "evaluation_suites",
            query={"name": values["name"], "version": values["version"]},
        ):
            raise ValueError("Suite name and version already exist")
        return self._store.insert_document("evaluation_suites", values)

    def update_suite(self, suite_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        return self._store.update_document("evaluation_suites", suite_id, values)

    def create_run_graph(
        self,
        run_values: dict[str, Any],
        tasks: list[dict[str, Any]],
        attempts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        run = self._store.insert_document("evaluation_runs", run_values)
        task_ids: dict[str, str] = {}
        for specification in tasks:
            values = dict(specification)
            key = str(values.pop("key"))
            parent_key = values.pop("parent_key", None)
            task = self._store.insert_document(
                "task_units",
                {
                    "run_id": run["id"],
                    "parent_task_id": task_ids.get(str(parent_key)) if parent_key else None,
                    **values,
                },
            )
            task_ids[key] = str(task["id"])
        for specification in attempts:
            values = dict(specification)
            task_key = str(values.pop("task_key"))
            self._store.insert_document(
                "sample_attempts",
                {"run_id": run["id"], "task_id": task_ids[task_key], **values},
            )
        return run

    def append_run_graph(
        self,
        run_id: str,
        tasks: list[dict[str, Any]],
        attempts: list[dict[str, Any]],
    ) -> None:
        task_ids: dict[str, str] = {}
        for specification in tasks:
            values = dict(specification)
            key = str(values.pop("key"))
            parent_key = values.pop("parent_key", None)
            parent_id = values.pop("parent_id", None)
            task = self._store.insert_document(
                "task_units",
                {
                    "run_id": run_id,
                    "parent_task_id": parent_id or (task_ids.get(str(parent_key)) if parent_key else None),
                    **values,
                },
            )
            task_ids[key] = str(task["id"])
        for specification in attempts:
            values = dict(specification)
            task_key = str(values.pop("task_key"))
            self._store.insert_document(
                "sample_attempts",
                {"run_id": run_id, "task_id": task_ids[task_key], **values},
            )

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return self._store.get_document("task_units", task_id)

    def claim_task(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
        run_id: str | None = None,
        system_max_concurrency: int | None = None,
        worker_max_concurrency: int | None = None,
    ) -> dict[str, Any] | None:
        return self._store.claim_task(
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            run_id=run_id,
            system_max_concurrency=system_max_concurrency,
            worker_max_concurrency=worker_max_concurrency,
        )

    def heartbeat_task(self, task_id: str, lease_token: str, lease_seconds: int) -> dict[str, Any] | None:
        return self._store.heartbeat_task(
            task_id=task_id,
            lease_token=lease_token,
            lease_seconds=lease_seconds,
        )

    def reclaim_expired_leases(self) -> int:
        return self._store.reclaim_expired_leases()

    def update_run_if(
        self,
        run_id: str,
        *,
        statuses: Iterable[str],
        values: dict[str, Any],
    ) -> dict[str, Any] | None:
        return self._store.update_document_if(
            "evaluation_runs",
            run_id,
            {"status": {"$in": tuple(statuses)}},
            values,
        )

    def update_task_for_lease(
        self,
        task_id: str,
        lease_token: str,
        values: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        task = self._store.get_document("task_units", task_id)
        if task is None:
            return None
        return self._store.update_task_if_current_lease(task, lease_token, values)

    def create_task(self, values: dict[str, Any]) -> dict[str, Any]:
        return self._store.insert_document("task_units", values)

    def create_attempt(self, values: dict[str, Any]) -> dict[str, Any]:
        return self._store.insert_document("sample_attempts", values)

    def begin_attempt(self, attempt_id: str, lease_token: str, values: dict[str, Any]) -> dict[str, Any] | None:
        return self._store.update_document_if(
            "sample_attempts",
            attempt_id,
            {"status": "pending"},
            {**values, "worker_lease_token": lease_token},
        )

    def complete_attempt(
        self,
        attempt_id: str,
        lease_token: str,
        values: dict[str, Any],
    ) -> dict[str, Any] | None:
        return self._store.update_document_if(
            "sample_attempts",
            attempt_id,
            {"status": "running", "worker_lease_token": lease_token},
            {**values, "worker_lease_token": None},
        )

    def update_attempt(self, attempt_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        return self._store.update_document("sample_attempts", attempt_id, values)

    def prepare_dataset(self, descriptor: dict[str, Any], data_root: str, settings: Settings | None) -> None:
        from app.modules.datasets.repositories import MongoDatasetRepository
        from app.modules.datasets.service import DatasetService

        frozen_id = descriptor.get("dataset_version_id")
        if isinstance(frozen_id, str):
            dataset = self._store.get_document("dataset_versions", frozen_id)
        else:
            query = {"dataset_id": descriptor["dataset_id"]}
            if isinstance(descriptor.get("version"), str):
                query["version"] = descriptor["version"]
            if isinstance(descriptor.get("revision"), str):
                query["revision"] = descriptor["revision"]
            matches = self._store.list_documents("dataset_versions", query=query, sort=[("created_at", -1)])
            dataset = matches[0] if matches else None
        if dataset is None:
            raise DatasetError(f"Required dataset {descriptor['dataset_id']} is not registered.")
        if dataset.get("status") != "ready":
            DatasetService(MongoDatasetRepository(self._store)).download(str(dataset["id"]), data_root, settings)

    def query_tasks(
        self,
        *,
        run_id: str | None,
        status: str | None,
        offset: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if run_id:
            query["run_id"] = run_id
        if status:
            query["status"] = status
        return self._store.list_documents(
            "task_units",
            query=query,
            sort=[("priority", -1), ("created_at", 1)],
            offset=offset,
            limit=limit,
        )

    def update_task_priority(self, task_id: str, priority: int) -> dict[str, Any] | None:
        return self._store.update_document("task_units", task_id, {"priority": priority})

    def queue_snapshot(self) -> dict[str, Any]:
        active_query = {"status": {"$in": ["leased", "running"]}}
        workers = self._store.distinct_values("task_units", "leased_by", active_query)
        errors = self._store.list_documents(
            "task_units",
            query={"status": "failed"},
            sort=[("updated_at", -1)],
            limit=20,
            projection={"id": 1, "run_id": 1, "payload": 1},
        )
        return {
            "queue": {
                "pending": self._store.count_documents(
                    "task_units", {"status": {"$in": ["pending", "retry_scheduled"]}}
                ),
                "active": self._store.count_documents("task_units", active_query),
            },
            "workers": sorted(str(worker) for worker in workers if worker),
            "errors": [
                {
                    "task_id": task["id"],
                    "run_id": task["run_id"],
                    "retry_exhausted_reason": (task.get("payload") or {}).get("retry_exhausted_reason"),
                }
                for task in errors
            ],
        }

    def find_previous_completed_run(self, run: dict[str, Any]) -> dict[str, Any] | None:
        candidates = [
            item
            for item in self._store.list_documents("evaluation_runs", sort=[("created_at", -1)])
            if item.get("id") != run["id"]
            and item.get("model_endpoint_id") == run["model_endpoint_id"]
            and item.get("benchmark_id") == run["benchmark_id"]
            and item.get("benchmark_version") == run["benchmark_version"]
            and item.get("status") in {"completed", "completed_with_errors"}
            and item.get("created_at") < run["created_at"]
        ]
        return candidates[0] if candidates else None

    def delete_run(self, run_id: str) -> list[str]:
        attempts = self.list_attempts(run_id)
        reports = self._store.list_documents("reports", query={"run_id": run_id})
        attempt_ids = [str(item["id"]) for item in attempts]
        report_ids = [str(item["id"]) for item in reports]
        if attempt_ids:
            self._store.delete_documents("human_reviews", {"sample_attempt_id": {"$in": attempt_ids}})
            self._store.delete_documents("judge_assessments", {"sample_attempt_id": {"$in": attempt_ids}})
            self._store.delete_documents("judge_assessments", {"comparison_sample_attempt_id": {"$in": attempt_ids}})
        if report_ids:
            self._store.delete_documents("report_shares", {"report_id": {"$in": report_ids}})
        self._store.delete_documents("task_units", {"run_id": run_id})
        self._store.delete_documents("sample_attempts", {"run_id": run_id})
        self._store.delete_documents("aggregate_metrics", {"run_id": run_id})
        self._store.delete_documents("reports", {"run_id": run_id})
        self._store.delete_document("evaluation_runs", run_id)
        return [str(report["artifact_path"]) for report in reports if isinstance(report.get("artifact_path"), str)]
