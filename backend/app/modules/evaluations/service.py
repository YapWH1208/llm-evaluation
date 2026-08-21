from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.benchmarks import get_installed_plugin
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.endpoints.models import EndpointStatus
from app.modules.evaluations.models import RunStatus, SampleAttemptStatus, TaskStatus, TaskType
from app.modules.benchmarks.prompts import standardization_flags
from app.modules.benchmarks.scoring import ScoringError, validate_scoring_rule
from app.modules.evaluations.names import format_run_display_name
from app.modules.evaluations.analysis import build_repository_run_summary
from app.modules.evaluations.evidence import (
    decorate_attempts,
    filter_attempts,
    run_logs,
    run_progress,
)
from app.modules.evaluations.lifecycle import RunLifecycle
from app.modules.evaluations.planning import (
    attempt_values,
    build_sample_messages,
    capability_compatibility,
    effective_scoring_rule,
    empty_preflight,
    endpoint_snapshot,
    estimate_retry_attempt_tokens,
    estimate_sample_tokens,
    prompt_snapshot,
    record_proxy,
    request_body_evidence,
    sample_modality,
    split_items_for_endpoint_budget,
    split_samples_for_endpoint_budget,
    task_values,
)
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
            return empty_preflight("Model endpoint not found.")
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
                **empty_preflight("Benchmark plugin is not installed for the requested version."),
                "issues": [*issues, "Benchmark plugin is not installed for the requested version."],
                "currency": endpoint.get("currency"),
            }
        samples = plugin.samples(sample_limit)
        endpoint_proxy = record_proxy(endpoint)
        if not samples:
            issues.append("At least one benchmark sample is required.")
        else:
            try:
                split_samples_for_endpoint_budget(samples, plugin.manifest, endpoint_proxy)
            except ValidationError as error:
                issues.append(str(error))
        compatibility = capability_compatibility(self._repository.list_capabilities(model_endpoint_id), plugin.manifest)
        if compatibility["unsupported"]:
            issues.append(
                "Model endpoint is incompatible with required benchmark capabilities: "
                + ", ".join(compatibility["unsupported"])
            )
        prompt_package = self._repository.get_prompt_package(prompt_package_id) if prompt_package_id else None
        if prompt_package_id and prompt_package is None:
            issues.append("Prompt package not found.")
        prompt_proxy = record_proxy(prompt_package) if prompt_package else None
        try:
            validate_scoring_rule(effective_scoring_rule(plugin.manifest, prompt_proxy))
        except ScoringError as error:
            issues.append(f"Scoring rule is invalid: {error}")
        datasets = self._preflight_declared_datasets(plugin.manifest.get("datasets"), issues)
        estimated_input_tokens = sum(estimate_sample_tokens(sample) for sample in samples)
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
            "request_body_evidence": request_body_evidence(
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
        compatibility = capability_compatibility(self._repository.list_capabilities(model_endpoint_id), plugin.manifest)
        if compatibility["unsupported"]:
            raise ConflictError(
                "Model endpoint is incompatible with required benchmark capabilities: "
                + ", ".join(compatibility["unsupported"])
            )
        prompt_package = self._repository.get_prompt_package(prompt_package_id) if prompt_package_id else None
        if prompt_package_id and prompt_package is None:
            raise NotFoundError("Prompt package not found.")
        prompt_proxy = record_proxy(prompt_package) if prompt_package else None
        frozen_datasets = self._freeze_declared_datasets(
            declared_datasets if declared_datasets is not None else plugin.manifest.get("datasets")
        )
        endpoint_proxy = record_proxy(endpoint)
        frozen_request_body = request_body_evidence(
            endpoint=endpoint_proxy,
            benchmark_manifest=plugin.manifest,
            suite_snapshot=suite_snapshot,
            request_body_override=request_body_override,
        )
        scoring_rule = effective_scoring_rule(plugin.manifest, prompt_proxy)
        try:
            validate_scoring_rule(scoring_rule)
            shards = split_samples_for_endpoint_budget(samples, plugin.manifest, endpoint_proxy)
        except (ScoringError, ValidationError) as error:
            raise ConflictError(str(error)) from error

        now = datetime.now(timezone.utc)
        snapshot = {
            "benchmark": {"id": benchmark_id, "version": benchmark_version, "manifest": plugin.manifest},
            "endpoint": endpoint_snapshot(endpoint),
            "sample_ids": [sample.sample_id for sample in samples],
            "datasets": frozen_datasets,
            "capability_compatibility": compatibility,
            "prompt_package": prompt_snapshot(prompt_package),
            "prompt_standardization": (
                {
                    "is_standard": not standardization_flags(prompt_proxy),
                    "flags": standardization_flags(prompt_proxy),
                }
                if prompt_proxy
                else {"is_standard": True, "flags": []}
            ),
            "evaluation_suite": suite_snapshot,
            "request_body_evidence": frozen_request_body,
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
            task_values(
                "dataset",
                task_type=TaskType.DATASET_PREPARATION.value,
                payload={"datasets": frozen_datasets, "prepared_inline": not bool(frozen_datasets)},
                task_status=TaskStatus.PENDING.value if frozen_datasets else TaskStatus.SUCCEEDED.value,
                now=now,
            ),
            task_values(
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
                task_values(
                    task_key,
                    parent_key="benchmark",
                    task_type=TaskType.EVALUATION_SHARD.value,
                    payload={
                        "sample_ids": [sample.sample_id for sample in shard_samples],
                        "estimated_request_count": len(shard_samples),
                        "estimated_token_count": sum(estimate_sample_tokens(sample) for sample in shard_samples),
                        "sample_token_estimates": {
                            sample.sample_id: estimate_sample_tokens(sample) for sample in shard_samples
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
                attempt_values(
                    task_key,
                    sample_id=sample.sample_id,
                    input_snapshot={
                        "messages": build_sample_messages(sample, prompt_proxy),
                        "modality": sample_modality(sample),
                        "metadata": dict(sample.metadata),
                        "request_body_evidence": frozen_request_body,
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

    def create_dataset_run(self, **values: Any) -> dict[str, Any]:
        from app.modules.evaluations.dataset_runs import create_dataset_run

        return create_dataset_run(self._repository, data_root=self._data_root, **values)

    def preflight_dataset_run(self, **values: Any) -> dict[str, object]:
        from app.modules.evaluations.dataset_runs import preflight_dataset_run

        return preflight_dataset_run(self._repository, data_root=self._data_root, **values)

    def create_custom_run(self, **values: Any) -> dict[str, Any]:
        from app.modules.evaluations.custom_runs import create_custom_multimodal_run

        return create_custom_multimodal_run(self._repository, data_root=self._data_root, **values)

    def retry_failed(self, run_id: str) -> dict[str, Any]:
        run = self.get(run_id)
        if run.get("status") not in {RunStatus.COMPLETED.value, RunStatus.COMPLETED_WITH_ERRORS.value}:
            raise ConflictError("Only completed evaluation runs can retry failed samples.")

        latest: dict[str, dict[str, Any]] = {}
        for attempt in self._repository.list_attempts(run_id):
            sample_id = str(attempt["sample_id"])
            previous = latest.get(sample_id)
            if previous is None or int(attempt.get("attempt_number", 1)) > int(previous.get("attempt_number", 1)):
                latest[sample_id] = attempt
        failed = [attempt for attempt in latest.values() if attempt.get("status") == SampleAttemptStatus.FAILED.value]
        if not failed:
            raise ConflictError("This run has no failed samples to retry.")

        endpoint = self._repository.get_endpoint(str(run["model_endpoint_id"]))
        if endpoint is None:
            raise ConflictError("The model endpoint for this run no longer exists.")
        tasks = self._repository.list_tasks(run_id)
        source_tasks = [task for task in tasks if task.get("task_type") == TaskType.EVALUATION_SHARD.value]
        source_payload = source_tasks[-1].get("payload") if source_tasks else None
        retry_policy = (
            source_payload.get("retry_policy")
            if isinstance(source_payload, dict) and isinstance(source_payload.get("retry_policy"), dict)
            else {"max_attempts": 3, "base_delay_seconds": 2, "max_delay_seconds": 60}
        )
        benchmark_tasks = [task for task in tasks if task.get("task_type") == TaskType.BENCHMARK.value]
        parent_id = str(benchmark_tasks[-1]["id"]) if benchmark_tasks else None
        try:
            retry_groups = split_items_for_endpoint_budget(
                (tuple(failed),),
                record_proxy(endpoint),
                token_estimate=estimate_retry_attempt_tokens,
            )
        except ValidationError as error:
            raise ConflictError(str(error)) from error

        now = datetime.now(timezone.utc)
        new_tasks: list[dict[str, Any]] = []
        new_attempts: list[dict[str, Any]] = []
        for index, group in enumerate(retry_groups):
            task_key = f"retry-{index}"
            token_estimates = {str(attempt["sample_id"]): estimate_retry_attempt_tokens(attempt) for attempt in group}
            task = task_values(
                task_key,
                task_type=TaskType.EVALUATION_SHARD.value,
                payload={
                    "sample_ids": [attempt["sample_id"] for attempt in group],
                    "estimated_request_count": len(group),
                    "estimated_token_count": sum(token_estimates.values()),
                    "sample_token_estimates": token_estimates,
                    "retry_policy": retry_policy,
                    "manual_retry": True,
                },
                task_status=TaskStatus.PENDING.value,
                now=now,
            )
            task["parent_id"] = parent_id
            new_tasks.append(task)
            for attempt in group:
                values = attempt_values(
                    task_key,
                    sample_id=str(attempt["sample_id"]),
                    input_snapshot=dict(attempt["input_snapshot"]),
                    reference_snapshot=dict(attempt["reference_snapshot"]),
                    now=now,
                )
                values["attempt_number"] = int(attempt.get("attempt_number", 1)) + 1
                new_attempts.append(values)
        self._repository.append_run_graph(run_id, new_tasks, new_attempts)
        return self._updated_run(
            run_id,
            {
                "status": RunStatus.QUEUED.value,
                "completed_at": None,
                "completed_samples": max(0, int(run.get("completed_samples", 0)) - len(failed)),
                "failed_samples": 0,
            },
        )

    def create_suite(self, values: dict[str, Any], *, created_by: str | None) -> dict[str, Any]:
        try:
            return self._repository.create_suite(
                {**values, "created_by": created_by, "created_at": datetime.now(timezone.utc)}
            )
        except ValueError as error:
            raise ConflictError(str(error)) from error

    def list_suites(self) -> list[dict[str, Any]]:
        return self._repository.list_suites()

    def get_suite(self, suite_id: str) -> dict[str, Any]:
        suite = self._repository.get_suite(suite_id)
        if suite is None:
            raise NotFoundError("Evaluation suite not found", context={"suite_id": suite_id})
        return suite

    def update_suite(self, suite_id: str, values: dict[str, Any]) -> dict[str, Any]:
        self.get_suite(suite_id)
        suite = self._repository.update_suite(suite_id, values)
        if suite is None:
            raise NotFoundError("Evaluation suite not found", context={"suite_id": suite_id})
        return suite

    def create_suite_runs(
        self,
        suite_id: str,
        *,
        model_endpoint_id: str,
        sample_limit: int | None,
        request_body_override: dict[str, Any],
        max_concurrency: int | None,
        created_by: str | None,
    ) -> list[dict[str, Any]]:
        suite = self.get_suite(suite_id)
        results: list[dict[str, Any]] = []
        for selection in suite["benchmark_list"]:
            if not isinstance(selection, dict) or not isinstance(selection.get("benchmark_id"), str):
                raise ConflictError("Suite benchmarks require benchmark_id entries.")
            benchmark_id = selection["benchmark_id"]
            benchmark_version = str(selection.get("version", "1.0.0"))
            prompt_package_id = selection.get("prompt_package_id")
            if prompt_package_id is None:
                overrides = suite.get("default_prompt_overrides")
                if isinstance(overrides, dict):
                    prompt_package_id = overrides.get(
                        f"{benchmark_id}@{benchmark_version}",
                        overrides.get(benchmark_id),
                    )
            if prompt_package_id is not None and not isinstance(prompt_package_id, str):
                raise ConflictError("Suite prompt_package_id must be a string.")
            snapshot = {
                "id": suite["id"],
                "name": suite["name"],
                "version": suite["version"],
                "default_prompt_overrides": suite.get("default_prompt_overrides", {}),
                "default_request_body": suite["default_request_body"],
                "weight_configuration": suite["weight_configuration"],
                "selection": selection,
                "effective_prompt_package_id": prompt_package_id,
            }
            results.append(
                self.create_benchmark(
                    model_endpoint_id=model_endpoint_id,
                    sample_limit=sample_limit,
                    prompt_package_id=prompt_package_id,
                    benchmark_id=benchmark_id,
                    benchmark_version=benchmark_version,
                    suite_id=str(suite["id"]),
                    suite_snapshot=snapshot,
                    request_body_override=request_body_override,
                    created_by=created_by,
                    max_concurrency=max_concurrency,
                )
            )
        return results

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
        return build_repository_run_summary(self._repository, run_id)

    def event_payload(self, run_id: str) -> dict[str, Any]:
        progress = self.progress(run_id)
        return {**progress, "summary": self.summary(run_id)}

    def _updated_run(self, run_id: str, values: dict[str, Any]) -> dict[str, Any]:
        run = self._repository.update_run(run_id, values)
        if run is None:
            raise NotFoundError("Evaluation run not found", context={"run_id": run_id})
        return run
