from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.core.secrets import SecretCipher
from app.db.models import RunStatus, SampleAttemptStatus, TaskStatus, TaskType
from app.infrastructure.providers.contracts import ModelExecutor, SampleExecutionResult
from app.modules.analytics.aggregation import AGGREGATION_VERSION
from app.modules.benchmarks.metrics import build_execution_metric_evidence
from app.modules.benchmarks.scoring import ScoringError, score_prediction
from app.modules.datasets.preparation import DatasetError
from app.modules.evaluations.ports import ExecutionRepository
from app.modules.reports.service import ReportError
from app.modules.reviews.judges import JudgeAssessmentError
from app.modules.reviews.scoring import is_llm_judge_rule, judge_assessment_evidence, judge_failure_evidence


DEFAULT_RETRY_POLICY = {
    "max_attempts": 3,
    "base_delay_seconds": 2,
    "max_delay_seconds": 60,
    "strategy": "exponential_jitter",
    "jitter_ratio": 0.2,
    "max_total_wait_seconds": 600,
    "respect_retry_after": True,
    "retry_response_parse_errors": True,
}

_RUNNABLE_RUN_STATUSES = (RunStatus.QUEUED.value, RunStatus.RUNNING.value)
_ACTIVE_SHARD_STATUSES = (
    TaskStatus.PENDING.value,
    TaskStatus.LEASED.value,
    TaskStatus.RUNNING.value,
    TaskStatus.RETRY_SCHEDULED.value,
)


class ExecutionService:
    """Store-neutral queue coordination and evaluation execution pipeline."""

    def __init__(self, repository: ExecutionRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    def claim(self, worker_id: str, lease_seconds: int, *, run_id: str | None = None) -> dict[str, Any] | None:
        return self._repository.claim_task(
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            run_id=run_id,
            system_max_concurrency=self._settings.system_max_concurrency,
            worker_max_concurrency=self._settings.worker_max_concurrency,
        )

    def heartbeat(self, task_id: str, lease_token: str, lease_seconds: int) -> dict[str, Any]:
        task = self._repository.heartbeat_task(task_id, lease_token, lease_seconds)
        if task is None:
            raise ConflictError("Task lease is no longer valid")
        return task

    def reclaim_expired(self) -> int:
        return self._repository.reclaim_expired_leases()

    def list_tasks(
        self,
        *,
        run_id: str | None,
        status: str | None,
        offset: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        return self._repository.query_tasks(
            run_id=run_id,
            status=status,
            offset=max(0, offset),
            limit=min(max(1, limit), 1000),
        )

    def update_priority(self, task_id: str, priority: int) -> dict[str, Any]:
        task = self._repository.get_task(task_id)
        if task is None:
            raise NotFoundError("Task not found", context={"task_id": task_id})
        if task.get("status") not in {TaskStatus.PENDING.value, TaskStatus.RETRY_SCHEDULED.value}:
            raise ConflictError("Only queued tasks can have their priority adjusted")
        updated = self._repository.update_task_priority(task_id, priority)
        if updated is None:
            raise NotFoundError("Task not found", context={"task_id": task_id})
        return updated

    def queue_snapshot(self) -> dict[str, Any]:
        return self._repository.queue_snapshot()

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
            task = self.claim("interactive-api", 600, run_id=run_id)
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
            return self._execute_scoring(task, lease_token)
        if task_type == TaskType.AGGREGATION.value:
            return self._execute_aggregation(task, lease_token)
        if task_type == TaskType.REPORT_GENERATION.value:
            return self._execute_report(task, lease_token)
        if task_type in {
            TaskType.DATASET_PREPARATION.value,
            TaskType.BENCHMARK.value,
            TaskType.JUDGE.value,
            TaskType.CLEANUP.value,
        }:
            return self._execute_stage(task, lease_token)
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
        policy = _retry_policy(_task_payload(task))
        attempts = self._prepare_attempts(task)
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
            stored = self._record_result(
                run,
                started,
                result,
                frozen_endpoint,
                lease_token,
                cipher=cipher,
                model_executor=model_executor,
            )
            if not result.success and _is_retryable(result.error_type, policy):
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

    def _execute_stage(
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
        payload = _task_payload(task)
        if task["task_type"] == TaskType.DATASET_PREPARATION.value:
            try:
                for descriptor in payload.get("datasets", []):
                    if isinstance(descriptor, dict) and isinstance(descriptor.get("dataset_id"), str):
                        self._repository.prepare_dataset(descriptor, self._settings.data_root, self._settings)
            except DatasetError as error:
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
                    "stage_completed_at": _utc_now().isoformat(),
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

    def _execute_scoring(
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
        latest = _latest_attempts(self._repository.list_attempts(str(run["id"])))
        task = self._update_leased_task(
            task,
            lease_token,
            {
                "payload": {
                    **_task_payload(task),
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
        self._enqueue_stage(run, task, TaskType.AGGREGATION.value)
        return run, task

    def _execute_aggregation(
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
        metric_count = self._repository.aggregate(str(run["id"]))
        task = self._update_leased_task(
            task,
            lease_token,
            {
                "payload": {
                    **_task_payload(task),
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
        self._enqueue_stage(run, task, TaskType.REPORT_GENERATION.value)
        return run, task

    def _execute_report(
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
        payload = _task_payload(task)
        try:
            report = self._repository.generate_report(
                str(run["id"]),
                str(payload.get("format", "html")),
                self._settings.data_root,
                report_type=str(payload.get("report_type", "single_model")),
            )
        except ReportError as error:
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
                values={"status": final_status, "completed_at": _utc_now()},
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
            values={"status": final_status, "completed_at": _utc_now()},
        )
        if completed is None:
            raise ConflictError("Evaluation run is no longer executable.")
        return completed, task

    def _prepare_attempts(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        payload = _task_payload(task)
        sample_ids = [
            value
            for value in payload.get("retry_sample_ids") or payload.get("sample_ids") or []
            if isinstance(value, str)
        ]
        attempts = [
            attempt
            for attempt in self._repository.list_attempts(str(task["run_id"]))
            if str(attempt["task_id"]) == str(task["id"])
        ]
        latest = _latest_attempts(attempts)
        if int(task.get("attempt_count", 0)) > 1:
            for sample_id in sample_ids:
                previous = latest.get(sample_id)
                if previous is None or previous.get("status") not in {
                    SampleAttemptStatus.FAILED.value,
                    SampleAttemptStatus.RETRY_SCHEDULED.value,
                }:
                    continue
                self._repository.create_attempt(
                    {
                        "run_id": previous["run_id"],
                        "task_id": previous["task_id"],
                        "sample_id": previous["sample_id"],
                        "attempt_number": int(previous["attempt_number"]) + 1,
                        "input_snapshot": previous["input_snapshot"],
                        "reference_snapshot": previous["reference_snapshot"],
                        "request_snapshot": None,
                        "raw_response": None,
                        "parsed_prediction": None,
                        "metric_evidence": None,
                        "score": None,
                        "latency_ms": None,
                        "input_tokens": None,
                        "output_tokens": None,
                        "estimated_cost": None,
                        "error_type": None,
                        "error_message": None,
                        "status": SampleAttemptStatus.PENDING.value,
                        "created_at": _utc_now(),
                        "started_at": None,
                        "completed_at": None,
                    }
                )
            attempts = [
                attempt
                for attempt in self._repository.list_attempts(str(task["run_id"]))
                if str(attempt["task_id"]) == str(task["id"])
            ]
            latest = _latest_attempts(attempts)
        return [
            latest[sample_id]
            for sample_id in sample_ids
            if sample_id in latest and latest[sample_id].get("status") == SampleAttemptStatus.PENDING.value
        ]

    def _record_result(
        self,
        run: dict[str, Any],
        attempt: dict[str, Any],
        result: SampleExecutionResult,
        endpoint: dict[str, Any],
        lease_token: str,
        *,
        cipher: SecretCipher,
        model_executor: ModelExecutor,
    ) -> dict[str, Any]:
        values: dict[str, Any] = {
            "request_snapshot": result.request_snapshot,
            "raw_response": result.raw_response,
            "parsed_prediction": result.prediction,
            "latency_ms": result.latency_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "estimated_cost": _estimate_cost(endpoint, result.input_tokens, result.output_tokens),
            "metric_evidence": build_execution_metric_evidence(
                token_logprobs=result.token_logprobs,
                existing=(attempt.get("metric_evidence") if isinstance(attempt.get("metric_evidence"), dict) else None),
            ),
            "completed_at": _utc_now(),
        }
        if result.success and result.prediction is not None:
            reference = attempt.get("reference_snapshot")
            scoring = reference.get("scoring") if isinstance(reference, dict) else None
            if is_llm_judge_rule(scoring):
                checkpoint = self._repository.update_attempt(
                    str(attempt["id"]),
                    {**values, "score": None, "error_type": None, "error_message": None},
                )
                if checkpoint is None:
                    raise ConflictError("Task lease was lost before result persistence.")
                evidence = self._automatic_judge(
                    run,
                    checkpoint,
                    cipher=cipher,
                    model_executor=model_executor,
                )
                self._require_lease(str(attempt["task_id"]), lease_token)
                stored = self._repository.complete_attempt(
                    str(attempt["id"]),
                    lease_token,
                    {
                        "metric_evidence": {**values["metric_evidence"], "llm_judge": evidence},
                        "status": SampleAttemptStatus.SUCCEEDED.value,
                    },
                )
                if stored is None:
                    raise ConflictError("Task lease was lost before judge evidence persistence.")
                return stored
            try:
                values.update(
                    {
                        "score": score_prediction(result.prediction, dict(reference or {})),
                        "status": SampleAttemptStatus.SUCCEEDED.value,
                        "error_type": None,
                        "error_message": None,
                    }
                )
            except ScoringError as error:
                values.update(
                    {
                        "score": None,
                        "status": SampleAttemptStatus.FAILED.value,
                        "error_type": "scoring_error",
                        "error_message": str(error),
                    }
                )
        else:
            values.update(
                {
                    "score": None,
                    "status": SampleAttemptStatus.FAILED.value,
                    "error_type": result.error_type or "execution_error",
                    "error_message": result.error_message or "Sample execution failed.",
                }
            )
        stored = self._repository.complete_attempt(str(attempt["id"]), lease_token, values)
        if stored is None:
            raise ConflictError("Task lease was lost before result persistence.")
        return stored

    def _automatic_judge(
        self,
        run: dict[str, Any],
        attempt: dict[str, Any],
        *,
        cipher: SecretCipher,
        model_executor: ModelExecutor,
    ) -> dict[str, object]:
        configuration = run.get("configuration_snapshot")
        configuration = configuration if isinstance(configuration, dict) else {}
        judge = configuration.get("judge") if isinstance(configuration.get("judge"), dict) else {}
        endpoint = judge.get("endpoint") if isinstance(judge.get("endpoint"), dict) else {}
        endpoint_id = endpoint.get("id")
        system_message = judge.get("system_message")
        if not isinstance(endpoint_id, str) or not endpoint_id:
            return judge_failure_evidence("Frozen judge endpoint configuration is missing.")
        if not isinstance(system_message, str) or not system_message:
            return judge_failure_evidence("Frozen judge system message is missing.")
        try:
            assessment = self._repository.assess_judge(
                sample_attempt_id=str(attempt["id"]),
                judge_endpoint_id=endpoint_id,
                rubric={"source": "llm_judge_metric", "reference_field": judge.get("reference_field")},
                system_message=system_message,
                cipher=cipher,
                model_executor=model_executor,
                endpoint_override=endpoint,
            )
        except JudgeAssessmentError as error:
            return judge_failure_evidence(str(error))
        return judge_assessment_evidence(assessment)

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
        delay = _retry_delay_seconds(
            int(task["attempt_count"]),
            policy,
            provider_retry_after_seconds=provider_retry_after_seconds,
        )
        payload = _task_payload(task)
        previous_wait = _nonnegative_float(payload.get("retry_total_wait_seconds", 0))
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
        latest = _latest_attempts(
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
        payload = {key: value for key, value in _task_payload(task).items() if key != "retry_sample_ids"}
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
            self._enqueue_stage(updated, task, TaskType.SCORING.value)
        return updated, task

    def _update_progress(self, run_id: str, retry_sample_ids: list[str]) -> dict[str, Any]:
        latest = _latest_attempts(self._repository.list_attempts(run_id))
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

    def _enqueue_stage(
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
        now = _utc_now()
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


def _latest_attempts(attempts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        sample_id = str(attempt["sample_id"])
        previous = latest.get(sample_id)
        if previous is None or int(attempt.get("attempt_number", 1)) > int(previous.get("attempt_number", 1)):
            latest[sample_id] = attempt
    return latest


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


def _task_payload(task: dict[str, Any]) -> dict[str, Any]:
    payload = task.get("payload")
    return dict(payload) if isinstance(payload, dict) else {}


def _lease_clear() -> dict[str, Any]:
    return {
        "leased_by": None,
        "lease_token": None,
        "lease_expires_at": None,
        "heartbeat_at": None,
    }


def _estimate_cost(endpoint: dict[str, Any], input_tokens: int | None, output_tokens: int | None) -> float | None:
    if input_tokens is None and output_tokens is None:
        return None
    input_cost = (input_tokens or 0) * (float(endpoint.get("input_cost_per_million") or 0) / 1_000_000)
    output_cost = (output_tokens or 0) * (float(endpoint.get("output_cost_per_million") or 0) / 1_000_000)
    return round(input_cost + output_cost, 12)


def _is_retryable(error_type: str | None, policy: dict[str, Any]) -> bool:
    if error_type in {"timeout", "connection_error"}:
        return True
    if error_type == "response_parse_error":
        return bool(policy["retry_response_parse_errors"])
    if not error_type or not error_type.startswith("http_"):
        return False
    try:
        status_code = int(error_type.removeprefix("http_"))
    except ValueError:
        return False
    return status_code in {408, 409, 425, 429} or 500 <= status_code <= 599


def _retry_policy(payload: dict[str, Any]) -> dict[str, Any]:
    configured = payload.get("retry_policy") if isinstance(payload, dict) else None
    configured = configured if isinstance(configured, dict) else {}
    strategy = configured.get("strategy", DEFAULT_RETRY_POLICY["strategy"])
    if strategy not in {"fixed", "exponential", "exponential_jitter"}:
        strategy = DEFAULT_RETRY_POLICY["strategy"]
    return {
        "max_attempts": max(1, int(configured.get("max_attempts", DEFAULT_RETRY_POLICY["max_attempts"]))),
        "base_delay_seconds": max(
            0,
            int(configured.get("base_delay_seconds", DEFAULT_RETRY_POLICY["base_delay_seconds"])),
        ),
        "max_delay_seconds": max(
            0,
            int(configured.get("max_delay_seconds", DEFAULT_RETRY_POLICY["max_delay_seconds"])),
        ),
        "strategy": strategy,
        "jitter_ratio": min(
            1.0,
            max(0.0, float(configured.get("jitter_ratio", DEFAULT_RETRY_POLICY["jitter_ratio"]))),
        ),
        "max_total_wait_seconds": max(
            0,
            int(configured.get("max_total_wait_seconds", DEFAULT_RETRY_POLICY["max_total_wait_seconds"])),
        ),
        "respect_retry_after": bool(configured.get("respect_retry_after", DEFAULT_RETRY_POLICY["respect_retry_after"])),
        "retry_response_parse_errors": bool(
            configured.get(
                "retry_response_parse_errors",
                DEFAULT_RETRY_POLICY["retry_response_parse_errors"],
            )
        ),
    }


def _retry_delay_seconds(
    attempt_count: int,
    policy: dict[str, Any],
    *,
    provider_retry_after_seconds: float | None,
) -> float:
    base_delay = float(policy["base_delay_seconds"])
    delay = base_delay if policy["strategy"] == "fixed" else base_delay * (2 ** max(0, attempt_count - 1))
    delay = min(float(policy["max_delay_seconds"]), delay)
    if policy["strategy"] == "exponential_jitter" and delay:
        delay *= 1 + random.uniform(-policy["jitter_ratio"], policy["jitter_ratio"])
    if policy["respect_retry_after"] and provider_retry_after_seconds is not None:
        delay = max(delay, provider_retry_after_seconds)
    return round(max(0.0, delay), 3)


def _nonnegative_float(value: object) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
