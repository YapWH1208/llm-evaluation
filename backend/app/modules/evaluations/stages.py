from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.core.errors import ApplicationError, ConflictError, NotFoundError
from app.modules.evaluations.models import RunStatus, SampleAttemptStatus, TaskStatus, TaskType
from app.modules.analytics.aggregation import AGGREGATION_VERSION, AggregationService
from app.modules.datasets.service import DatasetService
from app.modules.evaluations.attempts import latest_attempts, task_payload, utc_now
from app.modules.evaluations.ports import ExecutionRepository
from app.modules.reports.service import ReportService


class PipelineStages:
    """Execute non-inference stages after evaluation shards fan in."""

    def __init__(
        self,
        repository: ExecutionRepository,
        settings: Settings,
        datasets: DatasetService,
        reports: ReportService,
        aggregation: AggregationService,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._datasets = datasets
        self._reports = reports
        self._aggregation = aggregation

    def execute_stage(
        self,
        task: dict[str, Any],
        lease_token: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        run = self._run(str(task["run_id"]))
        task = self._update_leased_task(
            task,
            lease_token,
            {"status": TaskStatus.RUNNING.value, "attempt_count": int(task.get("attempt_count", 0)) + 1},
            "Task lease was lost before execution started.",
        )
        payload = task_payload(task)
        if task["task_type"] == TaskType.DATASET_PREPARATION.value:
            try:
                for descriptor in payload.get("datasets", []):
                    if isinstance(descriptor, dict) and isinstance(descriptor.get("dataset_id"), str):
                        self._datasets.prepare(descriptor, self._settings.data_root, self._settings)
            except ApplicationError as error:
                self._update_leased_task(
                    task,
                    lease_token,
                    {
                        "status": TaskStatus.RETRY_SCHEDULED.value,
                        "payload": {**payload, "dataset_error": str(error)},
                        **_lease_clear(),
                    },
                    "Task lease was lost before retry scheduling.",
                )
                raise ConflictError(str(error)) from error
        task = self._update_leased_task(
            task,
            lease_token,
            {
                "status": TaskStatus.SUCCEEDED.value,
                "payload": {
                    **payload,
                    "worker_interface": task["task_type"],
                    "stage_completed_at": utc_now().isoformat(),
                },
                **_lease_clear(),
            },
            "Task lease was lost before finalization.",
        )
        if (
            task["task_type"] == TaskType.DATASET_PREPARATION.value
            and run.get("status") == RunStatus.WAITING_FOR_DATASET.value
        ):
            updated = self._repository.update_run_if(
                str(run["id"]),
                statuses=(RunStatus.WAITING_FOR_DATASET.value,),
                values={"status": RunStatus.QUEUED.value},
            )
            if updated is None:
                raise ConflictError("Evaluation run is no longer executable.")
            run = updated
        return run, task

    def execute_scoring(
        self,
        task: dict[str, Any],
        lease_token: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        run = self._run(str(task["run_id"]))
        if run.get("status") not in {RunStatus.SCORING.value, RunStatus.RUNNING.value}:
            raise ConflictError("Evaluation run is not ready for scoring.")
        task = self._update_leased_task(
            task,
            lease_token,
            {"status": TaskStatus.RUNNING.value, "attempt_count": int(task.get("attempt_count", 0)) + 1},
            "Task lease was lost before execution started.",
        )
        run = self._repository.update_run_if(
            str(run["id"]),
            statuses=(RunStatus.SCORING.value, RunStatus.RUNNING.value),
            values={"status": RunStatus.SCORING.value},
        )
        if run is None:
            raise ConflictError("Evaluation run is no longer executable.")
        latest = latest_attempts(self._repository.list_attempts(str(run["id"])))
        task = self._update_leased_task(
            task,
            lease_token,
            {
                "payload": {
                    **task_payload(task),
                    "scored_samples": sum(item.get("score") is not None for item in latest.values()),
                    "failed_samples": sum(
                        item.get("status") == SampleAttemptStatus.FAILED.value for item in latest.values()
                    ),
                    "deterministic_scoring": "verified",
                },
                "status": TaskStatus.SUCCEEDED.value,
                **_lease_clear(),
            },
            "Task lease was lost before finalization.",
        )
        run = self._repository.update_run_if(
            str(run["id"]),
            statuses=(RunStatus.SCORING.value,),
            values={"status": RunStatus.AGGREGATING.value},
        )
        if run is None:
            raise ConflictError("Evaluation run is no longer executable.")
        self.enqueue_stage(run, task, TaskType.AGGREGATION.value)
        return run, task

    def execute_aggregation(
        self,
        task: dict[str, Any],
        lease_token: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        run = self._run(str(task["run_id"]))
        if run.get("status") not in {RunStatus.AGGREGATING.value, RunStatus.SCORING.value}:
            raise ConflictError("Evaluation run is not ready for aggregation.")
        task = self._update_leased_task(
            task,
            lease_token,
            {"status": TaskStatus.RUNNING.value, "attempt_count": int(task.get("attempt_count", 0)) + 1},
            "Task lease was lost before execution started.",
        )
        run = self._repository.update_run_if(
            str(run["id"]),
            statuses=(RunStatus.AGGREGATING.value, RunStatus.SCORING.value),
            values={"status": RunStatus.AGGREGATING.value},
        )
        if run is None:
            raise ConflictError("Evaluation run is no longer executable.")
        metric_count = len(self._aggregation.recompute(str(run["id"])))
        task = self._update_leased_task(
            task,
            lease_token,
            {
                "payload": {
                    **task_payload(task),
                    "metric_count": metric_count,
                    "aggregation_version": AGGREGATION_VERSION,
                },
                "status": TaskStatus.SUCCEEDED.value,
                **_lease_clear(),
            },
            "Task lease was lost before finalization.",
        )
        run = self._repository.update_run_if(
            str(run["id"]),
            statuses=(RunStatus.AGGREGATING.value,),
            values={"status": RunStatus.GENERATING_REPORT.value, "completed_at": None},
        )
        if run is None:
            raise ConflictError("Evaluation run is no longer executable.")
        self.enqueue_stage(run, task, TaskType.REPORT_GENERATION.value)
        return run, task

    def execute_report(
        self,
        task: dict[str, Any],
        lease_token: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        run = self._run(str(task["run_id"]))
        if run.get("status") != RunStatus.GENERATING_REPORT.value:
            raise ConflictError("Evaluation run is not ready for report generation.")
        task = self._update_leased_task(
            task,
            lease_token,
            {"status": TaskStatus.RUNNING.value, "attempt_count": int(task.get("attempt_count", 0)) + 1},
            "Task lease was lost before execution started.",
        )
        payload = task_payload(task)
        try:
            report = self._reports.generate(
                str(run["id"]),
                str(payload.get("format", "html")),
                report_type=str(payload.get("report_type", "single_model")),
            )
        except ApplicationError as error:
            task = self._update_leased_task(
                task,
                lease_token,
                {
                    "status": TaskStatus.FAILED.value,
                    "payload": {**payload, "report_error": str(error)},
                    **_lease_clear(),
                },
                "Task lease was lost before finalization.",
            )
            final_status = str(
                payload.get(
                    "terminal_status",
                    RunStatus.COMPLETED_WITH_ERRORS.value
                    if int(run.get("failed_samples", 0))
                    else RunStatus.COMPLETED.value,
                )
            )
            self._repository.update_run_if(
                str(run["id"]),
                statuses=(RunStatus.GENERATING_REPORT.value,),
                values={"status": final_status, "completed_at": utc_now()},
            )
            raise ConflictError(str(error)) from error
        task = self._update_leased_task(
            task,
            lease_token,
            {
                "status": TaskStatus.SUCCEEDED.value,
                "payload": {**payload, "report_id": report["id"], "artifact_path": report["artifact_path"]},
                **_lease_clear(),
            },
            "Task lease was lost before finalization.",
        )
        final_status = (
            RunStatus.COMPLETED_WITH_ERRORS.value if int(run.get("failed_samples", 0)) else RunStatus.COMPLETED.value
        )
        completed = self._repository.update_run_if(
            str(run["id"]),
            statuses=(RunStatus.GENERATING_REPORT.value,),
            values={"status": final_status, "completed_at": utc_now()},
        )
        if completed is None:
            raise ConflictError("Evaluation run is no longer executable.")
        return completed, task

    def enqueue_stage(
        self,
        run: dict[str, Any],
        parent_task: dict[str, Any],
        task_type: str,
    ) -> dict[str, Any]:
        existing = [
            task
            for task in self._repository.list_tasks(str(run["id"]))
            if task.get("parent_task_id") == parent_task["id"] and task.get("task_type") == task_type
        ]
        if existing:
            return existing[0]
        now = utc_now()
        return self._repository.create_task(
            {
                "run_id": run["id"],
                "parent_task_id": parent_task["id"],
                "task_type": task_type,
                "payload": {
                    "pipeline_stage": task_type,
                    **(
                        {
                            "format": "html",
                            "report_type": "single_model",
                            "terminal_status": (
                                RunStatus.COMPLETED_WITH_ERRORS.value
                                if int(run.get("failed_samples", 0))
                                else RunStatus.COMPLETED.value
                            ),
                        }
                        if task_type == TaskType.REPORT_GENERATION.value
                        else {}
                    ),
                },
                "status": TaskStatus.PENDING.value,
                "priority": int(parent_task.get("priority", 0)),
                "attempt_count": 0,
                "leased_by": None,
                "lease_token": None,
                "lease_version": 0,
                "lease_expires_at": None,
                "next_retry_at": None,
                "heartbeat_at": None,
                "created_at": now,
                "updated_at": now,
            }
        )

    def _run(self, run_id: str) -> dict[str, Any]:
        run = self._repository.get_run(run_id)
        if run is None:
            raise NotFoundError("Evaluation run not found", context={"run_id": run_id})
        return run

    def _update_leased_task(
        self,
        task: dict[str, Any],
        lease_token: str,
        values: dict[str, Any],
        error_message: str,
    ) -> dict[str, Any]:
        updated = self._repository.update_task_for_lease(str(task["id"]), lease_token, values)
        if updated is None:
            raise ConflictError(error_message)
        return updated


def _lease_clear() -> dict[str, Any]:
    return {
        "leased_by": None,
        "lease_token": None,
        "lease_expires_at": None,
        "heartbeat_at": None,
    }
