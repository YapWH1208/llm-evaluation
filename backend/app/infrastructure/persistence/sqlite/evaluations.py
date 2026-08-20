from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update

from app.core.config import Settings
from app.core.secrets import SecretCipher
from app.db.database import Database
from app.db.models import (
    BenchmarkDefinition,
    DatasetVersion,
    EvaluationRun,
    HumanReview,
    JudgeAssessment,
    MediaAsset,
    ModelCapability,
    ModelEndpoint,
    PromptPackage,
    Report,
    SampleAttempt,
    TaskUnit,
)
from app.infrastructure.providers.contracts import ModelExecutor
from app.modules.datasets.preparation import DatasetError


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

    def append_run_graph(
        self,
        run_id: str,
        tasks: list[dict[str, Any]],
        attempts: list[dict[str, Any]],
    ) -> None:
        with self._database.get_session() as session:
            task_ids: dict[str, str] = {}
            for specification in tasks:
                values = dict(specification)
                key = str(values.pop("key"))
                parent_key = values.pop("parent_key", None)
                parent_id = values.pop("parent_id", None)
                task = TaskUnit(
                    run_id=run_id,
                    parent_task_id=parent_id or (task_ids.get(str(parent_key)) if parent_key else None),
                    **values,
                )
                session.add(task)
                session.flush()
                task_ids[key] = task.id
            session.add_all(
                [
                    SampleAttempt(
                        run_id=run_id,
                        task_id=task_ids[str(values.pop("task_key"))],
                        **values,
                    )
                    for item in attempts
                    for values in [dict(item)]
                ]
            )
            session.commit()

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._database.get_session() as session:
            task = session.get(TaskUnit, task_id)
            return _model_values(task) if task is not None else None

    def claim_task(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
        run_id: str | None = None,
        system_max_concurrency: int | None = None,
        worker_max_concurrency: int | None = None,
    ) -> dict[str, Any] | None:
        from app.infrastructure.persistence.sqlite.queue import claim_task

        with self._database.get_session() as session:
            task = claim_task(
                session,
                worker_id,
                lease_seconds,
                run_id=run_id,
                system_max_concurrency=system_max_concurrency,
                worker_max_concurrency=worker_max_concurrency,
            )
            return _model_values(task) if task is not None else None

    def heartbeat_task(self, task_id: str, lease_token: str, lease_seconds: int) -> dict[str, Any] | None:
        from app.infrastructure.persistence.sqlite.queue import heartbeat_task

        with self._database.get_session() as session:
            task = heartbeat_task(session, task_id, lease_token, lease_seconds)
            return _model_values(task) if task is not None else None

    def reclaim_expired_leases(self) -> int:
        from app.infrastructure.persistence.sqlite.queue import reclaim_expired_leases

        with self._database.get_session() as session:
            return reclaim_expired_leases(session)

    def update_run_if(
        self,
        run_id: str,
        *,
        statuses: Iterable[str],
        values: dict[str, Any],
    ) -> dict[str, Any] | None:
        with self._database.get_session() as session:
            result = session.execute(
                update(EvaluationRun)
                .where(EvaluationRun.id == run_id, EvaluationRun.status.in_(tuple(statuses)))
                .values(**values)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                session.rollback()
                return None
            session.commit()
            run = session.get(EvaluationRun, run_id)
            return _model_values(run) if run is not None else None

    def update_task_for_lease(
        self,
        task_id: str,
        lease_token: str,
        values: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc)
        persisted = {"heartbeat_at": now, **(values or {})}
        with self._database.get_session() as session:
            result = session.execute(
                update(TaskUnit)
                .where(
                    TaskUnit.id == task_id,
                    TaskUnit.lease_token == lease_token,
                    TaskUnit.status.in_(("leased", "running")),
                    TaskUnit.lease_expires_at >= now,
                )
                .values(**persisted)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                session.rollback()
                return None
            session.commit()
            task = session.get(TaskUnit, task_id)
            return _model_values(task) if task is not None else None

    def create_task(self, values: dict[str, Any]) -> dict[str, Any]:
        with self._database.get_session() as session:
            task = TaskUnit(**values)
            session.add(task)
            session.commit()
            session.refresh(task)
            return _model_values(task)

    def create_attempt(self, values: dict[str, Any]) -> dict[str, Any]:
        with self._database.get_session() as session:
            attempt = SampleAttempt(**values)
            session.add(attempt)
            session.commit()
            session.refresh(attempt)
            return _model_values(attempt)

    def begin_attempt(self, attempt_id: str, lease_token: str, values: dict[str, Any]) -> dict[str, Any] | None:
        del lease_token
        with self._database.get_session() as session:
            result = session.execute(
                update(SampleAttempt)
                .where(SampleAttempt.id == attempt_id, SampleAttempt.status == "pending")
                .values(**values)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                session.rollback()
                return None
            session.commit()
            attempt = session.get(SampleAttempt, attempt_id)
            return _model_values(attempt) if attempt is not None else None

    def complete_attempt(
        self,
        attempt_id: str,
        lease_token: str,
        values: dict[str, Any],
    ) -> dict[str, Any] | None:
        del lease_token
        with self._database.get_session() as session:
            result = session.execute(
                update(SampleAttempt)
                .where(SampleAttempt.id == attempt_id, SampleAttempt.status == "running")
                .values(**values)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                session.rollback()
                return None
            session.commit()
            attempt = session.get(SampleAttempt, attempt_id)
            return _model_values(attempt) if attempt is not None else None

    def update_attempt(self, attempt_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        with self._database.get_session() as session:
            attempt = session.get(SampleAttempt, attempt_id)
            if attempt is None:
                return None
            for name, value in values.items():
                setattr(attempt, name, value)
            session.commit()
            session.refresh(attempt)
            return _model_values(attempt)

    def prepare_dataset(self, descriptor: dict[str, Any], data_root: str, settings: Settings | None) -> None:
        from app.modules.datasets.repositories import SqliteSessionDatasetRepository
        from app.modules.datasets.service import DatasetService

        with self._database.get_session() as session:
            frozen_id = descriptor.get("dataset_version_id")
            if isinstance(frozen_id, str):
                dataset = session.get(DatasetVersion, frozen_id)
            else:
                query = select(DatasetVersion).where(DatasetVersion.dataset_id == descriptor["dataset_id"])
                if isinstance(descriptor.get("version"), str):
                    query = query.where(DatasetVersion.version == descriptor["version"])
                if isinstance(descriptor.get("revision"), str):
                    query = query.where(DatasetVersion.revision == descriptor["revision"])
                dataset = session.scalar(query.order_by(DatasetVersion.created_at.desc()))
            if dataset is None:
                raise DatasetError(f"Required dataset {descriptor['dataset_id']} is not registered.")
            if dataset.status != "ready":
                DatasetService(SqliteSessionDatasetRepository(session)).download(dataset.id, data_root, settings)

    def aggregate(self, run_id: str) -> int:
        from app.modules.analytics.aggregation import recompute_aggregate_metrics

        with self._database.get_session() as session:
            return len(recompute_aggregate_metrics(session, run_id))

    def generate_report(
        self,
        run_id: str,
        format: str,
        data_root: str,
        *,
        report_type: str,
    ) -> dict[str, Any]:
        from app.modules.reports.service import generate_report

        with self._database.get_session() as session:
            report = generate_report(session, run_id, format, data_root, report_type=report_type)
            return _model_values(report)

    def assess_judge(
        self,
        *,
        sample_attempt_id: str,
        judge_endpoint_id: str,
        rubric: dict[str, Any],
        system_message: str,
        cipher: SecretCipher,
        model_executor: ModelExecutor,
        endpoint_override: dict[str, Any],
    ) -> dict[str, Any]:
        from app.modules.reviews.judges import assess_sample_attempt

        with self._database.get_session() as session:
            assessment = assess_sample_attempt(
                session,
                sample_attempt_id=sample_attempt_id,
                judge_endpoint_id=judge_endpoint_id,
                rubric=rubric,
                system_message=system_message,
                persist=True,
                cipher=cipher,
                model_executor=model_executor,
                endpoint_override=endpoint_override,
            )
            return _model_values(assessment)

    def query_tasks(
        self,
        *,
        run_id: str | None,
        status: str | None,
        offset: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        with self._database.get_session() as session:
            query = select(TaskUnit)
            if run_id:
                query = query.where(TaskUnit.run_id == run_id)
            if status:
                query = query.where(TaskUnit.status == status)
            return [
                _model_values(task)
                for task in session.scalars(
                    query.order_by(TaskUnit.priority.desc(), TaskUnit.created_at).offset(offset).limit(limit)
                )
            ]

    def update_task_priority(self, task_id: str, priority: int) -> dict[str, Any] | None:
        with self._database.get_session() as session:
            task = session.get(TaskUnit, task_id)
            if task is None:
                return None
            task.priority = priority
            session.commit()
            session.refresh(task)
            return _model_values(task)

    def queue_snapshot(self) -> dict[str, Any]:
        with self._database.get_session() as session:
            active = TaskUnit.status.in_(("leased", "running"))
            workers = session.scalars(
                select(TaskUnit.leased_by).where(active, TaskUnit.leased_by.is_not(None)).distinct().limit(500)
            )
            errors = session.scalars(
                select(TaskUnit).where(TaskUnit.status == "failed").order_by(TaskUnit.updated_at.desc()).limit(20)
            )
            return {
                "queue": {
                    "pending": session.scalar(
                        select(func.count())
                        .select_from(TaskUnit)
                        .where(TaskUnit.status.in_(("pending", "retry_scheduled")))
                    )
                    or 0,
                    "active": session.scalar(select(func.count()).select_from(TaskUnit).where(active)) or 0,
                },
                "workers": sorted(str(worker) for worker in workers if worker),
                "errors": [
                    {
                        "task_id": task.id,
                        "run_id": task.run_id,
                        "retry_exhausted_reason": (task.payload or {}).get("retry_exhausted_reason"),
                    }
                    for task in errors
                ],
            }

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
