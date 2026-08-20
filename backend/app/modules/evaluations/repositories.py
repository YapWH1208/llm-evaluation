from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import select, update

from app.db.database import Database
from app.db.models import (
    EvaluationRun,
    BenchmarkDefinition,
    DatasetVersion,
    HumanReview,
    JudgeAssessment,
    MediaAsset,
    ModelEndpoint,
    ModelCapability,
    PromptPackage,
    Report,
    SampleAttempt,
    TaskUnit,
)
from app.db.mongo import MongoDocumentStore


def _model_values(model: Any) -> dict[str, Any]:
    return {column.name: getattr(model, column.name) for column in model.__table__.columns}


class SqliteEvaluationRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._database.get_session() as session:
            run = session.get(EvaluationRun, run_id)
            return _model_values(run) if run is not None else None

    def list_runs(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        with self._database.get_session() as session:
            query = select(EvaluationRun).order_by(EvaluationRun.created_at.desc())
            if not include_archived:
                query = query.where(EvaluationRun.archived_at.is_(None))
            return [_model_values(run) for run in session.scalars(query)]

    def update_run(self, run_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        with self._database.get_session() as session:
            run = session.get(EvaluationRun, run_id)
            if run is None:
                return None
            for field, value in values.items():
                setattr(run, field, value)
            session.commit()
            session.refresh(run)
            return _model_values(run)

    def update_tasks(
        self,
        run_id: str,
        *,
        statuses: Iterable[str],
        values: dict[str, Any],
        increment_lease_version: bool = False,
    ) -> int:
        with self._database.get_session() as session:
            persisted = dict(values)
            if increment_lease_version:
                persisted["lease_version"] = TaskUnit.lease_version + 1
            result = session.execute(
                update(TaskUnit)
                .where(TaskUnit.run_id == run_id, TaskUnit.status.in_(tuple(statuses)))
                .values(**persisted)
                .execution_options(synchronize_session=False)
            )
            session.commit()
            return int(result.rowcount or 0)

    def update_attempts(
        self,
        run_id: str,
        *,
        statuses: Iterable[str],
        values: dict[str, Any],
    ) -> int:
        with self._database.get_session() as session:
            result = session.execute(
                update(SampleAttempt)
                .where(SampleAttempt.run_id == run_id, SampleAttempt.status.in_(tuple(statuses)))
                .values(**values)
                .execution_options(synchronize_session=False)
            )
            session.commit()
            return int(result.rowcount or 0)

    def list_tasks(self, run_id: str) -> list[dict[str, Any]]:
        with self._database.get_session() as session:
            return [
                _model_values(task)
                for task in session.scalars(
                    select(TaskUnit).where(TaskUnit.run_id == run_id).order_by(TaskUnit.created_at)
                )
            ]

    def list_attempts(self, run_id: str) -> list[dict[str, Any]]:
        with self._database.get_session() as session:
            return [
                _model_values(attempt)
                for attempt in session.scalars(
                    select(SampleAttempt)
                    .where(SampleAttempt.run_id == run_id)
                    .order_by(SampleAttempt.sample_id, SampleAttempt.attempt_number)
                )
            ]

    def list_reviews(self, attempt_ids: Iterable[str]) -> list[dict[str, Any]]:
        ids = tuple(attempt_ids)
        if not ids:
            return []
        with self._database.get_session() as session:
            return [
                _model_values(review)
                for review in session.scalars(select(HumanReview).where(HumanReview.sample_attempt_id.in_(ids)))
            ]

    def list_judge_assessments(self, attempt_ids: Iterable[str]) -> list[dict[str, Any]]:
        ids = tuple(attempt_ids)
        if not ids:
            return []
        with self._database.get_session() as session:
            return [
                _model_values(assessment)
                for assessment in session.scalars(
                    select(JudgeAssessment).where(JudgeAssessment.sample_attempt_id.in_(ids))
                )
            ]

    def get_endpoint(self, endpoint_id: str) -> dict[str, Any] | None:
        with self._database.get_session() as session:
            endpoint = session.get(ModelEndpoint, endpoint_id)
            return _model_values(endpoint) if endpoint is not None else None

    def get_prompt_package(self, prompt_package_id: str) -> dict[str, Any] | None:
        with self._database.get_session() as session:
            prompt = session.get(PromptPackage, prompt_package_id)
            return _model_values(prompt) if prompt is not None else None

    def get_benchmark_definition(self, benchmark_id: str, benchmark_version: str) -> dict[str, Any] | None:
        with self._database.get_session() as session:
            definition = session.scalar(
                select(BenchmarkDefinition).where(
                    BenchmarkDefinition.benchmark_id == benchmark_id,
                    BenchmarkDefinition.version == benchmark_version,
                )
            )
            return _model_values(definition) if definition is not None else None

    def list_capabilities(self, endpoint_id: str) -> list[dict[str, Any]]:
        with self._database.get_session() as session:
            return [
                _model_values(capability)
                for capability in session.scalars(
                    select(ModelCapability).where(ModelCapability.model_endpoint_id == endpoint_id)
                )
            ]

    def get_dataset(self, dataset_version_id: str) -> dict[str, Any] | None:
        with self._database.get_session() as session:
            dataset = session.get(DatasetVersion, dataset_version_id)
            return _model_values(dataset) if dataset is not None else None

    def get_media_asset(self, asset_id: str) -> dict[str, Any] | None:
        with self._database.get_session() as session:
            asset = session.get(MediaAsset, asset_id)
            return _model_values(asset) if asset is not None else None

    def find_dataset(self, *, dataset_id: str, version: str | None, revision: str | None) -> dict[str, Any] | None:
        with self._database.get_session() as session:
            query = select(DatasetVersion).where(DatasetVersion.dataset_id == dataset_id)
            if version is not None:
                query = query.where(DatasetVersion.version == version)
            if revision is not None:
                query = query.where(DatasetVersion.revision == revision)
            dataset = session.scalar(query.order_by(DatasetVersion.created_at.desc()))
            return _model_values(dataset) if dataset is not None else None

    def create_dataset(self, values: dict[str, Any]) -> dict[str, Any]:
        with self._database.get_session() as session:
            dataset = DatasetVersion(**values)
            session.add(dataset)
            session.commit()
            session.refresh(dataset)
            return _model_values(dataset)

    def create_run_graph(
        self,
        run_values: dict[str, Any],
        tasks: list[dict[str, Any]],
        attempts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with self._database.get_session() as session:
            run = EvaluationRun(**run_values)
            session.add(run)
            session.flush()
            task_ids: dict[str, str] = {}
            for specification in tasks:
                values = dict(specification)
                key = str(values.pop("key"))
                parent_key = values.pop("parent_key", None)
                task = TaskUnit(
                    run_id=run.id,
                    parent_task_id=task_ids.get(str(parent_key)) if parent_key else None,
                    **values,
                )
                session.add(task)
                session.flush()
                task_ids[key] = task.id
            session.add_all(
                [
                    SampleAttempt(
                        run_id=run.id,
                        task_id=task_ids[str(values.pop("task_key"))],
                        **values,
                    )
                    for item in attempts
                    for values in [dict(item)]
                ]
            )
            session.commit()
            session.refresh(run)
            return _model_values(run)

    def find_previous_completed_run(self, run: dict[str, Any]) -> dict[str, Any] | None:
        with self._database.get_session() as session:
            previous = session.scalar(
                select(EvaluationRun)
                .where(
                    EvaluationRun.model_endpoint_id == run["model_endpoint_id"],
                    EvaluationRun.benchmark_id == run["benchmark_id"],
                    EvaluationRun.benchmark_version == run["benchmark_version"],
                    EvaluationRun.id != run["id"],
                    EvaluationRun.status.in_(("completed", "completed_with_errors")),
                    EvaluationRun.created_at < run["created_at"],
                )
                .order_by(EvaluationRun.created_at.desc())
            )
            return _model_values(previous) if previous is not None else None

    def delete_run(self, run_id: str) -> list[str]:
        with self._database.get_session() as session:
            run = session.get(EvaluationRun, run_id)
            if run is None:
                return []
            artifact_paths = [
                report.artifact_path for report in session.scalars(select(Report).where(Report.run_id == run_id))
            ]
            session.delete(run)
            session.commit()
            return artifact_paths


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
