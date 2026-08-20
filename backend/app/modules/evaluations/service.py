from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.benchmarks import get_installed_plugin
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db import (
    EndpointStatus,
    ModelEndpoint,
    PromptPackage,
    RunStatus,
    SampleAttemptStatus,
    TaskStatus,
    TaskType,
)
from app.db.models import ModelCapability
from app.infrastructure.providers.common import resolve_request_body
from app.modules.benchmarks.prompts import PromptTemplateError, render_template, standardization_flags
from app.modules.benchmarks.scoring import ScoringError, validate_scoring_rule
from app.modules.evaluations.names import format_run_display_name
from app.modules.evaluations.analysis import add_summary_insights, summarize_attempts
from app.modules.evaluations.evidence import (
    decorate_attempts,
    filter_attempts,
    run_logs,
    run_progress,
)
from app.modules.evaluations.lifecycle import RunLifecycle
from app.modules.evaluations.ports import EvaluationRepository
from app.modules.reports.service import delete_report_artifact


_ACTIVE_TASK_STATUSES = (
    TaskStatus.PENDING.value,
    TaskStatus.RETRY_SCHEDULED.value,
    TaskStatus.LEASED.value,
    TaskStatus.RUNNING.value,
)
_ACTIVE_ATTEMPT_STATUSES = (
    SampleAttemptStatus.PENDING.value,
    SampleAttemptStatus.LEASED.value,
    SampleAttemptStatus.RUNNING.value,
    SampleAttemptStatus.RETRY_SCHEDULED.value,
)


class EvaluationService:
    """Store-neutral evaluation lifecycle, querying, and evidence behavior."""

    def __init__(self, repository: EvaluationRepository, *, data_root: str) -> None:
        self._repository = repository
        self._data_root = data_root

    def get(self, run_id: str) -> dict[str, Any]:
        run = self._repository.get_run(run_id)
        if run is None:
            raise NotFoundError("Evaluation run not found", context={"run_id": run_id})
        return run

    def list(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        return self._repository.list_runs(include_archived=include_archived)

    def preflight_benchmark(
        self,
        *,
        model_endpoint_id: str,
        sample_limit: int | None,
        prompt_package_id: str | None,
        benchmark_id: str,
        benchmark_version: str,
        request_body_override: dict[str, object] | None = None,
    ) -> dict[str, object]:
        endpoint = self._repository.get_endpoint(model_endpoint_id)
        issues: list[str] = []
        if endpoint is None:
            return _empty_preflight("Model endpoint not found.")
        if endpoint.get("status") != EndpointStatus.AVAILABLE.value:
            issues.append("Model endpoint must pass a connection test before scheduling a run.")
        definition = self._repository.get_benchmark_definition(benchmark_id, benchmark_version)
        if definition is not None and definition.get("status") in {"disabled", "deprecated", "broken"}:
            issues.append(
                f"Benchmark {benchmark_id}@{benchmark_version} is {definition['status']} and cannot be scheduled."
            )
        plugin = get_installed_plugin(benchmark_id, benchmark_version)
        if plugin is None:
            return {
                **_empty_preflight("Benchmark plugin is not installed for the requested version."),
                "issues": [*issues, "Benchmark plugin is not installed for the requested version."],
                "currency": endpoint.get("currency"),
            }
        samples = plugin.samples(sample_limit)
        endpoint_proxy = _record_proxy(endpoint)
        if not samples:
            issues.append("At least one benchmark sample is required.")
        else:
            try:
                _split_samples_for_endpoint_budget(samples, plugin.manifest, endpoint_proxy)
            except RunCreationError as error:
                issues.append(str(error))
        compatibility = _capability_compatibility_records(
            self._repository.list_capabilities(model_endpoint_id), plugin.manifest
        )
        if compatibility["unsupported"]:
            issues.append(
                "Model endpoint is incompatible with required benchmark capabilities: "
                + ", ".join(compatibility["unsupported"])
            )
        prompt_package = self._repository.get_prompt_package(prompt_package_id) if prompt_package_id else None
        if prompt_package_id and prompt_package is None:
            issues.append("Prompt package not found.")
        prompt_proxy = _record_proxy(prompt_package) if prompt_package else None
        try:
            validate_scoring_rule(_effective_scoring_rule(plugin.manifest, prompt_proxy))
        except ScoringError as error:
            issues.append(f"Scoring rule is invalid: {error}")
        datasets = self._preflight_declared_datasets(plugin.manifest.get("datasets"), issues)
        estimated_input_tokens = sum(_estimate_sample_tokens(sample) for sample in samples)
        estimated_output_tokens = len(samples) * 64
        input_cost = endpoint.get("input_cost_per_million")
        output_cost = endpoint.get("output_cost_per_million")
        estimated_cost = (
            ((estimated_input_tokens * float(input_cost)) + (estimated_output_tokens * float(output_cost))) / 1_000_000
            if input_cost is not None and output_cost is not None
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
            "currency": endpoint.get("currency"),
            "compatibility": compatibility,
            "datasets": datasets,
            "request_body_evidence": _request_body_evidence(
                endpoint=endpoint_proxy,
                benchmark_manifest=plugin.manifest,
                suite_snapshot=None,
                request_body_override=request_body_override,
            ),
        }

    def create_benchmark(
        self,
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
        endpoint = self._repository.get_endpoint(model_endpoint_id)
        if endpoint is None:
            raise NotFoundError("Model endpoint not found.")
        if endpoint.get("status") != EndpointStatus.AVAILABLE.value:
            raise ConflictError("Model endpoint must pass a connection test before scheduling a run.")
        definition = self._repository.get_benchmark_definition(benchmark_id, benchmark_version)
        if definition is not None and definition.get("status") in {"disabled", "deprecated", "broken"}:
            raise ConflictError(
                f"Benchmark {benchmark_id}@{benchmark_version} is {definition['status']} and cannot be scheduled."
            )
        plugin = get_installed_plugin(benchmark_id, benchmark_version)
        if plugin is None:
            raise ConflictError("Benchmark plugin is not installed for the requested version.")
        samples = plugin.samples(sample_limit)
        if not samples:
            raise ConflictError("At least one benchmark sample is required.")
        compatibility = _capability_compatibility_records(
            self._repository.list_capabilities(model_endpoint_id), plugin.manifest
        )
        if compatibility["unsupported"]:
            raise ConflictError(
                "Model endpoint is incompatible with required benchmark capabilities: "
                + ", ".join(compatibility["unsupported"])
            )
        prompt_package = self._repository.get_prompt_package(prompt_package_id) if prompt_package_id else None
        if prompt_package_id and prompt_package is None:
            raise NotFoundError("Prompt package not found.")
        prompt_proxy = _record_proxy(prompt_package) if prompt_package else None
        frozen_datasets = self._freeze_declared_datasets(
            declared_datasets if declared_datasets is not None else plugin.manifest.get("datasets")
        )
        endpoint_proxy = _record_proxy(endpoint)
        request_body_evidence = _request_body_evidence(
            endpoint=endpoint_proxy,
            benchmark_manifest=plugin.manifest,
            suite_snapshot=suite_snapshot,
            request_body_override=request_body_override,
        )
        scoring_rule = _effective_scoring_rule(plugin.manifest, prompt_proxy)
        try:
            validate_scoring_rule(scoring_rule)
            shards = _split_samples_for_endpoint_budget(samples, plugin.manifest, endpoint_proxy)
        except (ScoringError, RunCreationError) as error:
            raise ConflictError(str(error)) from error

        now = datetime.now(timezone.utc)
        snapshot = {
            "benchmark": {"id": benchmark_id, "version": benchmark_version, "manifest": plugin.manifest},
            "endpoint": _endpoint_snapshot(endpoint),
            "sample_ids": [sample.sample_id for sample in samples],
            "datasets": frozen_datasets,
            "capability_compatibility": compatibility,
            "prompt_package": _prompt_snapshot(prompt_package),
            "prompt_standardization": (
                {
                    "is_standard": not standardization_flags(prompt_proxy),
                    "flags": standardization_flags(prompt_proxy),
                }
                if prompt_proxy
                else {"is_standard": True, "flags": []}
            ),
            "evaluation_suite": suite_snapshot,
            "request_body_evidence": request_body_evidence,
        }
        run_values = {
            "model_endpoint_id": model_endpoint_id,
            "prompt_package_id": prompt_package_id,
            "suite_id": suite_id,
            "created_by": created_by,
            "max_concurrency": max_concurrency,
            "benchmark_id": benchmark_id,
            "benchmark_version": benchmark_version,
            "display_name": format_run_display_name(str(endpoint["model_name"]), benchmark_id, now),
            "configuration_snapshot": snapshot,
            "status": RunStatus.WAITING_FOR_DATASET.value if frozen_datasets else RunStatus.QUEUED.value,
            "total_samples": len(samples),
            "completed_samples": 0,
            "successful_samples": 0,
            "failed_samples": 0,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "archived_at": None,
        }
        tasks = [
            _task_values(
                "dataset",
                task_type=TaskType.DATASET_PREPARATION.value,
                payload={"datasets": frozen_datasets, "prepared_inline": not bool(frozen_datasets)},
                task_status=TaskStatus.PENDING.value if frozen_datasets else TaskStatus.SUCCEEDED.value,
                now=now,
            ),
            _task_values(
                "benchmark",
                parent_key="dataset",
                task_type=TaskType.BENCHMARK.value,
                payload={
                    "benchmark_id": benchmark_id,
                    "benchmark_version": benchmark_version,
                    "planned_samples": len(samples),
                },
                task_status=TaskStatus.PENDING.value if frozen_datasets else TaskStatus.SUCCEEDED.value,
                now=now,
            ),
        ]
        attempts: list[dict[str, Any]] = []
        for shard_index, shard_samples in enumerate(shards, start=1):
            task_key = f"shard-{shard_index}"
            tasks.append(
                _task_values(
                    task_key,
                    parent_key="benchmark",
                    task_type=TaskType.EVALUATION_SHARD.value,
                    payload={
                        "sample_ids": [sample.sample_id for sample in shard_samples],
                        "estimated_request_count": len(shard_samples),
                        "estimated_token_count": sum(_estimate_sample_tokens(sample) for sample in shard_samples),
                        "sample_token_estimates": {
                            sample.sample_id: _estimate_sample_tokens(sample) for sample in shard_samples
                        },
                        "shard_index": shard_index,
                        "shard_count": len(shards),
                        "retry_policy": {
                            "max_attempts": 3,
                            "base_delay_seconds": 2,
                            "max_delay_seconds": 60,
                        },
                    },
                    task_status=TaskStatus.PENDING.value,
                    now=now,
                )
            )
            attempts.extend(
                _attempt_values(
                    task_key,
                    sample_id=sample.sample_id,
                    input_snapshot={
                        "messages": _build_sample_messages(sample, prompt_proxy),
                        "modality": _sample_modality(sample),
                        "metadata": dict(sample.metadata),
                        "request_body_evidence": request_body_evidence,
                    },
                    reference_snapshot={
                        "type": str(scoring_rule.get("type", "exact_match")),
                        "answer": sample.reference_answer,
                        "scoring": scoring_rule,
                    },
                    now=now,
                )
                for sample in shard_samples
            )
        return self._repository.create_run_graph(run_values, tasks, attempts)

    def clone(self, run_id: str) -> dict[str, Any]:
        source = self.get(run_id)
        snapshot = source.get("configuration_snapshot")
        snapshot = snapshot if isinstance(snapshot, dict) else {}
        datasets = snapshot.get("datasets")
        return self.create_benchmark(
            model_endpoint_id=str(source["model_endpoint_id"]),
            sample_limit=int(source["total_samples"]),
            prompt_package_id=(str(source["prompt_package_id"]) if source.get("prompt_package_id") else None),
            benchmark_id=str(source["benchmark_id"]),
            benchmark_version=str(source["benchmark_version"]),
            declared_datasets=datasets if isinstance(datasets, list) else None,
            created_by=str(source["created_by"]) if source.get("created_by") else None,
            max_concurrency=(int(source["max_concurrency"]) if source.get("max_concurrency") is not None else None),
        )

    def rerun_benchmark(self, run_id: str) -> dict[str, Any]:
        run = self.clone(run_id)
        snapshot = run.get("configuration_snapshot")
        snapshot = dict(snapshot) if isinstance(snapshot, dict) else {}
        snapshot["rerun_of"] = {"run_id": run_id, "kind": "benchmark"}
        return self._updated_run(str(run["id"]), {"configuration_snapshot": snapshot})

    def _preflight_declared_datasets(self, descriptors: object, issues: list[str]) -> list[dict[str, object]]:
        if not isinstance(descriptors, list):
            return []
        datasets: list[dict[str, object]] = []
        for descriptor in descriptors:
            if not isinstance(descriptor, dict) or not isinstance(descriptor.get("dataset_id"), str):
                continue
            dataset = self._repository.find_dataset(
                dataset_id=descriptor["dataset_id"],
                version=descriptor.get("version") if isinstance(descriptor.get("version"), str) else None,
                revision=(descriptor.get("revision") if isinstance(descriptor.get("revision"), str) else None),
            )
            if dataset is None:
                source_url = descriptor.get("source_url")
                if isinstance(source_url, str) and source_url.strip():
                    datasets.append(
                        {
                            "dataset_id": descriptor["dataset_id"],
                            "version": descriptor.get("version", "default"),
                            "revision": descriptor.get("revision", "default"),
                            "status": "will_register",
                            "will_prepare": True,
                        }
                    )
                else:
                    issues.append(f"Required dataset {descriptor['dataset_id']} is not registered.")
                    datasets.append(
                        {
                            "dataset_id": descriptor["dataset_id"],
                            "status": "missing",
                            "will_prepare": False,
                        }
                    )
            else:
                datasets.append(
                    {
                        "id": dataset["id"],
                        "dataset_id": dataset["dataset_id"],
                        "version": dataset["version"],
                        "revision": dataset["revision"],
                        "status": dataset["status"],
                        "will_prepare": dataset["status"] != "ready",
                    }
                )
        return datasets

    def _freeze_declared_datasets(self, descriptors: object) -> list[dict[str, object]]:
        if not isinstance(descriptors, list):
            return []
        frozen: list[dict[str, object]] = []
        for descriptor in descriptors:
            if not isinstance(descriptor, dict) or not isinstance(descriptor.get("dataset_id"), str):
                raise ConflictError("Benchmark dataset descriptors require a dataset_id.")
            existing_id = descriptor.get("dataset_version_id")
            if isinstance(existing_id, str):
                dataset = self._repository.get_dataset(existing_id)
                if dataset is None:
                    raise NotFoundError(f"Declared dataset revision {existing_id} is not registered.")
            else:
                dataset = self._repository.find_dataset(
                    dataset_id=descriptor["dataset_id"],
                    version=(descriptor.get("version") if isinstance(descriptor.get("version"), str) else None),
                    revision=(descriptor.get("revision") if isinstance(descriptor.get("revision"), str) else None),
                )
                if dataset is None:
                    dataset = self._register_declared_dataset(descriptor)
            frozen.append(
                {
                    **descriptor,
                    "dataset_version_id": dataset["id"],
                    "dataset_id": dataset["dataset_id"],
                    "version": dataset["version"],
                    "revision": dataset["revision"],
                    "checksum": dataset.get("checksum"),
                }
            )
        return frozen

    def _register_declared_dataset(self, descriptor: dict[str, object]) -> dict[str, Any]:
        source_url = descriptor.get("source_url")
        if not isinstance(source_url, str) or not source_url.strip():
            raise NotFoundError(f"Required dataset {descriptor['dataset_id']} is not registered.")
        version = descriptor.get("version")
        revision = descriptor.get("revision")
        license_text = descriptor.get("license_text")
        credential_binding_id = descriptor.get("credential_binding_id")
        checksum = descriptor.get("checksum")
        return self._repository.create_dataset(
            {
                "dataset_id": str(descriptor["dataset_id"]),
                "version": version.strip() if isinstance(version, str) and version.strip() else "default",
                "revision": (revision.strip() if isinstance(revision, str) and revision.strip() else "default"),
                "source_url": source_url.strip(),
                "credential_env_var": None,
                "credential_binding_id": (
                    credential_binding_id.strip()
                    if isinstance(credential_binding_id, str) and credential_binding_id.strip()
                    else None
                ),
                "checksum": checksum.strip() if isinstance(checksum, str) and checksum.strip() else None,
                "size_bytes": None,
                "local_path": None,
                "prepared_path": None,
                "license_text": (
                    license_text.strip() if isinstance(license_text, str) and license_text.strip() else None
                ),
                "license_accepted_at": None,
                "input_field": None,
                "reference_field": None,
                "capabilities": [],
                "languages": [],
                "evaluation_type": "custom",
                "status": (
                    "license_required" if isinstance(license_text, str) and license_text.strip() else "not_downloaded"
                ),
                "error_message": None,
                "created_at": datetime.now(timezone.utc),
            }
        )

    def pause(self, run_id: str) -> dict[str, Any]:
        run = self.get(run_id)
        if not RunLifecycle.can_pause(str(run["status"])):
            raise ConflictError("Run cannot be paused in its current state")
        self._repository.update_tasks(
            run_id,
            statuses=_ACTIVE_TASK_STATUSES,
            values={
                "status": TaskStatus.CANCELLED.value,
                "leased_by": None,
                "lease_token": None,
                "lease_expires_at": None,
                "heartbeat_at": None,
            },
            increment_lease_version=True,
        )
        self._repository.update_attempts(
            run_id,
            statuses=_ACTIVE_ATTEMPT_STATUSES,
            values={"status": SampleAttemptStatus.PENDING.value, "completed_at": None},
        )
        return self._updated_run(run_id, {"status": RunStatus.PAUSED.value})

    def resume(self, run_id: str) -> dict[str, Any]:
        run = self.get(run_id)
        if not RunLifecycle.can_resume(str(run["status"])):
            raise ConflictError("Only paused runs can be resumed")
        self._repository.update_tasks(
            run_id,
            statuses=(TaskStatus.CANCELLED.value,),
            values={"status": TaskStatus.PENDING.value},
        )
        return self._updated_run(run_id, {"status": RunStatus.QUEUED.value})

    def cancel(self, run_id: str) -> dict[str, Any]:
        run = self.get(run_id)
        if not RunLifecycle.can_cancel(str(run["status"])):
            raise ConflictError("Run cannot be cancelled in its current state")
        self._repository.update_tasks(
            run_id,
            statuses=_ACTIVE_TASK_STATUSES,
            values={
                "status": TaskStatus.CANCELLED.value,
                "leased_by": None,
                "lease_token": None,
                "lease_expires_at": None,
                "heartbeat_at": None,
            },
            increment_lease_version=True,
        )
        self._repository.update_attempts(
            run_id,
            statuses=_ACTIVE_ATTEMPT_STATUSES,
            values={"status": SampleAttemptStatus.CANCELLED.value},
        )
        return self._updated_run(run_id, {"status": RunStatus.CANCELLED.value})

    def archive(self, run_id: str) -> dict[str, Any]:
        run = self.get(run_id)
        if not RunLifecycle.can_archive(str(run["status"])):
            raise ConflictError("Only terminal evaluation runs can be archived")
        return self._updated_run(
            run_id,
            {"archived_at": run.get("archived_at") or datetime.now(timezone.utc)},
        )

    def delete(self, run_id: str) -> None:
        run = self.get(run_id)
        if not RunLifecycle.can_delete(run.get("archived_at")):
            raise ConflictError("Archive the evaluation run before deleting it")
        for artifact_path in self._repository.delete_run(run_id):
            delete_report_artifact(self._data_root, artifact_path)

    def update_scheduling(self, run_id: str, values: dict[str, Any]) -> dict[str, Any]:
        if not values:
            raise ValidationError("Specify a scheduling value to update")
        run = self.get(run_id)
        if not RunLifecycle.can_change_scheduling(str(run["status"])):
            raise ConflictError("Terminal evaluation runs cannot change scheduling controls")
        return self._updated_run(run_id, values)

    def list_attempts(
        self,
        run_id: str,
        *,
        offset: int = 0,
        limit: int = 200,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        self.get(run_id)
        attempts = self._repository.list_attempts(run_id)
        attempt_ids = [str(attempt["id"]) for attempt in attempts]
        decorated = decorate_attempts(
            attempts,
            self._repository.list_reviews(attempt_ids),
            self._repository.list_judge_assessments(attempt_ids),
        )
        return filter_attempts(decorated, **filters)[offset : offset + limit]

    def progress(self, run_id: str) -> dict[str, Any]:
        return run_progress(self.get(run_id))

    def logs(self, run_id: str, *, offset: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        self.get(run_id)
        return run_logs(self._repository.list_tasks(run_id), self._repository.list_attempts(run_id))[
            offset : offset + limit
        ]

    def summary(self, run_id: str) -> dict[str, Any]:
        run = self.get(run_id)
        endpoint = self._repository.get_endpoint(str(run["model_endpoint_id"]))
        current_attempts = _latest_attempt_values(self._repository.list_attempts(run_id))
        summary = summarize_attempts(
            current_attempts,
            total_samples=int(run["total_samples"]),
            currency=str(endpoint["currency"]) if endpoint and endpoint.get("currency") else None,
        )
        previous = self._repository.find_previous_completed_run(run)
        previous_summary = None
        if previous is not None:
            previous_summary = summarize_attempts(
                _latest_attempt_values(self._repository.list_attempts(str(previous["id"]))),
                total_samples=int(previous["total_samples"]),
                currency=(str(endpoint["currency"]) if endpoint and endpoint.get("currency") else None),
            )
        return add_summary_insights(summary, current_attempts, previous_summary)

    def event_payload(self, run_id: str) -> dict[str, Any]:
        progress = self.progress(run_id)
        return {**progress, "summary": self.summary(run_id)}

    def _updated_run(self, run_id: str, values: dict[str, Any]) -> dict[str, Any]:
        run = self._repository.update_run(run_id, values)
        if run is None:
            raise NotFoundError("Evaluation run not found", context={"run_id": run_id})
        return run


def _latest_attempt_values(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for attempt in sorted(
        attempts,
        key=lambda item: (str(item["sample_id"]), -int(item.get("attempt_number") or 1)),
    ):
        latest.setdefault(str(attempt["sample_id"]), attempt)
    return [latest[sample_id] for sample_id in sorted(latest)]


def _empty_preflight(issue: str) -> dict[str, object]:
    return {
        "can_queue": False,
        "issues": [issue],
        "sample_count": 0,
        "estimated_requests": 0,
        "estimated_input_tokens": 0,
        "estimated_output_tokens": 0,
        "estimated_cost": None,
        "currency": None,
        "compatibility": {"required": [], "unsupported": [], "unverified": []},
        "datasets": [],
        "request_body_evidence": None,
    }


def _record_proxy(record: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(**record)


def _endpoint_snapshot(endpoint: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": endpoint["id"],
        "base_url": endpoint["base_url"],
        "model_name": endpoint["model_name"],
        "protocol_profile": endpoint.get("protocol_profile", "openai_chat_completions"),
        "default_request_body": endpoint.get("default_request_body", {}),
        "timeout_seconds": endpoint.get("timeout_seconds", 60),
        "custom_headers": endpoint.get("custom_headers", {}),
        "input_cost_per_million": endpoint.get("input_cost_per_million"),
        "output_cost_per_million": endpoint.get("output_cost_per_million"),
    }


def _prompt_snapshot(prompt: dict[str, Any] | None) -> dict[str, Any] | None:
    if prompt is None:
        return None
    return {
        "id": prompt["id"],
        "name": prompt["name"],
        "version": prompt["version"],
        "system_message": prompt.get("system_message"),
        "user_template": prompt["user_template"],
        "few_shot_examples": prompt.get("few_shot_examples", []),
        "scoring_rule": prompt.get("scoring_rule"),
    }


def _task_values(
    key: str,
    *,
    task_type: str,
    payload: dict[str, Any],
    task_status: str,
    now: datetime,
    parent_key: str | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "parent_key": parent_key,
        "task_type": task_type,
        "payload": payload,
        "status": task_status,
        "priority": 0,
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


def _attempt_values(
    task_key: str,
    *,
    sample_id: str,
    input_snapshot: dict[str, Any],
    reference_snapshot: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    return {
        "task_key": task_key,
        "sample_id": sample_id,
        "attempt_number": 1,
        "input_snapshot": input_snapshot,
        "reference_snapshot": reference_snapshot,
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
        "created_at": now,
        "started_at": None,
        "completed_at": None,
    }


def _capability_compatibility_records(
    capabilities: list[dict[str, Any]], manifest: dict[str, object]
) -> dict[str, list[str]]:
    required = [capability for capability in manifest.get("required_capabilities", []) if isinstance(capability, str)]
    records = {str(record["capability_key"]): record for record in capabilities}
    unsupported = [
        capability
        for capability in required
        if capability in records
        and records[capability].get("effective_status") in {"unsupported", "detected_user_unsupported"}
    ]
    unverified = [
        capability
        for capability in required
        if capability not in records or records[capability].get("effective_status") == "unverified"
    ]
    return {"required": required, "unsupported": unsupported, "unverified": unverified}


class RunCreationError(ValueError):
    """Raised when a requested evaluation run cannot be scheduled."""


def _effective_scoring_rule(manifest: dict[str, object], prompt_package: PromptPackage | None) -> dict[str, object]:
    if prompt_package is not None and isinstance(prompt_package.scoring_rule, dict) and prompt_package.scoring_rule:
        return dict(prompt_package.scoring_rule)
    benchmark_rule = manifest.get("scoring")
    if isinstance(benchmark_rule, dict) and benchmark_rule:
        return dict(benchmark_rule)
    return {"type": "exact_match"}


def _request_body_evidence(
    *,
    endpoint: ModelEndpoint,
    benchmark_manifest: dict[str, object],
    suite_snapshot: dict[str, object] | None,
    request_body_override: dict[str, object] | None,
) -> dict[str, object]:
    """Build the frozen Request Body evidence attached to every sample attempt."""

    suite_defaults = suite_snapshot.get("default_request_body") if isinstance(suite_snapshot, dict) else None
    benchmark_defaults = benchmark_manifest.get("default_request_body")
    benchmark_forced = benchmark_manifest.get("forced_request_body")
    if not isinstance(benchmark_forced, dict):
        benchmark_forced = benchmark_manifest.get("required_request_body")
    return resolve_request_body(
        protocol_profile=str(endpoint.protocol_profile),
        model_defaults=endpoint.default_request_body,
        suite_defaults=suite_defaults if isinstance(suite_defaults, dict) else None,
        benchmark_defaults=benchmark_defaults if isinstance(benchmark_defaults, dict) else None,
        run_override=request_body_override,
        benchmark_forced=benchmark_forced if isinstance(benchmark_forced, dict) else None,
    )


def _build_messages(question: str, prompt_package: PromptPackage | None) -> list[dict[str, object]]:
    if prompt_package is None:
        return [{"role": "user", "content": question}]
    template = prompt_package.user_template
    messages: list[dict[str, object]] = []
    if prompt_package.system_message:
        messages.append({"role": "system", "content": prompt_package.system_message})
    for example in prompt_package.few_shot_examples:
        if (
            isinstance(example, dict)
            and isinstance(example.get("role"), str)
            and isinstance(example.get("content"), str)
        ):
            messages.append({"role": example["role"], "content": example["content"]})
    try:
        rendered = render_template(
            template,
            {
                "question": question,
                "choices": "",
                "context": "",
                "image": "",
                "audio": "",
                "video": "",
                "language": "",
                "output_schema": "",
            },
        )
    except PromptTemplateError as error:
        raise RunCreationError(str(error)) from error
    messages.append({"role": "user", "content": rendered})
    return messages


def _build_sample_messages(sample: object, prompt_package: PromptPackage | None) -> list[dict[str, object]]:
    """Preserve unified multimodal sample content while applying prompt packages to text samples."""

    raw_messages = getattr(sample, "messages", ())
    if isinstance(raw_messages, tuple) and raw_messages:
        messages = deepcopy(list(raw_messages))
        if prompt_package is None:
            return messages
        # Keep the immutable media message intact and prepend package-level system
        # and few-shot context. The sample itself remains the final user request.
        return _build_messages(str(getattr(sample, "prompt", "")), prompt_package)[:-1] + messages
    return _build_messages(str(getattr(sample, "prompt", "")), prompt_package)


def _sample_modality(sample: object) -> str:
    raw_messages = getattr(sample, "messages", ())
    if not isinstance(raw_messages, tuple) or not raw_messages:
        return "text"
    modalities: set[str] = set()
    for message in raw_messages:
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("type"), str) and part["type"] != "text":
                modalities.add(part["type"])
    if not modalities:
        return "text"
    return next(iter(modalities)) if len(modalities) == 1 else "multimodal"


def _estimate_request_tokens(prompt: str) -> int:
    """Conservative dependency-free estimate used only for TPM admission control."""

    return max(1, (len(prompt) + 3) // 4) + 32


def _estimate_sample_tokens(sample: object) -> int:
    """Estimate text plus a conservative token budget for each media part."""

    estimate = _estimate_request_tokens(str(getattr(sample, "prompt", "")))
    raw_messages = getattr(sample, "messages", ())
    if not isinstance(raw_messages, tuple):
        return estimate
    media_parts = sum(
        1
        for message in raw_messages
        if isinstance(message, dict) and isinstance(message.get("content"), list)
        for part in message["content"]
        if isinstance(part, dict) and part.get("type") not in {"text", "tool_result"}
    )
    return estimate + (media_parts * 256)


def _split_samples_into_shards(
    samples: tuple[object, ...],
    manifest: dict[str, object],
) -> tuple[tuple[object, ...], ...]:
    """Create independently leaseable shard tasks from manifest or modality guidance."""

    requested_size = manifest.get("shard_size")
    if isinstance(requested_size, int) and not isinstance(requested_size, bool) and requested_size > 0:
        shard_size = min(requested_size, 1_000)
    else:
        modalities = {str(item) for item in manifest.get("modalities", []) if isinstance(item, str)}
        shard_size = (
            5 if "video" in modalities else 20 if "audio" in modalities else 25 if "image" in modalities else 50
        )
    return tuple(tuple(samples[index : index + shard_size]) for index in range(0, len(samples), shard_size))


def _split_samples_for_endpoint_budget(
    samples: tuple[object, ...],
    manifest: dict[str, object],
    endpoint: object,
) -> tuple[tuple[object, ...], ...]:
    """Split manifest shards again until each task fits every endpoint window.

    Admission is atomic, but it can only admit a task that is individually
    below every configured request and token cap.  Sharding here keeps a run
    executable instead of creating work that can never be claimed.
    """

    return _split_items_for_endpoint_budget(
        _split_samples_into_shards(samples, manifest),
        endpoint,
        token_estimate=_estimate_sample_tokens,
    )


def _split_items_for_endpoint_budget(
    candidate_shards: tuple[tuple[object, ...], ...],
    endpoint: object,
    *,
    token_estimate: Callable[[object], int],
) -> tuple[tuple[object, ...], ...]:
    """Return budget-safe subshards for any items with a token estimator."""

    shards: list[tuple[object, ...]] = []
    for candidate_shard in candidate_shards:
        current: list[object] = []
        current_tokens = 0
        for item in candidate_shard:
            estimate = max(1, int(token_estimate(item)))
            if not _fits_endpoint_budget(endpoint, len(current) + 1, current_tokens + estimate):
                if not current:
                    raise RunCreationError(
                        "A benchmark sample exceeds the configured endpoint request or token budget."
                    )
                shards.append(tuple(current))
                current = []
                current_tokens = 0
                if not _fits_endpoint_budget(endpoint, 1, estimate):
                    raise RunCreationError(
                        "A benchmark sample exceeds the configured endpoint request or token budget."
                    )
            current.append(item)
            current_tokens += estimate
        if current:
            shards.append(tuple(current))
    return tuple(shards)


def _fits_endpoint_budget(endpoint: object, request_count: int, estimated_tokens: int) -> bool:
    estimated_output_tokens = min(estimated_tokens, request_count * 32)
    estimated_input_tokens = max(0, estimated_tokens - estimated_output_tokens)
    limits = (
        ("requests_per_second", request_count),
        ("requests_per_minute", request_count),
        ("tokens_per_minute", estimated_tokens),
        ("input_tokens_per_minute", estimated_input_tokens),
        ("output_tokens_per_minute", estimated_output_tokens),
    )
    for field, measured in limits:
        limit = _endpoint_positive_limit(endpoint, field)
        if limit is not None and measured > limit:
            return False
    return True


def _endpoint_positive_limit(endpoint: object, field: str) -> int | None:
    value = endpoint.get(field) if isinstance(endpoint, dict) else getattr(endpoint, field, None)
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return None
    return limit if limit > 0 else None


def _capability_compatibility(
    session: Session,
    endpoint_id: str,
    manifest: dict[str, object],
) -> dict[str, list[str]]:
    required = [capability for capability in manifest.get("required_capabilities", []) if isinstance(capability, str)]
    records = {
        record.capability_key: record
        for record in session.scalars(select(ModelCapability).where(ModelCapability.model_endpoint_id == endpoint_id))
    }
    unsupported = [
        capability
        for capability in required
        if records.get(capability)
        and records[capability].effective_status in {"unsupported", "detected_user_unsupported"}
    ]
    unverified = [
        capability
        for capability in required
        if capability not in records or records[capability].effective_status == "unverified"
    ]
    return {"required": required, "unsupported": unsupported, "unverified": unverified}
