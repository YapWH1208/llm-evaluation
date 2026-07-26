from __future__ import annotations

"""Document-store execution path for durable benchmark tasks.

The API and worker layers use these functions only when the configured primary
database is MongoDB.  All storage-specific operations remain in
``MongoDocumentStore``; the execution behaviour mirrors the relational path.
"""

from datetime import datetime, timedelta, timezone
import base64
from typing import Any

from app.benchmarks import get_installed_plugin
from app.core.secrets import SecretCipher
from app.db.mongo import MongoDocumentStore
from app.services.evaluation_runs import _build_messages, _estimate_request_tokens
from app.services.model_executor import ModelExecutor, SampleExecutionResult, normalize_exact_match
from app.services.run_analysis import summarize_attempts
from app.services.content_ir import ContentValidationError, normalize_content_parts
from app.services.media_assets import MediaAssetError, safe_asset_path
from app.services.run_executor import _is_retryable, _retry_delay_seconds, _retry_policy
from app.services.request_body import resolve_request_body
from app.services.prompt_templates import standardization_flags


class MongoRunExecutionError(ValueError):
    """Raised when a document-backed run cannot be created or executed safely."""


def create_mongo_benchmark_run(
    store: MongoDocumentStore,
    *,
    model_endpoint_id: str,
    sample_limit: int | None,
    prompt_package_id: str | None,
    benchmark_id: str,
    benchmark_version: str,
    suite_id: str | None = None,
    suite_snapshot: dict[str, object] | None = None,
    request_body_override: dict[str, object] | None = None,
    created_by: str | None = None,
    max_concurrency: int | None = None,
) -> dict[str, Any]:
    endpoint = store.get_document("model_endpoints", model_endpoint_id)
    if endpoint is None:
        raise MongoRunExecutionError("Model endpoint not found.")
    if endpoint.get("status") != "available":
        raise MongoRunExecutionError("Model endpoint must pass a connection test before scheduling a run.")
    definitions = store.list_documents("benchmark_definitions", query={"benchmark_id": benchmark_id, "version": benchmark_version})
    if definitions and definitions[0].get("status") in {"disabled", "deprecated", "broken"}:
        raise MongoRunExecutionError(f"Benchmark {benchmark_id}@{benchmark_version} is {definitions[0]['status']} and cannot be scheduled.")
    plugin = get_installed_plugin(benchmark_id, benchmark_version)
    if plugin is None:
        raise MongoRunExecutionError("Benchmark plugin is not installed for the requested version.")
    samples = plugin.samples(sample_limit)
    if not samples:
        raise MongoRunExecutionError("At least one benchmark sample is required.")
    compatibility = _capability_compatibility(store, model_endpoint_id, plugin.manifest)
    if compatibility["unsupported"]:
        raise MongoRunExecutionError(
            "Model endpoint is incompatible with required benchmark capabilities: "
            + ", ".join(compatibility["unsupported"])
        )
    prompt_package = store.get_document("prompt_packages", prompt_package_id) if prompt_package_id else None
    if prompt_package_id and prompt_package is None:
        raise MongoRunExecutionError("Prompt package not found.")

    request_body_evidence = _mongo_request_body_evidence(
        endpoint=endpoint,
        benchmark_manifest=plugin.manifest,
        suite_snapshot=suite_snapshot,
        request_body_override=request_body_override,
    )

    prompt_proxy = _proxy(prompt_package) if prompt_package else None
    now = _utc_now()
    snapshot = {
        "benchmark": {"id": benchmark_id, "version": benchmark_version, "manifest": plugin.manifest},
        "endpoint": {
            "id": endpoint["id"],
            "base_url": endpoint["base_url"],
            "model_name": endpoint["model_name"],
            "protocol_profile": endpoint.get("protocol_profile", "openai_chat_completions"),
            "default_request_body": endpoint.get("default_request_body", {}),
        },
        "sample_ids": [sample.sample_id for sample in samples],
        "capability_compatibility": compatibility,
        "prompt_package": (
            {
                "id": prompt_package["id"],
                "name": prompt_package["name"],
                "version": prompt_package["version"],
                "system_message": prompt_package.get("system_message"),
                "user_template": prompt_package["user_template"],
                "few_shot_examples": prompt_package.get("few_shot_examples", []),
            }
            if prompt_package
            else None
        ),
        "prompt_standardization": (
            {"is_standard": not standardization_flags(_proxy(prompt_package)), "flags": standardization_flags(_proxy(prompt_package))}
            if prompt_package else {"is_standard": True, "flags": []}
        ),
        "evaluation_suite": suite_snapshot,
        "request_body_evidence": request_body_evidence,
    }
    run = store.insert_document(
        "evaluation_runs",
        {
            "model_endpoint_id": model_endpoint_id,
            "prompt_package_id": prompt_package_id,
            "suite_id": suite_id,
            "created_by": created_by,
            "max_concurrency": max_concurrency,
            "benchmark_id": benchmark_id,
            "benchmark_version": benchmark_version,
            "configuration_snapshot": snapshot,
            "status": "queued",
            "total_samples": len(samples),
            "completed_samples": 0,
            "successful_samples": 0,
            "failed_samples": 0,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
        },
    )
    task = store.insert_document(
        "task_units",
        {
            "run_id": run["id"],
            "task_type": "evaluation_shard",
            "payload": {
                "sample_ids": [sample.sample_id for sample in samples],
                "estimated_request_count": len(samples),
                "estimated_token_count": sum(_estimate_request_tokens(sample.prompt) for sample in samples),
                "retry_policy": {"max_attempts": 3, "base_delay_seconds": 2, "max_delay_seconds": 60},
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
    for sample in samples:
        store.insert_document(
            "sample_attempts",
            {
                "run_id": run["id"],
                "task_id": task["id"],
                "sample_id": sample.sample_id,
                "attempt_number": 1,
                "input_snapshot": {"messages": _build_messages(sample.prompt, prompt_proxy), "modality": "text", "request_body_evidence": request_body_evidence},
                "reference_snapshot": {"type": "exact_match", "answer": sample.reference_answer},
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
    return run


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
        model_defaults=endpoint.get("default_request_body") if isinstance(endpoint.get("default_request_body"), dict) else None,
        suite_defaults=suite_defaults if isinstance(suite_defaults, dict) else None,
        benchmark_defaults=benchmark_defaults if isinstance(benchmark_defaults, dict) else None,
        run_override=request_body_override,
        benchmark_forced=benchmark_forced if isinstance(benchmark_forced, dict) else None,
    )


def create_mongo_custom_multimodal_run(
    store: MongoDocumentStore,
    *,
    data_root: str,
    model_endpoint_id: str,
    sample_id: str,
    messages: list[dict[str, Any]],
    reference_answer: str,
    created_by: str | None = None,
    max_concurrency: int | None = None,
) -> dict[str, Any]:
    endpoint = store.get_document("model_endpoints", model_endpoint_id)
    if endpoint is None: raise MongoRunExecutionError("Model endpoint not found.")
    if endpoint.get("status") != "available": raise MongoRunExecutionError("Model endpoint must pass a connection test before scheduling a run.")
    if not sample_id.strip() or not reference_answer.strip(): raise MongoRunExecutionError("Custom samples require a sample ID and reference answer.")
    normalized = _normalize_mongo_messages(store, data_root, messages)
    request_body_evidence = resolve_request_body(protocol_profile=str(endpoint.get("protocol_profile", "openai_chat_completions")), model_defaults=endpoint.get("default_request_body") if isinstance(endpoint.get("default_request_body"), dict) else None)
    now = _utc_now()
    run = store.insert_document("evaluation_runs", {"model_endpoint_id":model_endpoint_id,"prompt_package_id":None,"suite_id":None,"created_by":created_by,"max_concurrency":max_concurrency,"benchmark_id":"custom-multimodal","benchmark_version":"1.0.0","configuration_snapshot":{"benchmark":{"id":"custom-multimodal","version":"1.0.0","source":"user"},"endpoint":{"id":endpoint["id"],"model_name":endpoint["model_name"],"protocol_profile":endpoint.get("protocol_profile","openai_chat_completions")},"sample_ids":[sample_id],"request_body_evidence":request_body_evidence},"status":"queued","total_samples":1,"completed_samples":0,"successful_samples":0,"failed_samples":0,"created_at":now,"started_at":None,"completed_at":None})
    task = store.insert_document("task_units", {"run_id":run["id"],"task_type":"evaluation_shard","payload":{"sample_ids":[sample_id],"estimated_request_count":1,"estimated_token_count":_estimate_message_tokens(normalized),"retry_policy":{"max_attempts":3,"base_delay_seconds":2,"max_delay_seconds":60}},"status":"pending","priority":0,"attempt_count":0,"leased_by":None,"lease_token":None,"lease_expires_at":None,"next_retry_at":None,"heartbeat_at":None,"created_at":now,"updated_at":now})
    store.insert_document("sample_attempts", {"run_id":run["id"],"task_id":task["id"],"sample_id":sample_id.strip(),"attempt_number":1,"input_snapshot":{"messages":normalized,"modality":_sample_modality(normalized),"request_body_evidence":request_body_evidence},"reference_snapshot":{"type":"exact_match","answer":reference_answer},"request_snapshot":None,"raw_response":None,"parsed_prediction":None,"score":None,"latency_ms":None,"input_tokens":None,"output_tokens":None,"estimated_cost":None,"error_type":None,"error_message":None,"status":"pending","created_at":now,"started_at":None,"completed_at":None})
    return run


def execute_mongo_queued_run(
    store: MongoDocumentStore,
    *,
    run_id: str,
    cipher: SecretCipher,
    model_executor: ModelExecutor,
) -> dict[str, Any]:
    run = store.get_document("evaluation_runs", run_id)
    if run is None:
        raise MongoRunExecutionError("Evaluation run not found.")
    if run["status"] != "queued":
        raise MongoRunExecutionError("Only queued evaluation runs can be executed.")
    task = store.claim_task(worker_id="interactive-api", lease_seconds=600, run_id=run_id)
    if task is None or not task.get("lease_token"):
        raise MongoRunExecutionError("No due task is available for this evaluation run.")
    run, _ = execute_mongo_leased_task(
        store,
        task_id=str(task["id"]),
        lease_token=str(task["lease_token"]),
        cipher=cipher,
        model_executor=model_executor,
    )
    return run


def clone_mongo_run(store: MongoDocumentStore, run_id: str) -> dict[str, Any]:
    source = store.get_document("evaluation_runs", run_id)
    if source is None:
        raise MongoRunExecutionError("Evaluation run not found.")
    return create_mongo_benchmark_run(
        store,
        model_endpoint_id=str(source["model_endpoint_id"]),
        sample_limit=int(source["total_samples"]),
        prompt_package_id=source.get("prompt_package_id"),
        benchmark_id=str(source["benchmark_id"]),
        benchmark_version=str(source["benchmark_version"]),
        suite_id=source.get("suite_id"),
        created_by=source.get("created_by"),
        max_concurrency=source.get("max_concurrency"),
    )


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
    source_tasks = store.list_documents("task_units", query={"run_id": run_id}, sort=[("created_at", -1)])
    source_payload = _task_payload(source_tasks[0]) if source_tasks else {}
    retry_policy = source_payload.get("retry_policy") if isinstance(source_payload.get("retry_policy"), dict) else {"max_attempts": 3, "base_delay_seconds": 2, "max_delay_seconds": 60}
    now = _utc_now()
    task = store.insert_document(
        "task_units",
        {
            "run_id": run_id,
            "task_type": "evaluation_shard",
            "payload": {
                "sample_ids": [attempt["sample_id"] for attempt in failed],
                "estimated_request_count": len(failed),
                "estimated_token_count": 0,
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
    for attempt in failed:
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
) -> tuple[dict[str, Any], dict[str, Any]]:
    task = store.get_document("task_units", task_id)
    if task is None:
        raise MongoRunExecutionError("Task not found.")
    if not _has_valid_lease(task, lease_token):
        raise MongoRunExecutionError("Task lease is no longer valid.")
    if task["task_type"] != "evaluation_shard":
        raise MongoRunExecutionError("Unsupported task type.")
    run = store.get_document("evaluation_runs", str(task["run_id"]))
    if run is None:
        raise MongoRunExecutionError("Evaluation run not found.")
    if run["status"] not in {"queued", "running"}:
        store.update_document("task_units", task_id, _lease_values("cancelled"))
        raise MongoRunExecutionError("Evaluation run is not executable in its current state.")
    endpoint = store.get_document("model_endpoints", str(run["model_endpoint_id"]))
    if endpoint is None:
        raise MongoRunExecutionError("The model endpoint for this run no longer exists.")

    now = _utc_now()
    store.update_document("evaluation_runs", run["id"], {"status": "running", "started_at": run.get("started_at") or now})
    task = store.update_document(
        "task_units",
        task_id,
        {"status": "running", "attempt_count": int(task.get("attempt_count", 0)) + 1},
    )
    assert task is not None
    policy = _retry_policy(_task_payload(task))
    attempts = _prepare_attempts(store, task)
    api_key = cipher.decrypt(str(endpoint["encrypted_api_key"]))
    retry_sample_ids: list[str] = []
    provider_retry_after_seconds: float | None = None
    for attempt in attempts:
        started_at = _utc_now()
        store.update_document("sample_attempts", str(attempt["id"]), {"status": "running", "started_at": started_at, "completed_at": None})
        result = model_executor.execute(_proxy(endpoint), api_key, attempt["input_snapshot"])
        stored = _record_result(store, attempt, result, endpoint)
        if not result.success and _is_retryable(result.error_type, policy):
            retry_sample_ids.append(str(stored["sample_id"]))
            if result.retry_after_seconds is not None:
                provider_retry_after_seconds = max(provider_retry_after_seconds or 0.0, result.retry_after_seconds)

    retry_sample_ids = sorted(set(retry_sample_ids))
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
            task = store.update_document(
                "task_units",
                task_id,
                {
                    "payload": payload,
                    "status": "retry_scheduled",
                    "next_retry_at": _utc_now() + timedelta(seconds=delay),
                    **_lease_values(),
                },
            )
            assert task is not None
            run = _update_run_progress(store, run["id"])
            run = store.update_document("evaluation_runs", run["id"], {"status": "queued"})
            assert run is not None
            return run, task
        payload.update({"retry_exhausted_reason": "max_total_wait_seconds", "retry_total_wait_seconds": prior_wait})
        task = store.update_document("task_units", task_id, {"payload": payload})
        assert task is not None

    run = _update_run_progress(store, run["id"])
    terminal_status = "completed_with_errors" if int(run["failed_samples"]) else "completed"
    task_status = "failed" if int(run["failed_samples"]) else "succeeded"
    task = store.update_document(
        "task_units",
        task_id,
        {"status": task_status, "next_retry_at": None, **_lease_values()},
    )
    run = store.update_document("evaluation_runs", run["id"], {"status": terminal_status, "completed_at": _utc_now()})
    assert task is not None and run is not None
    return run, task


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
    return summarize_attempts(
        [_proxy(attempt) for attempt in latest.values()],
        total_samples=int(run["total_samples"]),
        currency=str(endpoint["currency"]) if endpoint else None,
    )


def _prepare_attempts(store: MongoDocumentStore, task: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _task_payload(task)
    sample_ids = [value for value in payload.get("retry_sample_ids") or payload.get("sample_ids") or [] if isinstance(value, str)]
    latest = _latest_attempts(store, str(task["id"]))
    if int(task["attempt_count"]) > 1:
        for sample_id in sample_ids:
            previous = latest.get(sample_id)
            if previous is None or previous.get("status") != "failed":
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


def _record_result(
    store: MongoDocumentStore,
    attempt: dict[str, Any],
    result: SampleExecutionResult,
    endpoint: dict[str, Any],
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "request_snapshot": result.request_snapshot,
        "raw_response": result.raw_response,
        "parsed_prediction": result.prediction,
        "latency_ms": result.latency_ms,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "estimated_cost": _estimate_cost(endpoint, result.input_tokens, result.output_tokens),
        "completed_at": _utc_now(),
    }
    if result.success and result.prediction is not None:
        values.update(
            {
                "score": float(
                    normalize_exact_match(result.prediction)
                    == normalize_exact_match(str(attempt["reference_snapshot"]["answer"]))
                ),
                "status": "succeeded",
                "error_type": None,
                "error_message": None,
            }
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
    stored = store.update_document("sample_attempts", str(attempt["id"]), values)
    assert stored is not None
    return stored


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


def _normalize_mongo_messages(store: MongoDocumentStore, data_root: str, messages: list[dict[str, Any]]) -> list[dict[str, object]]:
    if not messages: raise MongoRunExecutionError("Custom samples require at least one message.")
    normalized: list[dict[str, object]] = []
    for message in messages:
        role, content = message.get("role"), message.get("content")
        if not isinstance(role, str) or not role: raise MongoRunExecutionError("Each message requires a role.")
        if isinstance(content, str) and content:
            normalized.append({"role":role,"content":content}); continue
        if not isinstance(content, list): raise MongoRunExecutionError("Message content must be text or a content-part list.")
        try: parts = normalize_content_parts(content)
        except ContentValidationError as error: raise MongoRunExecutionError(str(error)) from error
        normalized.append({"role":role,"content":[_resolve_mongo_asset(store,data_root,part) for part in parts]})
    return normalized


def _resolve_mongo_asset(store: MongoDocumentStore, data_root: str, part: dict[str, Any]) -> dict[str, object]:
    if part["type"] in {"text", "tool_result"} or not isinstance(part.get("source"),dict) or not part["source"].get("asset_id"): return part
    asset_id = part["source"]["asset_id"]
    if not isinstance(asset_id,str): raise MongoRunExecutionError("Media asset ID must be a string.")
    asset = store.get_document("media_assets",asset_id)
    if asset is None: raise MongoRunExecutionError("Referenced media asset was not found.")
    try: encoded = base64.b64encode(safe_asset_path(data_root,str(asset["storage_path"])).read_bytes()).decode("ascii")
    except MediaAssetError as error: raise MongoRunExecutionError(str(error)) from error
    return {"type":part["type"],"source":{"base64_data":encoded},"mime_type":str(asset["mime_type"])}


def _sample_modality(messages: list[dict[str, object]]) -> str:
    kinds = {part["type"] for message in messages if isinstance(message.get("content"),list) for part in message["content"] if isinstance(part,dict) and part.get("type") != "text"}
    return "+".join(sorted(kinds | {"text"}))


def _estimate_message_tokens(messages: list[dict[str, object]]) -> int:
    text_length = sum(len(content) for message in messages if isinstance((content := message.get("content")),str))
    return max(32, (text_length + 3) // 4 + 32)


def _has_valid_lease(task: dict[str, Any], lease_token: str) -> bool:
    expires_at = task.get("lease_expires_at")
    if not isinstance(expires_at, datetime):
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return bool(task.get("lease_token") == lease_token and task.get("status") in {"leased", "running"} and expires_at >= _utc_now())


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


def _nonnegative_float(value: object) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
