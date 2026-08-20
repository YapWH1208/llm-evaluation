from __future__ import annotations

"""Document-store execution path for durable benchmark tasks.

The API and worker layers use these functions only when the configured primary
database is MongoDB.  All storage-specific operations remain in
``MongoDocumentStore``; the execution behaviour mirrors the relational path.
"""

from datetime import datetime, timedelta, timezone
import json
from typing import Any

from app.core.config import Settings
from app.core.secrets import SecretCipher
from app.db.mongo import MongoDocumentStore
from app.modules.evaluations.service import (
    RunCreationError,
    _split_items_for_endpoint_budget,
)
from app.modules.reviews.scoring import (
    JudgeScoringError,
    is_llm_judge_rule,
    judge_assessment_evidence,
    judge_failure_evidence,
    normalize_judge_rule,
    validate_judge_endpoint,
)
from app.modules.reviews.judges import JudgeAssessmentError
from app.modules.reviews.mongo_judges import assess_mongo_sample_attempt
from app.infrastructure.providers.contracts import ModelExecutor, SampleExecutionResult
from app.modules.benchmarks.scoring import ScoringError, score_prediction
from app.modules.analytics.aggregation import AGGREGATION_VERSION, recompute_mongo_aggregate_metrics
from app.modules.benchmarks.metrics import build_execution_metric_evidence
from app.modules.reports.service import ReportError
from app.modules.evaluations.analysis import add_summary_insights, summarize_attempts
from app.modules.evaluations.executor import _is_retryable, _retry_delay_seconds, _retry_policy
from app.infrastructure.providers.common import resolve_request_body
from app.modules.datasets.repositories import MongoDatasetRepository
from app.modules.datasets.service import DatasetService


class MongoRunExecutionError(ValueError):
    """Raised when a document-backed run cannot be created or executed safely."""


def _mongo_judge_endpoint_for_rule(
    store: MongoDocumentStore,
    *,
    scoring_rule: dict[str, object],
    evaluated_endpoint_id: str,
) -> dict[str, Any] | None:
    if not is_llm_judge_rule(scoring_rule):
        return None
    normalized = normalize_judge_rule(scoring_rule)
    endpoint = store.get_document("model_endpoints", normalized["judge_endpoint_id"])
    try:
        validate_judge_endpoint(
            normalized,
            evaluated_endpoint_id=evaluated_endpoint_id,
            judge_endpoint=endpoint,
        )
    except JudgeScoringError as error:
        raise MongoRunExecutionError(str(error)) from error
    return endpoint


def _dataset_run_manifest() -> dict[str, object]:
    from app.modules.evaluations.dataset_runs import _DATASET_RUN_MANIFEST

    return dict(_DATASET_RUN_MANIFEST)


def _mongo_request_body_evidence(
    *,
    endpoint: dict[str, Any],
    benchmark_manifest: dict[str, object],
    suite_snapshot: dict[str, object] | None,
    request_body_override: dict[str, object] | None,
) -> dict[str, object]:
    suite_defaults = suite_snapshot.get("default_request_body") if isinstance(suite_snapshot, dict) else None
    benchmark_defaults = benchmark_manifest.get("default_request_body")
    benchmark_forced = benchmark_manifest.get("forced_request_body")
    if not isinstance(benchmark_forced, dict):
        benchmark_forced = benchmark_manifest.get("required_request_body")
    return resolve_request_body(
        protocol_profile=str(endpoint.get("protocol_profile", "openai_chat_completions")),
        model_defaults=endpoint.get("default_request_body")
        if isinstance(endpoint.get("default_request_body"), dict)
        else None,
        suite_defaults=suite_defaults if isinstance(suite_defaults, dict) else None,
        benchmark_defaults=benchmark_defaults if isinstance(benchmark_defaults, dict) else None,
        run_override=request_body_override,
        benchmark_forced=benchmark_forced if isinstance(benchmark_forced, dict) else None,
    )


def execute_mongo_queued_run(
    store: MongoDocumentStore,
    *,
    run_id: str,
    cipher: SecretCipher,
    model_executor: ModelExecutor,
    data_root: str = "data",
    settings: Settings | None = None,
) -> dict[str, Any]:
    run = store.get_document("evaluation_runs", run_id)
    if run is None:
        raise MongoRunExecutionError("Evaluation run not found.")
    if run["status"] not in {"queued", "running"}:
        raise MongoRunExecutionError("Only queued or running evaluation runs can be executed.")
    while True:
        task = store.claim_task(worker_id="interactive-api", lease_seconds=600, run_id=run_id)
        if task is None or not task.get("lease_token"):
            current = store.get_document("evaluation_runs", run_id)
            if current is not None and current.get("status") in {
                "queued",
                "running",
                "completed",
                "completed_with_errors",
            }:
                return current
            raise MongoRunExecutionError("No due task is available for this evaluation run.")
        run, _ = execute_mongo_leased_task(
            store,
            task_id=str(task["id"]),
            lease_token=str(task["lease_token"]),
            cipher=cipher,
            model_executor=model_executor,
            data_root=data_root,
            settings=settings,
        )
        if run.get("status") in {"completed", "completed_with_errors"}:
            return run


def retry_failed_mongo_samples(store: MongoDocumentStore, run_id: str) -> dict[str, Any]:
    run = store.get_document("evaluation_runs", run_id)
    if run is None:
        raise MongoRunExecutionError("Evaluation run not found.")
    if run["status"] not in {"completed", "completed_with_errors"}:
        raise MongoRunExecutionError("Only completed evaluation runs can retry failed samples.")
    attempts = store.list_documents(
        "sample_attempts", query={"run_id": run_id}, sort=[("sample_id", 1), ("attempt_number", -1)]
    )
    latest: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        latest.setdefault(str(attempt["sample_id"]), attempt)
    failed = [attempt for attempt in latest.values() if attempt.get("status") == "failed"]
    if not failed:
        raise MongoRunExecutionError("This run has no failed samples to retry.")
    endpoint = store.get_document("model_endpoints", str(run["model_endpoint_id"]))
    if endpoint is None:
        raise MongoRunExecutionError("The model endpoint for this run no longer exists.")
    source_tasks = [
        task
        for task in store.list_documents("task_units", query={"run_id": run_id}, sort=[("created_at", -1)])
        if task.get("task_type") == "evaluation_shard"
    ]
    source_payload = _task_payload(source_tasks[0]) if source_tasks else {}
    retry_policy = (
        source_payload.get("retry_policy")
        if isinstance(source_payload.get("retry_policy"), dict)
        else {"max_attempts": 3, "base_delay_seconds": 2, "max_delay_seconds": 60}
    )
    benchmark_tasks = [
        task
        for task in store.list_documents("task_units", query={"run_id": run_id}, sort=[("created_at", -1)])
        if task.get("task_type") == "benchmark"
    ]
    now = _utc_now()
    try:
        retry_groups = _split_items_for_endpoint_budget(
            (tuple(failed),), endpoint, token_estimate=_estimate_mongo_retry_attempt_tokens
        )
    except RunCreationError as error:
        raise MongoRunExecutionError(str(error)) from error
    for group in retry_groups:
        token_estimates = {
            str(attempt["sample_id"]): _estimate_mongo_retry_attempt_tokens(attempt) for attempt in group
        }
        task = store.insert_document(
            "task_units",
            {
                "run_id": run_id,
                "parent_task_id": benchmark_tasks[0]["id"] if benchmark_tasks else None,
                "task_type": "evaluation_shard",
                "payload": {
                    "sample_ids": [attempt["sample_id"] for attempt in group],
                    "estimated_request_count": len(group),
                    "estimated_token_count": sum(token_estimates.values()),
                    "sample_token_estimates": token_estimates,
                    "retry_policy": retry_policy,
                    "manual_retry": True,
                },
                "status": "pending",
                "priority": 0,
                "attempt_count": 0,
                "leased_by": None,
                "lease_token": None,
                "lease_expires_at": None,
                "next_retry_at": None,
                "heartbeat_at": None,
                "created_at": now,
                "updated_at": now,
            },
        )
        for attempt in group:
            store.insert_document(
                "sample_attempts",
                {
                    "run_id": run_id,
                    "task_id": task["id"],
                    "sample_id": attempt["sample_id"],
                    "attempt_number": int(attempt["attempt_number"]) + 1,
                    "input_snapshot": attempt["input_snapshot"],
                    "reference_snapshot": attempt["reference_snapshot"],
                    "request_snapshot": None,
                    "raw_response": None,
                    "parsed_prediction": None,
                    "score": None,
                    "latency_ms": None,
                    "input_tokens": None,
                    "output_tokens": None,
                    "estimated_cost": None,
                    "error_type": None,
                    "error_message": None,
                    "status": "pending",
                    "created_at": now,
                    "started_at": None,
                    "completed_at": None,
                },
            )
    updated = store.update_document("evaluation_runs", run_id, {"status": "queued", "completed_at": None})
    assert updated is not None
    return updated


def execute_mongo_leased_task(
    store: MongoDocumentStore,
    *,
    task_id: str,
    lease_token: str,
    cipher: SecretCipher,
    model_executor: ModelExecutor,
    data_root: str = "data",
    settings: Settings | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    task = store.get_document("task_units", task_id)
    if task is None:
        raise MongoRunExecutionError("Task not found.")
    _require_current_mongo_lease(store, task_id, lease_token)
    if task["task_type"] == "scoring":
        return _execute_mongo_scoring_task(store, task, lease_token)
    if task["task_type"] == "aggregation":
        return _execute_mongo_aggregation_task(store, task, lease_token)
    if task["task_type"] == "report_generation":
        return _execute_mongo_report_task(store, task, lease_token, data_root=data_root)
    if task["task_type"] in {"dataset_preparation", "benchmark", "judge", "cleanup"}:
        return _execute_mongo_stage_task(store, task, lease_token, data_root=data_root, settings=settings)
    if task["task_type"] != "evaluation_shard":
        raise MongoRunExecutionError("Unsupported task type.")
    run = store.get_document("evaluation_runs", str(task["run_id"]))
    if run is None:
        raise MongoRunExecutionError("Evaluation run not found.")
    if run["status"] not in {"queued", "running"}:
        raise MongoRunExecutionError("Evaluation run is not executable in its current state.")
    endpoint = store.get_document("model_endpoints", str(run["model_endpoint_id"]))
    if endpoint is None:
        raise MongoRunExecutionError("The model endpoint for this run no longer exists.")

    frozen_endpoint = _frozen_mongo_endpoint(run, endpoint)
    now = _utc_now()
    run = store.update_document_if(
        "evaluation_runs",
        str(run["id"]),
        {"status": {"$in": ["queued", "running"]}},
        {"status": "running", "started_at": run.get("started_at") or now},
    )
    if run is None:
        raise MongoRunExecutionError("Evaluation run is no longer executable.")
    task = store.update_task_if_current_lease(
        task,
        lease_token,
        {"status": "running", "attempt_count": int(task.get("attempt_count", 0)) + 1},
    )
    if task is None:
        raise MongoRunExecutionError("Task lease was lost before execution started.")
    policy = _retry_policy(_task_payload(task))
    attempts = _prepare_attempts(store, task)
    api_key = cipher.decrypt(str(endpoint["encrypted_api_key"]))
    retry_sample_ids: list[str] = []
    provider_retry_after_seconds: float | None = None
    for attempt in attempts:
        _require_current_mongo_lease(store, task_id, lease_token)
        _require_runnable_mongo_run(store, str(run["id"]))
        started_at = _utc_now()
        started = store.update_document_if(
            "sample_attempts",
            str(attempt["id"]),
            {"status": "pending"},
            {"status": "running", "started_at": started_at, "completed_at": None, "worker_lease_token": lease_token},
        )
        if started is None:
            raise MongoRunExecutionError("Sample attempt is no longer available for this task lease.")
        result = model_executor.execute(_proxy(frozen_endpoint), api_key, attempt["input_snapshot"])
        _require_current_mongo_lease(store, task_id, lease_token)
        stored = _record_result(
            store,
            run,
            attempt,
            result,
            frozen_endpoint,
            lease_token,
            cipher=cipher,
            model_executor=model_executor,
        )
        if not result.success and _is_retryable(result.error_type, policy):
            retry_sample_ids.append(str(stored["sample_id"]))
            if result.retry_after_seconds is not None:
                provider_retry_after_seconds = max(provider_retry_after_seconds or 0.0, result.retry_after_seconds)

    retry_sample_ids = sorted(set(retry_sample_ids))
    _require_current_mongo_lease(store, task_id, lease_token)
    if retry_sample_ids and int(task["attempt_count"]) < int(policy["max_attempts"]):
        delay = _retry_delay_seconds(
            int(task["attempt_count"]), policy, provider_retry_after_seconds=provider_retry_after_seconds
        )
        payload = _task_payload(task)
        prior_wait = _nonnegative_float(payload.get("retry_total_wait_seconds", 0))
        if prior_wait + delay <= float(policy["max_total_wait_seconds"]):
            payload.update(
                {
                    "retry_sample_ids": retry_sample_ids,
                    "retry_total_wait_seconds": round(prior_wait + delay, 3),
                    "last_retry_delay_seconds": delay,
                }
            )
            task = store.update_task_if_current_lease(
                task,
                lease_token,
                {
                    "payload": payload,
                    "status": "retry_scheduled",
                    "next_retry_at": _utc_now() + timedelta(seconds=delay),
                    **_lease_values(),
                },
            )
            if task is None:
                raise MongoRunExecutionError("Task lease was lost before retry scheduling.")
            for attempt in _latest_attempts(store, str(task["id"])).values():
                if str(attempt["sample_id"]) in retry_sample_ids and attempt.get("status") == "failed":
                    store.update_document("sample_attempts", str(attempt["id"]), {"status": "retry_scheduled"})
            run = _update_run_progress(store, run["id"])
            run = store.update_document_if(
                "evaluation_runs", str(run["id"]), {"status": {"$in": ["queued", "running"]}}, {"status": "queued"}
            )
            if run is None:
                raise MongoRunExecutionError("Evaluation run is no longer executable.")
            return run, task
        payload.update({"retry_exhausted_reason": "max_total_wait_seconds", "retry_total_wait_seconds": prior_wait})
        task = store.update_task_if_current_lease(task, lease_token, {"payload": payload})
        if task is None:
            raise MongoRunExecutionError("Task lease was lost before finalization.")

    _require_current_mongo_lease(store, task_id, lease_token)
    run = _update_run_progress(store, run["id"])
    task = store.update_task_if_current_lease(
        task,
        lease_token,
        {"status": "succeeded", "next_retry_at": None, **_lease_values()},
    )
    if task is None:
        raise MongoRunExecutionError("Task lease was lost before finalization.")
    incomplete_shards = [
        candidate
        for candidate in store.list_documents(
            "task_units", query={"run_id": run["id"], "task_type": "evaluation_shard"}
        )
        if candidate["id"] != task_id and candidate.get("status") in {"pending", "leased", "running", "retry_scheduled"}
    ]
    if incomplete_shards:
        run = store.update_document_if(
            "evaluation_runs",
            str(run["id"]),
            {"status": {"$in": ["queued", "running"]}},
            {"status": "running", "completed_at": None},
        )
        if run is None:
            raise MongoRunExecutionError("Evaluation run is no longer executable.")
        return run, task
    run = store.update_document_if(
        "evaluation_runs",
        str(run["id"]),
        {"status": {"$in": ["queued", "running"]}},
        {"status": "scoring", "completed_at": None},
    )
    if run is None:
        raise MongoRunExecutionError("Evaluation run is no longer executable.")
    _enqueue_mongo_stage_task(store, run, parent_task=task, task_type="scoring")
    return run, task


def _execute_mongo_stage_task(
    store: MongoDocumentStore,
    task: dict[str, Any],
    lease_token: str,
    *,
    data_root: str,
    settings: Settings | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    run = store.get_document("evaluation_runs", str(task["run_id"]))
    if run is None:
        raise MongoRunExecutionError("Evaluation run not found.")
    task = _require_current_mongo_lease(store, str(task["id"]), lease_token)
    task = store.update_task_if_current_lease(
        task, lease_token, {"status": "running", "attempt_count": int(task.get("attempt_count", 0)) + 1}
    )
    if task is None:
        raise MongoRunExecutionError("Task lease was lost before execution started.")
    now = _utc_now()
    payload = _task_payload(task)
    if task["task_type"] == "dataset_preparation":
        try:
            for descriptor in payload.get("datasets", []):
                if not isinstance(descriptor, dict) or not isinstance(descriptor.get("dataset_id"), str):
                    continue
                frozen_id = descriptor.get("dataset_version_id")
                if isinstance(frozen_id, str):
                    dataset = store.get_document("dataset_versions", frozen_id)
                else:
                    query = {"dataset_id": descriptor["dataset_id"]}
                    if isinstance(descriptor.get("version"), str):
                        query["version"] = descriptor["version"]
                    if isinstance(descriptor.get("revision"), str):
                        query["revision"] = descriptor["revision"]
                    matches = store.list_documents("dataset_versions", query=query, sort=[("created_at", -1)])
                    dataset = matches[0] if matches else None
                if dataset is None:
                    raise MongoRunExecutionError(f"Required dataset {descriptor['dataset_id']} is not registered.")
                if dataset.get("status") != "ready":
                    DatasetService(MongoDatasetRepository(store)).download(str(dataset["id"]), data_root, settings)
        except Exception as error:
            failed = store.update_task_if_current_lease(
                task,
                lease_token,
                {"status": "retry_scheduled", "payload": {**payload, "dataset_error": str(error)}, **_lease_values()},
            )
            if failed is None:
                raise MongoRunExecutionError("Task lease was lost before retry scheduling.") from error
            raise MongoRunExecutionError(str(error)) from error
    updated_task = store.update_task_if_current_lease(
        task,
        lease_token,
        {
            "status": "succeeded",
            "payload": {**payload, "worker_interface": task["task_type"], "stage_completed_at": now.isoformat()},
            **_lease_values(),
        },
    )
    if updated_task is None:
        raise MongoRunExecutionError("Task lease was lost before finalization.")
    if task["task_type"] == "dataset_preparation" and run.get("status") == "waiting_for_dataset":
        run = store.update_document_if(
            "evaluation_runs", str(run["id"]), {"status": "waiting_for_dataset"}, {"status": "queued"}
        )
        if run is None:
            raise MongoRunExecutionError("Evaluation run is no longer executable.")
    return run, updated_task


def _execute_mongo_scoring_task(
    store: MongoDocumentStore,
    task: dict[str, Any],
    lease_token: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    run = store.get_document("evaluation_runs", str(task["run_id"]))
    if run is None:
        raise MongoRunExecutionError("Evaluation run not found.")
    if run.get("status") not in {"scoring", "running"}:
        raise MongoRunExecutionError("Evaluation run is not ready for scoring.")
    task = _require_current_mongo_lease(store, str(task["id"]), lease_token)
    task = store.update_task_if_current_lease(
        task, lease_token, {"status": "running", "attempt_count": int(task.get("attempt_count", 0)) + 1}
    )
    if task is None:
        raise MongoRunExecutionError("Task lease was lost before execution started.")
    run = store.update_document_if(
        "evaluation_runs", str(run["id"]), {"status": {"$in": ["scoring", "running"]}}, {"status": "scoring"}
    )
    if run is None:
        raise MongoRunExecutionError("Evaluation run is no longer executable.")
    attempts = _latest_run_attempts(store, str(run["id"]))
    task = store.update_task_if_current_lease(
        task,
        lease_token,
        {
            "payload": {
                **_task_payload(task),
                "scored_samples": sum(item.get("score") is not None for item in attempts.values()),
                "failed_samples": sum(item.get("status") == "failed" for item in attempts.values()),
                "deterministic_scoring": "verified",
            },
            "status": "succeeded",
            **_lease_values(),
        },
    )
    if task is None:
        raise MongoRunExecutionError("Task lease was lost before finalization.")
    run = store.update_document_if("evaluation_runs", str(run["id"]), {"status": "scoring"}, {"status": "aggregating"})
    if run is None:
        raise MongoRunExecutionError("Evaluation run is no longer executable.")
    _enqueue_mongo_stage_task(store, run, parent_task=task, task_type="aggregation")
    return run, task


def _execute_mongo_aggregation_task(
    store: MongoDocumentStore,
    task: dict[str, Any],
    lease_token: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    run = store.get_document("evaluation_runs", str(task["run_id"]))
    if run is None:
        raise MongoRunExecutionError("Evaluation run not found.")
    if run.get("status") not in {"aggregating", "scoring"}:
        raise MongoRunExecutionError("Evaluation run is not ready for aggregation.")
    task = _require_current_mongo_lease(store, str(task["id"]), lease_token)
    task = store.update_task_if_current_lease(
        task, lease_token, {"status": "running", "attempt_count": int(task.get("attempt_count", 0)) + 1}
    )
    if task is None:
        raise MongoRunExecutionError("Task lease was lost before execution started.")
    run = store.update_document_if(
        "evaluation_runs", str(run["id"]), {"status": {"$in": ["aggregating", "scoring"]}}, {"status": "aggregating"}
    )
    if run is None:
        raise MongoRunExecutionError("Evaluation run is no longer executable.")
    metrics = recompute_mongo_aggregate_metrics(store, str(run["id"]))
    task = store.update_task_if_current_lease(
        task,
        lease_token,
        {
            "payload": {
                **_task_payload(task),
                "metric_count": len(metrics),
                "aggregation_version": AGGREGATION_VERSION,
            },
            "status": "succeeded",
            **_lease_values(),
        },
    )
    if task is None:
        raise MongoRunExecutionError("Task lease was lost before finalization.")
    run = store.update_document_if(
        "evaluation_runs",
        str(run["id"]),
        {"status": "aggregating"},
        {"status": "generating_report", "completed_at": None},
    )
    if run is None:
        raise MongoRunExecutionError("Evaluation run is no longer executable.")
    _enqueue_mongo_stage_task(store, run, parent_task=task, task_type="report_generation")
    return run, task


def _execute_mongo_report_task(
    store: MongoDocumentStore,
    task: dict[str, Any],
    lease_token: str,
    *,
    data_root: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    run = store.get_document("evaluation_runs", str(task["run_id"]))
    if run is None:
        raise MongoRunExecutionError("Evaluation run not found.")
    if run.get("status") != "generating_report":
        raise MongoRunExecutionError("Evaluation run is not ready for report generation.")
    task = _require_current_mongo_lease(store, str(task["id"]), lease_token)
    task = store.update_task_if_current_lease(
        task, lease_token, {"status": "running", "attempt_count": int(task.get("attempt_count", 0)) + 1}
    )
    if task is None:
        raise MongoRunExecutionError("Task lease was lost before execution started.")
    payload = _task_payload(task)
    try:
        from app.modules.reports.mongo import generate_mongo_report

        report = generate_mongo_report(
            store,
            str(run["id"]),
            str(payload.get("format", "html")),
            data_root,
            report_type=str(payload.get("report_type", "single_model")),
        )
    except ReportError as error:
        task = store.update_task_if_current_lease(
            task,
            lease_token,
            {"status": "failed", "payload": {**payload, "report_error": str(error)}, **_lease_values()},
        )
        if task is None:
            raise MongoRunExecutionError("Task lease was lost before finalization.") from error
        run = store.update_document_if(
            "evaluation_runs",
            str(run["id"]),
            {"status": "generating_report"},
            {
                "status": str(
                    payload.get(
                        "terminal_status", "completed_with_errors" if int(run.get("failed_samples", 0)) else "completed"
                    )
                ),
                "completed_at": _utc_now(),
            },
        )
        if run is None:
            raise MongoRunExecutionError("Evaluation run is no longer executable.") from error
        raise MongoRunExecutionError(str(error)) from error
    task = store.update_task_if_current_lease(
        task,
        lease_token,
        {
            "status": "succeeded",
            "payload": {**payload, "report_id": report["id"], "artifact_path": report["artifact_path"]},
            **_lease_values(),
        },
    )
    if task is None:
        raise MongoRunExecutionError("Task lease was lost before finalization.")
    final_status = "completed_with_errors" if int(run.get("failed_samples", 0)) else "completed"
    run = store.update_document_if(
        "evaluation_runs",
        str(run["id"]),
        {"status": "generating_report"},
        {"status": final_status, "completed_at": _utc_now()},
    )
    if run is None:
        raise MongoRunExecutionError("Evaluation run is no longer executable.")
    return run, task


def _enqueue_mongo_stage_task(
    store: MongoDocumentStore,
    run: dict[str, Any],
    *,
    parent_task: dict[str, Any],
    task_type: str,
) -> dict[str, Any]:
    existing = [
        task
        for task in store.list_documents("task_units", query={"run_id": run["id"]})
        if task.get("parent_task_id") == parent_task["id"] and task.get("task_type") == task_type
    ]
    if existing:
        return existing[0]
    now = _utc_now()
    return store.insert_document(
        "task_units",
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
                        "terminal_status": "completed_with_errors"
                        if int(run.get("failed_samples", 0))
                        else "completed",
                    }
                    if task_type == "report_generation"
                    else {}
                ),
            },
            "status": "pending",
            "priority": int(parent_task.get("priority", 0)),
            "attempt_count": 0,
            "leased_by": None,
            "lease_token": None,
            "lease_expires_at": None,
            "next_retry_at": None,
            "heartbeat_at": None,
            "created_at": now,
            "updated_at": now,
        },
    )


def build_mongo_run_summary(store: MongoDocumentStore, run_id: str) -> dict[str, Any]:
    run = store.get_document("evaluation_runs", run_id)
    if run is None:
        raise MongoRunExecutionError("Evaluation run not found.")
    endpoint = store.get_document("model_endpoints", str(run["model_endpoint_id"]))
    attempts = store.list_documents(
        "sample_attempts", query={"run_id": run_id}, sort=[("sample_id", 1), ("attempt_number", -1)]
    )
    latest: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        latest.setdefault(str(attempt["sample_id"]), attempt)
    attempts = [_proxy(attempt) for attempt in latest.values()]
    return add_summary_insights(
        summarize_attempts(
            attempts,
            total_samples=int(run["total_samples"]),
            currency=str(endpoint["currency"]) if endpoint else None,
        ),
        attempts,
    )


def _prepare_attempts(store: MongoDocumentStore, task: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _task_payload(task)
    sample_ids = [
        value for value in payload.get("retry_sample_ids") or payload.get("sample_ids") or [] if isinstance(value, str)
    ]
    latest = _latest_attempts(store, str(task["id"]))
    if int(task["attempt_count"]) > 1:
        for sample_id in sample_ids:
            previous = latest.get(sample_id)
            if previous is None or previous.get("status") not in {"failed", "retry_scheduled"}:
                continue
            created_at = _utc_now()
            store.insert_document(
                "sample_attempts",
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
                    "score": None,
                    "latency_ms": None,
                    "input_tokens": None,
                    "output_tokens": None,
                    "estimated_cost": None,
                    "error_type": None,
                    "error_message": None,
                    "status": "pending",
                    "created_at": created_at,
                    "started_at": None,
                    "completed_at": None,
                },
            )
        latest = _latest_attempts(store, str(task["id"]))
    return [
        latest[sample_id]
        for sample_id in sample_ids
        if sample_id in latest and latest[sample_id].get("status") == "pending"
    ]


def _latest_attempts(store: MongoDocumentStore, task_id: str) -> dict[str, dict[str, Any]]:
    attempts = store.list_documents(
        "sample_attempts", query={"task_id": task_id}, sort=[("sample_id", 1), ("attempt_number", -1)]
    )
    latest: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        latest.setdefault(str(attempt["sample_id"]), attempt)
    return latest


def _latest_run_attempts(store: MongoDocumentStore, run_id: str) -> dict[str, dict[str, Any]]:
    attempts = store.list_documents(
        "sample_attempts", query={"run_id": run_id}, sort=[("sample_id", 1), ("attempt_number", -1)]
    )
    latest: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        latest.setdefault(str(attempt["sample_id"]), attempt)
    return latest


def _record_result(
    store: MongoDocumentStore,
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
            existing=attempt.get("metric_evidence") if isinstance(attempt.get("metric_evidence"), dict) else None,
        ),
        "completed_at": _utc_now(),
    }
    if result.success and result.prediction is not None:
        if is_llm_judge_rule(attempt.get("reference_snapshot", {}).get("scoring")):
            values.update({"score": None, "error_type": None, "error_message": None})
            stored = store.update_document_if(
                "sample_attempts",
                str(attempt["id"]),
                {"status": "running", "worker_lease_token": lease_token},
                values,
            )
            if stored is None:
                raise MongoRunExecutionError("Task lease was lost before result persistence.")
            evidence = _automatic_mongo_judge_evidence(
                store,
                run,
                stored,
                cipher=cipher,
                model_executor=model_executor,
            )
            _require_current_mongo_lease(store, str(attempt["task_id"]), lease_token)
            completed = store.update_document_if(
                "sample_attempts",
                str(attempt["id"]),
                {"status": "running", "worker_lease_token": lease_token},
                {
                    "metric_evidence": {**values["metric_evidence"], "llm_judge": evidence},
                    "status": "succeeded",
                    "worker_lease_token": None,
                },
            )
            if completed is None:
                raise MongoRunExecutionError("Task lease was lost before judge evidence persistence.")
            return completed
        try:
            values.update(
                {
                    "score": score_prediction(result.prediction, attempt["reference_snapshot"]),
                    "status": "succeeded",
                    "error_type": None,
                    "error_message": None,
                }
            )
        except ScoringError as error:
            values.update(
                {"score": None, "status": "failed", "error_type": "scoring_error", "error_message": str(error)}
            )
    else:
        values.update(
            {
                "score": None,
                "status": "failed",
                "error_type": result.error_type or "execution_error",
                "error_message": result.error_message or "Sample execution failed.",
            }
        )
    stored = store.update_document_if(
        "sample_attempts",
        str(attempt["id"]),
        {"status": "running", "worker_lease_token": lease_token},
        {**values, "worker_lease_token": None},
    )
    if stored is None:
        raise MongoRunExecutionError("Task lease was lost before result persistence.")
    return stored


def _automatic_mongo_judge_evidence(
    store: MongoDocumentStore,
    run: dict[str, Any],
    attempt: dict[str, Any],
    *,
    cipher: SecretCipher,
    model_executor: ModelExecutor,
) -> dict[str, object]:
    """Run the frozen judge configuration without changing target execution status."""

    configuration = run.get("configuration_snapshot") if isinstance(run.get("configuration_snapshot"), dict) else {}
    judge = configuration.get("judge") if isinstance(configuration.get("judge"), dict) else {}
    endpoint = judge.get("endpoint") if isinstance(judge.get("endpoint"), dict) else {}
    judge_endpoint_id = endpoint.get("id")
    system_message = judge.get("system_message")
    if not isinstance(judge_endpoint_id, str) or not judge_endpoint_id:
        return judge_failure_evidence("Frozen judge endpoint configuration is missing.")
    if not isinstance(system_message, str) or not system_message:
        return judge_failure_evidence("Frozen judge system message is missing.")
    try:
        assessment = assess_mongo_sample_attempt(
            store,
            sample_attempt_id=str(attempt["id"]),
            judge_endpoint_id=judge_endpoint_id,
            rubric={
                "source": "llm_judge_metric",
                "reference_field": judge.get("reference_field"),
            },
            system_message=system_message,
            cipher=cipher,
            model_executor=model_executor,
            endpoint_override=endpoint,
        )
    except JudgeAssessmentError as error:
        return judge_failure_evidence(str(error))
    return judge_assessment_evidence(assessment)


def _update_run_progress(store: MongoDocumentStore, run_id: str) -> dict[str, Any]:
    attempts = store.list_documents(
        "sample_attempts", query={"run_id": run_id}, sort=[("sample_id", 1), ("attempt_number", -1)]
    )
    latest: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        latest.setdefault(str(attempt["sample_id"]), attempt)
    completed = sum(item.get("status") in {"succeeded", "failed"} for item in latest.values())
    successful = sum(item.get("status") == "succeeded" for item in latest.values())
    failed = sum(item.get("status") == "failed" for item in latest.values())
    run = store.update_document(
        "evaluation_runs",
        run_id,
        {"completed_samples": completed, "successful_samples": successful, "failed_samples": failed},
    )
    assert run is not None
    return run


def _capability_compatibility(
    store: MongoDocumentStore,
    endpoint_id: str,
    manifest: dict[str, object],
) -> dict[str, list[str]]:
    required = [item for item in manifest.get("required_capabilities", []) if isinstance(item, str)]
    records = {
        str(item["capability_key"]): item
        for item in store.list_documents("model_capabilities", query={"model_endpoint_id": endpoint_id})
    }
    unsupported = [
        capability
        for capability in required
        if records.get(capability, {}).get("effective_status") in {"unsupported", "detected_user_unsupported"}
    ]
    unverified = [
        capability
        for capability in required
        if capability not in records or records[capability].get("effective_status") == "unverified"
    ]
    return {"required": required, "unsupported": unsupported, "unverified": unverified}


def _estimate_mongo_retry_attempt_tokens(attempt: object) -> int:
    """Recover a conservative quota estimate from a persisted Mongo attempt."""

    value = attempt if isinstance(attempt, dict) else {}
    snapshot = value.get("input_snapshot") if isinstance(value.get("input_snapshot"), dict) else {}
    messages = snapshot.get("messages") if isinstance(snapshot.get("messages"), list) else []
    encoded = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    media_parts = sum(
        1
        for message in messages
        if isinstance(message, dict) and isinstance(message.get("content"), list)
        for part in message["content"]
        if isinstance(part, dict) and part.get("type") not in {"text", "tool_result"}
    )
    return max(1, (len(encoded) + 3) // 4) + 32 + (media_parts * 256)


def _lease_values(status: str | None = None) -> dict[str, Any]:
    values: dict[str, Any] = {
        "leased_by": None,
        "lease_token": None,
        "lease_expires_at": None,
        "heartbeat_at": None,
    }
    if status is not None:
        values["status"] = status
    return values


def _task_payload(task: dict[str, Any]) -> dict[str, Any]:
    payload = task.get("payload")
    return dict(payload) if isinstance(payload, dict) else {}


def _estimate_cost(endpoint: dict[str, Any], input_tokens: int | None, output_tokens: int | None) -> float | None:
    if input_tokens is None and output_tokens is None:
        return None
    input_cost = (input_tokens or 0) * (float(endpoint.get("input_cost_per_million") or 0) / 1_000_000)
    output_cost = (output_tokens or 0) * (float(endpoint.get("output_cost_per_million") or 0) / 1_000_000)
    return round(input_cost + output_cost, 12)


def _proxy(document: dict[str, Any]) -> Any:
    return type("DocumentEndpoint", (), document)()


def _frozen_mongo_endpoint(run: dict[str, Any], endpoint: dict[str, Any]) -> dict[str, Any]:
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


def _require_current_mongo_lease(store: MongoDocumentStore, task_id: str, lease_token: str) -> dict[str, Any]:
    task = store.get_document("task_units", task_id)
    if task is None:
        raise MongoRunExecutionError("Task lease was lost before result persistence.")
    fenced = store.update_task_if_current_lease(task, lease_token)
    if fenced is None:
        raise MongoRunExecutionError("Task lease was lost before result persistence.")
    return fenced


def _require_runnable_mongo_run(store: MongoDocumentStore, run_id: str) -> None:
    run = store.get_document("evaluation_runs", run_id)
    if run is None or run.get("status") not in {"queued", "running"}:
        raise MongoRunExecutionError("Evaluation run is no longer executable.")


def _nonnegative_float(value: object) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _positive_limit(value: object) -> int | None:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return None
    return limit if limit > 0 else None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
