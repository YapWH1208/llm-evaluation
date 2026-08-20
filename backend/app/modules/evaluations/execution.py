from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.core.secrets import SecretCipher
from app.db.models import RunStatus, SampleAttemptStatus, TaskStatus, TaskType
from app.infrastructure.providers.contracts import ModelExecutor
from app.modules.evaluations.attempts import AttemptProcessor, latest_attempts, task_payload
from app.modules.evaluations.ports import ExecutionRepository
from app.modules.evaluations.queue_service import QueueService
from app.modules.evaluations.retry import (
    is_retryable,
    nonnegative_float,
    retry_delay_seconds,
    retry_policy,
)
from app.modules.evaluations.stages import PipelineStages
from app.modules.reviews.judges import JudgeService
from app.modules.reports.service import ReportService
from app.modules.analytics.aggregation import AggregationService


_RUNNABLE_RUN_STATUSES = (RunStatus.QUEUED.value, RunStatus.RUNNING.value)
_ACTIVE_SHARD_STATUSES = (
    TaskStatus.PENDING.value,
    TaskStatus.LEASED.value,
    TaskStatus.RUNNING.value,
    TaskStatus.RETRY_SCHEDULED.value,
)


class ExecutionService:
    """Store-neutral queue coordination and evaluation execution pipeline."""

    def __init__(
        self,
        repository: ExecutionRepository,
        settings: Settings,
        queue: QueueService,
        judges: JudgeService,
        reports: ReportService,
        aggregation: AggregationService,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._queue = queue
        self._attempts = AttemptProcessor(repository, judges)
        self._stages = PipelineStages(repository, settings, reports, aggregation)

    def execute_run(
        self,
        run_id: str,
        *,
        cipher: SecretCipher,
        model_executor: ModelExecutor,
    ) -> dict[str, Any]:
        run = self._repository.get_run(run_id)
        if run is None:
            raise NotFoundError("Evaluation run not found", context={"run_id": run_id})
        if run.get("status") not in _RUNNABLE_RUN_STATUSES:
            raise ConflictError("Only queued or running evaluation runs can be executed.")
        while True:
            task = self._queue.claim("interactive-api", 600, run_id=run_id)
            if task is None or not task.get("lease_token"):
                current = self._repository.get_run(run_id)
                if current is not None and current.get("status") in {
                    RunStatus.QUEUED.value,
                    RunStatus.RUNNING.value,
                    RunStatus.COMPLETED.value,
                    RunStatus.COMPLETED_WITH_ERRORS.value,
                }:
                    return current
                raise ConflictError("No due task is available for this evaluation run.")
            run, _ = self.execute_task(
                str(task["id"]),
                str(task["lease_token"]),
                cipher=cipher,
                model_executor=model_executor,
            )
            if run.get("status") in {RunStatus.COMPLETED.value, RunStatus.COMPLETED_WITH_ERRORS.value}:
                return run

    def execute_task(
        self,
        task_id: str,
        lease_token: str,
        *,
        cipher: SecretCipher,
        model_executor: ModelExecutor,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        task = self._repository.get_task(task_id)
        if task is None:
            raise NotFoundError("Task not found", context={"task_id": task_id})
        task = self._require_lease(task_id, lease_token)
        task_type = str(task["task_type"])
        if task_type == TaskType.SCORING.value:
            return self._stages.execute_scoring(task, lease_token)
        if task_type == TaskType.AGGREGATION.value:
            return self._stages.execute_aggregation(task, lease_token)
        if task_type == TaskType.REPORT_GENERATION.value:
            return self._stages.execute_report(task, lease_token)
        if task_type in {
            TaskType.DATASET_PREPARATION.value,
            TaskType.BENCHMARK.value,
            TaskType.JUDGE.value,
            TaskType.CLEANUP.value,
        }:
            return self._stages.execute_stage(task, lease_token)
        if task_type != TaskType.EVALUATION_SHARD.value:
            raise ConflictError("Unsupported task type.")
        return self._execute_shard(task, lease_token, cipher=cipher, model_executor=model_executor)

    def _execute_shard(
        self,
        task: dict[str, Any],
        lease_token: str,
        *,
        cipher: SecretCipher,
        model_executor: ModelExecutor,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        run_id = str(task["run_id"])
        run = self._runnable_run(run_id)
        endpoint = self._repository.get_endpoint(str(run["model_endpoint_id"]))
        if endpoint is None:
            raise ConflictError("The model endpoint for this run no longer exists.")
        now = _utc_now()
        run = self._repository.update_run_if(
            run_id,
            statuses=_RUNNABLE_RUN_STATUSES,
            values={"status": RunStatus.RUNNING.value, "started_at": run.get("started_at") or now},
        )
        if run is None:
            raise ConflictError("Evaluation run is no longer executable.")
        task = self._update_leased_task(
            task,
            lease_token,
            {"status": TaskStatus.RUNNING.value, "attempt_count": int(task.get("attempt_count", 0)) + 1},
            "Task lease was lost before execution started.",
        )
        frozen_endpoint = _frozen_endpoint(run, endpoint)
        policy = retry_policy(task_payload(task))
        attempts = self._attempts.prepare(task)
        api_key = cipher.decrypt(str(endpoint["encrypted_api_key"]))
        retry_sample_ids: list[str] = []
        provider_retry_after_seconds: float | None = None
        for attempt in attempts:
            self._require_lease(str(task["id"]), lease_token)
            self._runnable_run(run_id)
            started = self._repository.begin_attempt(
                str(attempt["id"]),
                lease_token,
                {"status": SampleAttemptStatus.RUNNING.value, "started_at": _utc_now(), "completed_at": None},
            )
            if started is None:
                raise ConflictError("Sample attempt is no longer available for this task lease.")
            result = model_executor.execute(_proxy(frozen_endpoint), api_key, dict(attempt["input_snapshot"]))
            self._require_lease(str(task["id"]), lease_token)
            stored = self._attempts.record_result(
                run,
                started,
                result,
                frozen_endpoint,
                lease_token,
                cipher=cipher,
                model_executor=model_executor,
            )
            if not result.success and is_retryable(result.error_type, policy):
                retry_sample_ids.append(str(stored["sample_id"]))
                if result.retry_after_seconds is not None:
                    provider_retry_after_seconds = max(
                        provider_retry_after_seconds or 0.0,
                        result.retry_after_seconds,
                    )

        retry_sample_ids = sorted(set(retry_sample_ids))
        self._require_lease(str(task["id"]), lease_token)
        if (
            retry_sample_ids
            and int(task["attempt_count"]) < int(policy["max_attempts"])
            and self._schedule_retry(
                run,
                task,
                lease_token,
                retry_sample_ids,
                policy,
                provider_retry_after_seconds=provider_retry_after_seconds,
            )
        ):
            refreshed_run = self._repository.get_run(run_id)
            refreshed_task = self._repository.get_task(str(task["id"]))
            assert refreshed_run is not None and refreshed_task is not None
            return refreshed_run, refreshed_task
        task = self._repository.get_task(str(task["id"])) or task
        return self._finalize_shard(run, task, lease_token)

    def _schedule_retry(
        self,
        run: dict[str, Any],
        task: dict[str, Any],
        lease_token: str,
        retry_sample_ids: list[str],
        policy: dict[str, Any],
        *,
        provider_retry_after_seconds: float | None,
    ) -> bool:
        delay = retry_delay_seconds(
            int(task["attempt_count"]),
            policy,
            provider_retry_after_seconds=provider_retry_after_seconds,
        )
        payload = task_payload(task)
        previous_wait = nonnegative_float(payload.get("retry_total_wait_seconds", 0))
        if previous_wait + delay > float(policy["max_total_wait_seconds"]):
            payload.update(
                {
                    "retry_exhausted_reason": "max_total_wait_seconds",
                    "retry_total_wait_seconds": previous_wait,
                }
            )
            self._update_leased_task(
                task,
                lease_token,
                {"payload": payload},
                "Task lease was lost before finalization.",
            )
            return False
        payload.update(
            {
                "retry_sample_ids": retry_sample_ids,
                "retry_total_wait_seconds": round(previous_wait + delay, 3),
                "last_retry_delay_seconds": delay,
            }
        )
        self._update_leased_task(
            task,
            lease_token,
            {
                "payload": payload,
                "status": TaskStatus.RETRY_SCHEDULED.value,
                "next_retry_at": _utc_now() + timedelta(seconds=delay),
                **_lease_clear(),
            },
            "Task lease was lost before retry scheduling.",
        )
        latest = latest_attempts(
            [
                attempt
                for attempt in self._repository.list_attempts(str(run["id"]))
                if str(attempt["task_id"]) == str(task["id"])
            ]
        )
        for attempt in latest.values():
            if (
                str(attempt["sample_id"]) in retry_sample_ids
                and attempt.get("status") == SampleAttemptStatus.FAILED.value
            ):
                self._repository.update_attempt(
                    str(attempt["id"]),
                    {"status": SampleAttemptStatus.RETRY_SCHEDULED.value},
                )
        self._update_progress(str(run["id"]), retry_sample_ids)
        queued = self._repository.update_run_if(
            str(run["id"]),
            statuses=_RUNNABLE_RUN_STATUSES,
            values={"status": RunStatus.QUEUED.value},
        )
        if queued is None:
            raise ConflictError("Evaluation run is no longer executable.")
        return True

    def _finalize_shard(
        self,
        run: dict[str, Any],
        task: dict[str, Any],
        lease_token: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        self._update_progress(str(run["id"]), [])
        payload = {key: value for key, value in task_payload(task).items() if key != "retry_sample_ids"}
        task = self._update_leased_task(
            task,
            lease_token,
            {
                "status": TaskStatus.SUCCEEDED.value,
                "next_retry_at": None,
                "payload": payload,
                **_lease_clear(),
            },
            "Task lease was lost before finalization.",
        )
        incomplete = [
            candidate
            for candidate in self._repository.list_tasks(str(run["id"]))
            if candidate["id"] != task["id"]
            and candidate.get("task_type") == TaskType.EVALUATION_SHARD.value
            and candidate.get("status") in _ACTIVE_SHARD_STATUSES
        ]
        target_status = RunStatus.RUNNING.value if incomplete else RunStatus.SCORING.value
        updated = self._repository.update_run_if(
            str(run["id"]),
            statuses=_RUNNABLE_RUN_STATUSES,
            values={"status": target_status, "completed_at": None},
        )
        if updated is None:
            raise ConflictError("Evaluation run is no longer executable.")
        if not incomplete:
            self._stages.enqueue_stage(updated, task, TaskType.SCORING.value)
        return updated, task

    def _update_progress(self, run_id: str, retry_sample_ids: list[str]) -> dict[str, Any]:
        latest = latest_attempts(self._repository.list_attempts(run_id))
        retry_set = set(retry_sample_ids)
        successful = sum(item.get("status") == SampleAttemptStatus.SUCCEEDED.value for item in latest.values())
        failed = sum(
            item.get("status") == SampleAttemptStatus.FAILED.value and str(item["sample_id"]) not in retry_set
            for item in latest.values()
        )
        run = self._repository.update_run_if(
            run_id,
            statuses=(
                RunStatus.QUEUED.value,
                RunStatus.RUNNING.value,
                RunStatus.SCORING.value,
                RunStatus.AGGREGATING.value,
                RunStatus.GENERATING_REPORT.value,
            ),
            values={
                "completed_samples": successful + failed,
                "successful_samples": successful,
                "failed_samples": failed,
            },
        )
        if run is None:
            raise ConflictError("Evaluation run is no longer executable.")
        return run

    def _run(self, run_id: str) -> dict[str, Any]:
        run = self._repository.get_run(run_id)
        if run is None:
            raise NotFoundError("Evaluation run not found", context={"run_id": run_id})
        return run

    def _runnable_run(self, run_id: str) -> dict[str, Any]:
        run = self._run(run_id)
        if run.get("status") not in _RUNNABLE_RUN_STATUSES:
            raise ConflictError("Evaluation run is no longer executable.")
        return run

    def _require_lease(self, task_id: str, lease_token: str) -> dict[str, Any]:
        task = self._repository.update_task_for_lease(task_id, lease_token)
        if task is None:
            raise ConflictError("Task lease was lost before result persistence.")
        return task

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


def _frozen_endpoint(run: dict[str, Any], endpoint: dict[str, Any]) -> dict[str, Any]:
    snapshot = run.get("configuration_snapshot") if isinstance(run.get("configuration_snapshot"), dict) else {}
    frozen = snapshot.get("endpoint") if isinstance(snapshot.get("endpoint"), dict) else {}
    values = dict(endpoint)
    for name in (
        "base_url",
        "model_name",
        "protocol_profile",
        "default_request_body",
        "timeout_seconds",
        "custom_headers",
        "input_cost_per_million",
        "output_cost_per_million",
    ):
        if name in frozen:
            values[name] = frozen[name]
    return values


def _proxy(document: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(**document)


def _lease_clear() -> dict[str, Any]:
    return {
        "leased_by": None,
        "lease_token": None,
        "lease_expires_at": None,
        "heartbeat_at": None,
    }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
