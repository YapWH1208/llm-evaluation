from __future__ import annotations

"""Document-store execution path for durable benchmark tasks.

The API and worker layers use these functions only when the configured primary
database is MongoDB.  All storage-specific operations remain in
``MongoDocumentStore``; the execution behaviour mirrors the relational path.
"""

from datetime import datetime, timedelta, timezone
import base64
import json
from typing import Any

from app.benchmarks import get_installed_plugin
from app.benchmarks.registry import BenchmarkSample
from app.core.config import Settings
from app.core.secrets import SecretCipher
from app.db.mongo import MongoDocumentStore
from app.services.evaluation_runs import (
    RunCreationError,
    _build_sample_messages,
    _estimate_sample_tokens,
    _split_items_for_endpoint_budget,
    _sample_modality as _benchmark_sample_modality,
    _split_samples_for_endpoint_budget,
)
from app.services.dataset_runs import (
    DATASET_RUN_BENCHMARK_ID,
    DATASET_RUN_BENCHMARK_VERSION,
    DatasetRunError,
    _build_dataset_samples,
    _empty_dataset_samples_message,
)
from app.services.dataset_records import DatasetRecordError
from app.services.model_executor import ModelExecutor, SampleExecutionResult
from app.services.scoring import ScoringError, score_prediction, validate_scoring_rule
from app.services.aggregation import recompute_mongo_aggregate_metrics
from app.services.reports import ReportError
from app.services.run_analysis import add_summary_insights, summarize_attempts
from app.services.content_ir import ContentValidationError, normalize_content_parts
from app.services.media_assets import MediaAssetError, safe_asset_path
from app.services.run_executor import _is_retryable, _retry_delay_seconds, _retry_policy
from app.services.request_body import resolve_request_body
from app.services.prompt_templates import standardization_flags
from app.services.mongo_datasets import download_mongo_dataset


class MongoRunExecutionError(ValueError):
    """Raised when a document-backed run cannot be created or executed safely."""


def preflight_mongo_benchmark_run(
    store: MongoDocumentStore,
    *,
    model_endpoint_id: str,
    sample_limit: int | None,
    prompt_package_id: str | None,
    benchmark_id: str,
    benchmark_version: str,
    request_body_override: dict[str, object] | None = None,
) -> dict[str, object]:
    """Return queue-readiness and estimates without writing Mongo documents."""

    endpoint = store.get_document("model_endpoints", model_endpoint_id)
    issues: list[str] = []
    if endpoint is None:
        return {"can_queue": False, "issues": ["Model endpoint not found."], "sample_count": 0, "estimated_requests": 0, "estimated_input_tokens": 0, "estimated_output_tokens": 0, "estimated_cost": None, "currency": None, "compatibility": {"required": [], "unsupported": [], "unverified": []}, "datasets": [], "request_body_evidence": None}
    if endpoint.get("status") != "available":
        issues.append("Model endpoint must pass a connection test before scheduling a run.")
    definitions = store.list_documents("benchmark_definitions", query={"benchmark_id": benchmark_id, "version": benchmark_version})
    if definitions and definitions[0].get("status") in {"disabled", "deprecated", "broken"}:
        issues.append(f"Benchmark {benchmark_id}@{benchmark_version} is {definitions[0]['status']} and cannot be scheduled.")
    plugin = get_installed_plugin(benchmark_id, benchmark_version)
    if plugin is None:
        return {"can_queue": False, "issues": [*issues, "Benchmark plugin is not installed for the requested version."], "sample_count": 0, "estimated_requests": 0, "estimated_input_tokens": 0, "estimated_output_tokens": 0, "estimated_cost": None, "currency": endpoint.get("currency"), "compatibility": {"required": [], "unsupported": [], "unverified": []}, "datasets": [], "request_body_evidence": None}
    samples = plugin.samples(sample_limit)
    if not samples:
        issues.append("At least one benchmark sample is required.")
    compatibility = _capability_compatibility(store, model_endpoint_id, plugin.manifest)
    if compatibility["unsupported"]:
        issues.append("Model endpoint is incompatible with required benchmark capabilities: " + ", ".join(compatibility["unsupported"]))
    prompt_package = store.get_document("prompt_packages", prompt_package_id) if prompt_package_id else None
    if prompt_package_id and prompt_package is None:
        issues.append("Prompt package not found.")
    try:
        validate_scoring_rule(_mongo_effective_scoring_rule(plugin.manifest, prompt_package))
    except ScoringError as error:
        issues.append(f"Scoring rule is invalid: {error}")
    datasets: list[dict[str, object]] = []
    for descriptor in plugin.manifest.get("datasets", []):
        if not isinstance(descriptor, dict) or not isinstance(descriptor.get("dataset_id"), str):
            continue
        query: dict[str, Any] = {"dataset_id": descriptor["dataset_id"]}
        if isinstance(descriptor.get("version"), str): query["version"] = descriptor["version"]
        if isinstance(descriptor.get("revision"), str): query["revision"] = descriptor["revision"]
        matches = store.list_documents("dataset_versions", query=query, sort=[("created_at", -1)])
        if not matches:
            if isinstance(descriptor.get("source_url"), str) and descriptor["source_url"].strip():
                datasets.append({"dataset_id": descriptor["dataset_id"], "version": descriptor.get("version", "default"), "revision": descriptor.get("revision", "default"), "status": "will_register", "will_prepare": True})
            else:
                issues.append(f"Required dataset {descriptor['dataset_id']} is not registered.")
                datasets.append({"dataset_id": descriptor["dataset_id"], "status": "missing", "will_prepare": False})
        else:
            dataset = matches[0]
            datasets.append({"id": dataset["id"], "dataset_id": dataset["dataset_id"], "version": dataset["version"], "revision": dataset["revision"], "status": dataset["status"], "will_prepare": dataset["status"] != "ready"})
    estimated_input_tokens = sum(_estimate_sample_tokens(sample) for sample in samples)
    estimated_output_tokens = len(samples) * 64
    input_cost = endpoint.get("input_cost_per_million")
    output_cost = endpoint.get("output_cost_per_million")
    estimated_cost = ((estimated_input_tokens * float(input_cost) + estimated_output_tokens * float(output_cost)) / 1_000_000) if input_cost is not None and output_cost is not None else None
    return {
        "can_queue": not issues,
        "issues": issues,
        "sample_count": len(samples),
        "estimated_requests": len(samples),
        "estimated_input_tokens": estimated_input_tokens,
        "estimated_output_tokens": estimated_output_tokens,
        "estimated_cost": estimated_cost,
        "currency": endpoint.get("currency"),
        "compatibility": compatibility,
        "datasets": datasets,
        "request_body_evidence": resolve_request_body(protocol_profile=str(endpoint.get("protocol_profile", "openai_chat_completions")), model_defaults=endpoint.get("default_request_body") if isinstance(endpoint.get("default_request_body"), dict) else None, run_override=request_body_override),
    }


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
    declared_datasets: list[dict[str, object]] | None = None,
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
    frozen_datasets = _freeze_mongo_declared_datasets(
        store,
        declared_datasets if declared_datasets is not None else plugin.manifest.get("datasets"),
    )

    request_body_evidence = _mongo_request_body_evidence(
        endpoint=endpoint,
        benchmark_manifest=plugin.manifest,
        suite_snapshot=suite_snapshot,
        request_body_override=request_body_override,
    )
    scoring_rule = _mongo_effective_scoring_rule(plugin.manifest, prompt_package)
    try:
        validate_scoring_rule(scoring_rule)
    except ScoringError as error:
        raise MongoRunExecutionError(f"Scoring rule is invalid: {error}") from error

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
            "timeout_seconds": endpoint.get("timeout_seconds", 60),
            "custom_headers": endpoint.get("custom_headers", {}),
            "input_cost_per_million": endpoint.get("input_cost_per_million"),
            "output_cost_per_million": endpoint.get("output_cost_per_million"),
        },
        "sample_ids": [sample.sample_id for sample in samples],
        "datasets": frozen_datasets,
        "capability_compatibility": compatibility,
        "prompt_package": (
            {
                "id": prompt_package["id"],
                "name": prompt_package["name"],
                "version": prompt_package["version"],
                "system_message": prompt_package.get("system_message"),
                "user_template": prompt_package["user_template"],
                "few_shot_examples": prompt_package.get("few_shot_examples", []),
                "scoring_rule": prompt_package.get("scoring_rule"),
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
            "status": "waiting_for_dataset" if frozen_datasets else "queued",
            "total_samples": len(samples),
            "completed_samples": 0,
            "successful_samples": 0,
            "failed_samples": 0,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
        },
    )
    dataset_task = store.insert_document(
        "task_units",
        {
            "run_id": run["id"],
            "parent_task_id": None,
            "task_type": "dataset_preparation",
            "payload": {"datasets": frozen_datasets, "prepared_inline": not bool(frozen_datasets)},
            "status": "pending" if frozen_datasets else "succeeded",
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
    benchmark_task = store.insert_document(
        "task_units",
        {
            "run_id": run["id"],
            "parent_task_id": dataset_task["id"],
            "task_type": "benchmark",
            "payload": {"benchmark_id": benchmark_id, "benchmark_version": benchmark_version, "planned_samples": len(samples)},
            "status": "pending" if frozen_datasets else "succeeded",
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
    try:
        shards = _split_samples_for_endpoint_budget(samples, plugin.manifest, endpoint)
    except RunCreationError as error:
        raise MongoRunExecutionError(str(error)) from error
    for shard_index, shard_samples in enumerate(shards, start=1):
        task = store.insert_document(
            "task_units",
            {
                "run_id": run["id"],
                "parent_task_id": benchmark_task["id"],
                "task_type": "evaluation_shard",
                "payload": {
                    "sample_ids": [sample.sample_id for sample in shard_samples],
                    "estimated_request_count": len(shard_samples),
                    "estimated_token_count": sum(_estimate_sample_tokens(sample) for sample in shard_samples),
                    "sample_token_estimates": {
                        sample.sample_id: _estimate_sample_tokens(sample) for sample in shard_samples
                    },
                    "shard_index": shard_index,
                    "shard_count": len(shards),
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
        for sample in shard_samples:
            store.insert_document(
                "sample_attempts",
                {
                    "run_id": run["id"],
                    "task_id": task["id"],
                    "sample_id": sample.sample_id,
                    "attempt_number": 1,
                    "input_snapshot": {"messages": _build_sample_messages(sample, prompt_proxy), "modality": _benchmark_sample_modality(sample), "metadata": dict(sample.metadata), "request_body_evidence": request_body_evidence},
                    "reference_snapshot": {"type": str(scoring_rule.get("type", "exact_match")), "answer": sample.reference_answer, "scoring": scoring_rule},
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


def create_mongo_dataset_run(
    store: MongoDocumentStore,
    *,
    data_root: str,
    model_endpoint_id: str,
    dataset_version_id: str,
    prompt_package_id: str | None,
    reference_field: str,
    sample_limit: int,
    input_field: str | None = None,
    request_body_override: dict[str, object] | None = None,
    created_by: str | None = None,
    max_concurrency: int | None = None,
) -> dict[str, Any]:
    endpoint = store.get_document("model_endpoints", model_endpoint_id)
    if endpoint is None:
        raise MongoRunExecutionError("Model endpoint not found.")
    if endpoint.get("status") != "available":
        raise MongoRunExecutionError("Model endpoint must pass a connection test before scheduling a run.")
    dataset = store.get_document("dataset_versions", dataset_version_id)
    if dataset is None:
        raise MongoRunExecutionError("Dataset version not found.")
    if dataset.get("status") != "ready" or not dataset.get("prepared_path"):
        raise MongoRunExecutionError(f"Dataset {dataset['dataset_id']} v{dataset['version']} is not ready; download and verify it before running.")
    prompt_package = store.get_document("prompt_packages", prompt_package_id) if prompt_package_id else None
    if prompt_package_id and prompt_package is None:
        raise MongoRunExecutionError("Prompt package not found.")
    if not reference_field.strip():
        raise MongoRunExecutionError("A reference field is required.")
    selected_input_field = input_field.strip() if input_field and input_field.strip() else None
    try:
        samples, skipped = _build_dataset_samples(
            prepared_path=dataset["prepared_path"],
            data_root=data_root,
            sample_limit=sample_limit,
            input_field=selected_input_field,
            reference_field=reference_field.strip(),
            prompt_package=_proxy(prompt_package) if prompt_package else None,
            dataset_id=dataset["dataset_id"],
            dataset_version=dataset["version"],
        )
    except (DatasetRecordError, DatasetRunError) as error:
        raise MongoRunExecutionError(str(error)) from error
    if not samples:
        raise MongoRunExecutionError(_empty_dataset_samples_message(
            sample_limit=sample_limit,
            input_field=selected_input_field,
            reference_field=reference_field.strip(),
        ))
    compatibility = _capability_compatibility(store, model_endpoint_id, _dataset_run_manifest())
    if compatibility["unsupported"]:
        raise MongoRunExecutionError(
            "Model endpoint is incompatible with dataset evaluation: " + ", ".join(compatibility["unsupported"])
        )
    scoring_rule = dict(prompt_package.get("scoring_rule")) if prompt_package and isinstance(prompt_package.get("scoring_rule"), dict) and prompt_package.get("scoring_rule") else {"type": "exact_match"}
    try:
        validate_scoring_rule(scoring_rule)
    except ScoringError as error:
        raise MongoRunExecutionError(f"Scoring rule is invalid: {error}") from error
    request_body_evidence = _mongo_request_body_evidence(
        endpoint=endpoint,
        benchmark_manifest=_dataset_run_manifest(),
        suite_snapshot=None,
        request_body_override=request_body_override,
    )
    frozen_datasets = [{
        "dataset_id": dataset["dataset_id"],
        "version": dataset["version"],
        "revision": dataset.get("revision", "default"),
        "dataset_version_id": dataset["id"],
    }]
    now = _utc_now()
    snapshot = {
        "benchmark": {"id": DATASET_RUN_BENCHMARK_ID, "version": DATASET_RUN_BENCHMARK_VERSION, "source": "user", "manifest": _dataset_run_manifest()},
        "endpoint": {
            "id": endpoint["id"],
            "base_url": endpoint["base_url"],
            "model_name": endpoint["model_name"],
            "protocol_profile": endpoint.get("protocol_profile", "openai_chat_completions"),
            "default_request_body": endpoint.get("default_request_body", {}),
            "timeout_seconds": endpoint.get("timeout_seconds", 60),
            "custom_headers": endpoint.get("custom_headers", {}),
            "input_cost_per_million": endpoint.get("input_cost_per_million"),
            "output_cost_per_million": endpoint.get("output_cost_per_million"),
        },
        "datasets": frozen_datasets,
        "dataset_version": {"id": dataset["id"], "dataset_id": dataset["dataset_id"], "version": dataset["version"], "revision": dataset.get("revision", "default")},
        "input_field": selected_input_field,
        "reference_field": reference_field.strip(),
        "sample_limit": sample_limit,
        "skipped_records": skipped,
        "sample_ids": [sample.sample_id for sample in samples],
        "capability_compatibility": compatibility,
        "prompt_package": (
            {"id": prompt_package["id"], "name": prompt_package["name"], "version": prompt_package["version"],
             "system_message": prompt_package.get("system_message"), "user_template": prompt_package["user_template"],
             "few_shot_examples": prompt_package.get("few_shot_examples", []), "scoring_rule": prompt_package.get("scoring_rule")}
            if prompt_package else None
        ),
        "request_body_evidence": request_body_evidence,
    }
    run = store.insert_document(
        "evaluation_runs",
        {
            "model_endpoint_id": model_endpoint_id,
            "prompt_package_id": prompt_package_id,
            "suite_id": None,
            "created_by": created_by,
            "max_concurrency": max_concurrency,
            "benchmark_id": DATASET_RUN_BENCHMARK_ID,
            "benchmark_version": DATASET_RUN_BENCHMARK_VERSION,
            "configuration_snapshot": snapshot,
            "status": "queued",
            "total_samples": len(samples),
            "completed_samples": 0,
            "successful_samples": 0,
            "failed_samples": 0,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "archived_at": None,
        },
    )
    dataset_task = store.insert_document(
        "task_units",
        {
            "run_id": run["id"],
            "parent_task_id": None,
            "task_type": "dataset_preparation",
            "payload": {"datasets": frozen_datasets, "prepared_inline": False},
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
    benchmark_task = store.insert_document(
        "task_units",
        {
            "run_id": run["id"],
            "parent_task_id": dataset_task["id"],
            "task_type": "benchmark",
            "payload": {"benchmark_id": DATASET_RUN_BENCHMARK_ID, "benchmark_version": DATASET_RUN_BENCHMARK_VERSION, "planned_samples": len(samples)},
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
    try:
        shards = _split_samples_for_endpoint_budget(tuple(samples), _dataset_run_manifest(), endpoint)
    except RunCreationError as error:
        raise MongoRunExecutionError(str(error)) from error
    for shard_index, shard_samples in enumerate(shards, start=1):
        task = store.insert_document(
            "task_units",
            {
                "run_id": run["id"],
                "parent_task_id": benchmark_task["id"],
                "task_type": "evaluation_shard",
                "payload": {
                    "sample_ids": [sample.sample_id for sample in shard_samples],
                    "estimated_request_count": len(shard_samples),
                    "estimated_token_count": sum(_estimate_sample_tokens(sample) for sample in shard_samples),
                    "sample_token_estimates": {sample.sample_id: _estimate_sample_tokens(sample) for sample in shard_samples},
                    "shard_index": shard_index,
                    "shard_count": len(shards),
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
        for sample in shard_samples:
            store.insert_document(
                "sample_attempts",
                {
                    "run_id": run["id"],
                    "task_id": task["id"],
                    "sample_id": sample.sample_id,
                    "attempt_number": 1,
                    "input_snapshot": {"messages": _build_sample_messages(sample, None), "modality": "text", "metadata": dict(sample.metadata), "request_body_evidence": request_body_evidence},
                    "reference_snapshot": {"type": str(scoring_rule.get("type", "exact_match")), "answer": sample.reference_answer, "scoring": scoring_rule},
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


def preflight_mongo_dataset_run(
    store: MongoDocumentStore,
    *,
    data_root: str,
    model_endpoint_id: str,
    dataset_version_id: str,
    prompt_package_id: str | None,
    reference_field: str,
    sample_limit: int,
    input_field: str | None = None,
    request_body_override: dict[str, object] | None = None,
) -> dict[str, object]:
    issues: list[str] = []
    endpoint = store.get_document("model_endpoints", model_endpoint_id)
    if endpoint is None:
        issues.append("Model endpoint not found.")
    elif endpoint.get("status") != "available":
        issues.append("Model endpoint must pass a connection test before scheduling a run.")
    dataset = store.get_document("dataset_versions", dataset_version_id)
    if dataset is None:
        issues.append("Dataset version not found.")
    elif dataset.get("status") != "ready" or not dataset.get("prepared_path"):
        issues.append(f"Dataset {dataset['dataset_id']} v{dataset['version']} is not ready; download and verify it first.")
    if prompt_package_id and store.get_document("prompt_packages", prompt_package_id) is None:
        issues.append("Prompt package not found.")
    if not reference_field.strip():
        issues.append("A reference field is required.")
    selected_input_field = input_field.strip() if input_field and input_field.strip() else None
    samples: list[BenchmarkSample] = []
    datasets: list[dict[str, object]] = []
    if dataset is not None and dataset.get("status") == "ready" and dataset.get("prepared_path"):
        datasets.append({"id": dataset["id"], "dataset_id": dataset["dataset_id"], "version": dataset["version"], "revision": dataset.get("revision", "default"), "status": dataset["status"], "will_prepare": False})
        try:
            samples, _skipped = _build_dataset_samples(
                prepared_path=dataset["prepared_path"],
                data_root=data_root,
                sample_limit=sample_limit,
                input_field=selected_input_field,
                reference_field=reference_field.strip(),
                prompt_package=_proxy(store.get_document("prompt_packages", prompt_package_id)) if prompt_package_id else None,
                dataset_id=dataset["dataset_id"],
                dataset_version=dataset["version"],
            )
            if not samples:
                issues.append(_empty_dataset_samples_message(
                    sample_limit=sample_limit,
                    input_field=selected_input_field,
                    reference_field=reference_field.strip(),
                ))
        except (DatasetRecordError, DatasetRunError) as error:
            issues.append(str(error))
    if endpoint is not None and endpoint.get("status") == "available":
        compatibility = _capability_compatibility(store, model_endpoint_id, _dataset_run_manifest())
        if compatibility["unsupported"]:
            issues.append("Model endpoint is incompatible with dataset evaluation: " + ", ".join(compatibility["unsupported"]))
    else:
        compatibility = {"required": ["text_input"], "unsupported": [], "unverified": []}
    estimated_input_tokens = sum(_estimate_sample_tokens(sample) for sample in samples)
    estimated_output_tokens = len(samples) * 64
    estimated_cost = (
        ((estimated_input_tokens * endpoint.get("input_cost_per_million")) + (estimated_output_tokens * endpoint.get("output_cost_per_million"))) / 1_000_000
        if endpoint is not None and endpoint.get("input_cost_per_million") is not None and endpoint.get("output_cost_per_million") is not None
        else None
    )
    return {
        "can_queue": not issues,
        "issues": issues,
        "sample_count": len(samples),
        "estimated_requests": len(samples),
        "estimated_input_tokens": estimated_input_tokens,
        "estimated_output_tokens": estimated_output_tokens,
        "estimated_cost": estimated_cost,
        "currency": endpoint.get("currency") if endpoint is not None else None,
        "compatibility": compatibility,
        "datasets": datasets,
        "request_body_evidence": (
            _mongo_request_body_evidence(endpoint=endpoint, benchmark_manifest=_dataset_run_manifest(), suite_snapshot=None, request_body_override=request_body_override)
            if endpoint is not None else None
        ),
    }


def _dataset_run_manifest() -> dict[str, object]:
    from app.services.dataset_runs import _DATASET_RUN_MANIFEST

    return dict(_DATASET_RUN_MANIFEST)


def _freeze_mongo_declared_datasets(
    store: MongoDocumentStore,
    descriptors: object,
) -> list[dict[str, object]]:
    if not isinstance(descriptors, list):
        return []
    frozen: list[dict[str, object]] = []
    for descriptor in descriptors:
        if not isinstance(descriptor, dict) or not isinstance(descriptor.get("dataset_id"), str):
            raise MongoRunExecutionError("Benchmark dataset descriptors require a dataset_id.")
        existing_id = descriptor.get("dataset_version_id")
        if isinstance(existing_id, str):
            dataset = store.get_document("dataset_versions", existing_id)
            if dataset is None:
                raise MongoRunExecutionError(f"Declared dataset revision {existing_id} is not registered.")
        else:
            query: dict[str, Any] = {"dataset_id": descriptor["dataset_id"]}
            if isinstance(descriptor.get("version"), str): query["version"] = descriptor["version"]
            if isinstance(descriptor.get("revision"), str): query["revision"] = descriptor["revision"]
            matches = store.list_documents("dataset_versions", query=query, sort=[("created_at", -1)])
            if not matches:
                dataset = _register_mongo_declared_dataset(store, descriptor)
            else:
                dataset = matches[0]
        frozen.append({**descriptor, "dataset_version_id": dataset["id"], "dataset_id": dataset["dataset_id"], "version": dataset["version"], "revision": dataset["revision"], "checksum": dataset.get("checksum")})
    return frozen


def _register_mongo_declared_dataset(
    store: MongoDocumentStore,
    descriptor: dict[str, object],
) -> dict[str, Any]:
    """Create a frozen manifest-owned revision for the document-store path."""

    source_url = descriptor.get("source_url")
    if not isinstance(source_url, str) or not source_url.strip():
        raise MongoRunExecutionError(f"Required dataset {descriptor['dataset_id']} is not registered.")
    version = descriptor.get("version")
    revision = descriptor.get("revision")
    license_text = descriptor.get("license_text")
    credential_binding_id = descriptor.get("credential_binding_id")
    checksum = descriptor.get("checksum")
    return store.insert_document(
        "dataset_versions",
        {
            "dataset_id": str(descriptor["dataset_id"]),
            "version": version.strip() if isinstance(version, str) and version.strip() else "default",
            "revision": revision.strip() if isinstance(revision, str) and revision.strip() else "default",
            "source_url": source_url.strip(),
            "checksum": checksum.strip() if isinstance(checksum, str) and checksum.strip() else None,
            "license_text": license_text.strip() if isinstance(license_text, str) and license_text.strip() else None,
            "credential_binding_id": credential_binding_id.strip() if isinstance(credential_binding_id, str) and credential_binding_id.strip() else None,
            "local_path": None,
            "prepared_path": None,
            "size_bytes": None,
            "license_accepted_at": None,
            "input_field": None,
            "reference_field": None,
            "status": "license_required" if isinstance(license_text, str) and license_text.strip() else "not_downloaded",
            "error_message": None,
            "created_at": _utc_now(),
        },
    )


def _mongo_effective_scoring_rule(manifest: dict[str, object], prompt_package: dict[str, Any] | None) -> dict[str, object]:
    prompt_rule = prompt_package.get("scoring_rule") if prompt_package else None
    if isinstance(prompt_rule, dict) and prompt_rule:
        return dict(prompt_rule)
    benchmark_rule = manifest.get("scoring")
    return dict(benchmark_rule) if isinstance(benchmark_rule, dict) and benchmark_rule else {"type": "exact_match"}


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
    run = store.insert_document("evaluation_runs", {"model_endpoint_id":model_endpoint_id,"prompt_package_id":None,"suite_id":None,"created_by":created_by,"max_concurrency":max_concurrency,"benchmark_id":"custom-multimodal","benchmark_version":"1.0.0","configuration_snapshot":{"benchmark":{"id":"custom-multimodal","version":"1.0.0","source":"user"},"endpoint":{"id":endpoint["id"],"base_url":endpoint["base_url"],"model_name":endpoint["model_name"],"protocol_profile":endpoint.get("protocol_profile","openai_chat_completions"),"default_request_body":endpoint.get("default_request_body", {}),"timeout_seconds":endpoint.get("timeout_seconds", 60),"custom_headers":endpoint.get("custom_headers", {}),"input_cost_per_million":endpoint.get("input_cost_per_million"),"output_cost_per_million":endpoint.get("output_cost_per_million")},"sample_ids":[sample_id],"request_body_evidence":request_body_evidence},"status":"queued","total_samples":1,"completed_samples":0,"successful_samples":0,"failed_samples":0,"created_at":now,"started_at":None,"completed_at":None})
    dataset_task = store.insert_document("task_units", {"run_id":run["id"],"parent_task_id":None,"task_type":"dataset_preparation","payload":{"source":"user","prepared_inline":True},"status":"succeeded","priority":0,"attempt_count":0,"leased_by":None,"lease_token":None,"lease_expires_at":None,"next_retry_at":None,"heartbeat_at":None,"created_at":now,"updated_at":now})
    benchmark_task = store.insert_document("task_units", {"run_id":run["id"],"parent_task_id":dataset_task["id"],"task_type":"benchmark","payload":{"benchmark_id":"custom-multimodal","benchmark_version":"1.0.0","planned_samples":1},"status":"succeeded","priority":0,"attempt_count":0,"leased_by":None,"lease_token":None,"lease_expires_at":None,"next_retry_at":None,"heartbeat_at":None,"created_at":now,"updated_at":now})
    task = store.insert_document("task_units", {"run_id":run["id"],"parent_task_id":benchmark_task["id"],"task_type":"evaluation_shard","payload":{"sample_ids":[sample_id],"estimated_request_count":1,"estimated_token_count":_estimate_message_tokens(normalized),"retry_policy":{"max_attempts":3,"base_delay_seconds":2,"max_delay_seconds":60}},"status":"pending","priority":0,"attempt_count":0,"leased_by":None,"lease_token":None,"lease_expires_at":None,"next_retry_at":None,"heartbeat_at":None,"created_at":now,"updated_at":now})
    store.insert_document("sample_attempts", {"run_id":run["id"],"task_id":task["id"],"sample_id":sample_id.strip(),"attempt_number":1,"input_snapshot":{"messages":normalized,"modality":_sample_modality(normalized),"metadata":{"capability":"custom","language":"unknown","difficulty":"custom"},"request_body_evidence":request_body_evidence},"reference_snapshot":{"type":"exact_match","answer":reference_answer},"request_snapshot":None,"raw_response":None,"parsed_prediction":None,"score":None,"latency_ms":None,"input_tokens":None,"output_tokens":None,"estimated_cost":None,"error_type":None,"error_message":None,"status":"pending","created_at":now,"started_at":None,"completed_at":None})
    return run


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
            if current is not None and current.get("status") in {"queued", "running", "completed", "completed_with_errors"}:
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


def clone_mongo_run(store: MongoDocumentStore, run_id: str) -> dict[str, Any]:
    source = store.get_document("evaluation_runs", run_id)
    if source is None:
        raise MongoRunExecutionError("Evaluation run not found.")
    snapshot = source.get("configuration_snapshot") if isinstance(source.get("configuration_snapshot"), dict) else {}
    snapshot_datasets = snapshot.get("datasets") if isinstance(snapshot, dict) else None
    return create_mongo_benchmark_run(
        store,
        model_endpoint_id=str(source["model_endpoint_id"]),
        sample_limit=int(source["total_samples"]),
        prompt_package_id=source.get("prompt_package_id"),
        benchmark_id=str(source["benchmark_id"]),
        benchmark_version=str(source["benchmark_version"]),
        declared_datasets=snapshot_datasets if isinstance(snapshot_datasets, list) else None,
        suite_id=source.get("suite_id"),
        created_by=source.get("created_by"),
        max_concurrency=source.get("max_concurrency"),
    )


def rerun_mongo_benchmark(store: MongoDocumentStore, run_id: str) -> dict[str, Any]:
    """Queue an immutable fresh benchmark pass from an existing Mongo run."""

    source = store.get_document("evaluation_runs", run_id)
    if source is None:
        raise MongoRunExecutionError("Evaluation run not found.")
    run = clone_mongo_run(store, run_id)
    snapshot = run.get("configuration_snapshot") if isinstance(run.get("configuration_snapshot"), dict) else {}
    updated = store.update_document(
        "evaluation_runs",
        str(run["id"]),
        {"configuration_snapshot": {**snapshot, "rerun_of": {"run_id": source["id"], "kind": "benchmark"}}},
    )
    assert updated is not None
    return updated


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
    retry_policy = source_payload.get("retry_policy") if isinstance(source_payload.get("retry_policy"), dict) else {"max_attempts": 3, "base_delay_seconds": 2, "max_delay_seconds": 60}
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
        token_estimates = {str(attempt["sample_id"]): _estimate_mongo_retry_attempt_tokens(attempt) for attempt in group}
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
        stored = _record_result(store, attempt, result, frozen_endpoint, lease_token)
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
            run = store.update_document_if("evaluation_runs", str(run["id"]), {"status": {"$in": ["queued", "running"]}}, {"status": "queued"})
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
        for candidate in store.list_documents("task_units", query={"run_id": run["id"], "task_type": "evaluation_shard"})
        if candidate["id"] != task_id and candidate.get("status") in {"pending", "leased", "running", "retry_scheduled"}
    ]
    if incomplete_shards:
        run = store.update_document_if("evaluation_runs", str(run["id"]), {"status": {"$in": ["queued", "running"]}}, {"status": "running", "completed_at": None})
        if run is None:
            raise MongoRunExecutionError("Evaluation run is no longer executable.")
        return run, task
    run = store.update_document_if("evaluation_runs", str(run["id"]), {"status": {"$in": ["queued", "running"]}}, {"status": "scoring", "completed_at": None})
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
                if not isinstance(descriptor, dict) or not isinstance(descriptor.get("dataset_id"), str): continue
                frozen_id = descriptor.get("dataset_version_id")
                if isinstance(frozen_id, str):
                    dataset = store.get_document("dataset_versions", frozen_id)
                else:
                    query = {"dataset_id": descriptor["dataset_id"]}
                    if isinstance(descriptor.get("version"), str): query["version"] = descriptor["version"]
                    if isinstance(descriptor.get("revision"), str): query["revision"] = descriptor["revision"]
                    matches = store.list_documents("dataset_versions", query=query, sort=[("created_at", -1)])
                    dataset = matches[0] if matches else None
                if dataset is None: raise MongoRunExecutionError(f"Required dataset {descriptor['dataset_id']} is not registered.")
                if dataset.get("status") != "ready": download_mongo_dataset(store, str(dataset["id"]), data_root, settings)
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
        {"status": "succeeded", "payload": {**payload, "worker_interface": task["task_type"], "stage_completed_at": now.isoformat()}, **_lease_values()},
    )
    if updated_task is None:
        raise MongoRunExecutionError("Task lease was lost before finalization.")
    if task["task_type"] == "dataset_preparation" and run.get("status") == "waiting_for_dataset":
        run = store.update_document_if("evaluation_runs", str(run["id"]), {"status": "waiting_for_dataset"}, {"status": "queued"})
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
    task = store.update_task_if_current_lease(task, lease_token, {"status": "running", "attempt_count": int(task.get("attempt_count", 0)) + 1})
    if task is None:
        raise MongoRunExecutionError("Task lease was lost before execution started.")
    run = store.update_document_if("evaluation_runs", str(run["id"]), {"status": {"$in": ["scoring", "running"]}}, {"status": "scoring"})
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
    task = store.update_task_if_current_lease(task, lease_token, {"status": "running", "attempt_count": int(task.get("attempt_count", 0)) + 1})
    if task is None:
        raise MongoRunExecutionError("Task lease was lost before execution started.")
    run = store.update_document_if("evaluation_runs", str(run["id"]), {"status": {"$in": ["aggregating", "scoring"]}}, {"status": "aggregating"})
    if run is None:
        raise MongoRunExecutionError("Evaluation run is no longer executable.")
    metrics = recompute_mongo_aggregate_metrics(store, str(run["id"]))
    task = store.update_task_if_current_lease(
        task,
        lease_token,
        {"payload": {**_task_payload(task), "metric_count": len(metrics), "aggregation_version": "1.0.0"}, "status": "succeeded", **_lease_values()},
    )
    if task is None:
        raise MongoRunExecutionError("Task lease was lost before finalization.")
    run = store.update_document_if("evaluation_runs", str(run["id"]), {"status": "aggregating"}, {"status": "generating_report", "completed_at": None})
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
    task = store.update_task_if_current_lease(task, lease_token, {"status": "running", "attempt_count": int(task.get("attempt_count", 0)) + 1})
    if task is None:
        raise MongoRunExecutionError("Task lease was lost before execution started.")
    payload = _task_payload(task)
    try:
        from app.services.mongo_reports import generate_mongo_report

        report = generate_mongo_report(
            store,
            str(run["id"]),
            str(payload.get("format", "html")),
            data_root,
            report_type=str(payload.get("report_type", "single_model")),
        )
    except ReportError as error:
        task = store.update_task_if_current_lease(task, lease_token, {"status": "failed", "payload": {**payload, "report_error": str(error)}, **_lease_values()})
        if task is None:
            raise MongoRunExecutionError("Task lease was lost before finalization.") from error
        run = store.update_document_if("evaluation_runs", str(run["id"]), {"status": "generating_report"}, {"status": str(payload.get("terminal_status", "completed_with_errors" if int(run.get("failed_samples", 0)) else "completed")), "completed_at": _utc_now()})
        if run is None:
            raise MongoRunExecutionError("Evaluation run is no longer executable.") from error
        raise MongoRunExecutionError(str(error)) from error
    task = store.update_task_if_current_lease(task, lease_token, {"status": "succeeded", "payload": {**payload, "report_id": report["id"], "artifact_path": report["artifact_path"]}, **_lease_values()})
    if task is None:
        raise MongoRunExecutionError("Task lease was lost before finalization.")
    final_status = "completed_with_errors" if int(run.get("failed_samples", 0)) else "completed"
    run = store.update_document_if("evaluation_runs", str(run["id"]), {"status": "generating_report"}, {"status": final_status, "completed_at": _utc_now()})
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
            "payload": {"pipeline_stage": task_type, **({"format": "html", "report_type": "single_model", "terminal_status": "completed_with_errors" if int(run.get("failed_samples", 0)) else "completed"} if task_type == "report_generation" else {})},
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
    return add_summary_insights(summarize_attempts(
        attempts,
        total_samples=int(run["total_samples"]),
        currency=str(endpoint["currency"]) if endpoint else None,
    ), attempts)


def _prepare_attempts(store: MongoDocumentStore, task: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _task_payload(task)
    sample_ids = [value for value in payload.get("retry_sample_ids") or payload.get("sample_ids") or [] if isinstance(value, str)]
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
    attempt: dict[str, Any],
    result: SampleExecutionResult,
    endpoint: dict[str, Any],
    lease_token: str,
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
        try:
            values.update({"score": score_prediction(result.prediction, attempt["reference_snapshot"]), "status": "succeeded", "error_type": None, "error_message": None})
        except ScoringError as error:
            values.update({"score": None, "status": "failed", "error_type": "scoring_error", "error_message": str(error)})
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
    return {"type":part["type"],"source":{"asset_id":asset_id,"base64_data":encoded},"mime_type":str(asset["mime_type"])}


def _sample_modality(messages: list[dict[str, object]]) -> str:
    kinds = {part["type"] for message in messages if isinstance(message.get("content"),list) for part in message["content"] if isinstance(part,dict) and part.get("type") != "text"}
    return "+".join(sorted(kinds | {"text"}))


def _estimate_message_tokens(messages: list[dict[str, object]]) -> int:
    text_length = sum(len(content) for message in messages if isinstance((content := message.get("content")),str))
    return max(32, (text_length + 3) // 4 + 32)


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
