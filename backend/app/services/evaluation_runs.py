from __future__ import annotations

from copy import deepcopy
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.benchmarks import get_installed_plugin
from app.db import (
    EndpointStatus,
    EvaluationRun,
    ModelEndpoint,
    PromptPackage,
    RunStatus,
    SampleAttempt,
    TaskStatus,
    TaskType,
    TaskUnit,
)
from app.db.models import DatasetVersion, ModelCapability
from app.db.models import BenchmarkDefinition
from app.services.request_body import resolve_request_body
from app.services.prompt_templates import PromptTemplateError, render_template, standardization_flags
from app.services.scoring import ScoringError, validate_scoring_rule


class RunCreationError(ValueError):
    """Raised when a requested evaluation run cannot be scheduled."""


def create_text_quick_check_run(
    session: Session,
    *,
    model_endpoint_id: str,
    sample_limit: int | None,
    prompt_package_id: str | None = None,
) -> EvaluationRun:
    return create_benchmark_run(
        session,
        model_endpoint_id=model_endpoint_id,
        sample_limit=sample_limit,
        prompt_package_id=prompt_package_id,
        benchmark_id="text-quick-check",
        benchmark_version="1.0.0",
    )


def preflight_benchmark_run(
    session: Session,
    *,
    model_endpoint_id: str,
    sample_limit: int | None,
    prompt_package_id: str | None,
    benchmark_id: str,
    benchmark_version: str,
    request_body_override: dict[str, object] | None = None,
) -> dict[str, object]:
    """Validate scheduling inputs and estimate work without creating a run."""

    endpoint = session.get(ModelEndpoint, model_endpoint_id)
    issues: list[str] = []
    if endpoint is None:
        return {
            "can_queue": False,
            "issues": ["Model endpoint not found."],
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
    if endpoint.status != EndpointStatus.AVAILABLE.value:
        issues.append("Model endpoint must pass a connection test before scheduling a run.")
    definition = session.scalar(
        select(BenchmarkDefinition).where(
            BenchmarkDefinition.benchmark_id == benchmark_id,
            BenchmarkDefinition.version == benchmark_version,
        )
    )
    if definition is not None and definition.status in {"disabled", "deprecated", "broken"}:
        issues.append(f"Benchmark {benchmark_id}@{benchmark_version} is {definition.status} and cannot be scheduled.")
    plugin = get_installed_plugin(benchmark_id, benchmark_version)
    if plugin is None:
        return {
            "can_queue": False,
            "issues": [*issues, "Benchmark plugin is not installed for the requested version."],
            "sample_count": 0,
            "estimated_requests": 0,
            "estimated_input_tokens": 0,
            "estimated_output_tokens": 0,
            "estimated_cost": None,
            "currency": endpoint.currency,
            "compatibility": {"required": [], "unsupported": [], "unverified": []},
            "datasets": [],
            "request_body_evidence": None,
        }
    samples = plugin.samples(sample_limit)
    if not samples:
        issues.append("At least one benchmark sample is required.")
    compatibility = _capability_compatibility(session, endpoint.id, plugin.manifest)
    if compatibility["unsupported"]:
        issues.append("Model endpoint is incompatible with required benchmark capabilities: " + ", ".join(compatibility["unsupported"]))
    prompt_package = session.get(PromptPackage, prompt_package_id) if prompt_package_id else None
    if prompt_package_id and prompt_package is None:
        issues.append("Prompt package not found.")
    try:
        validate_scoring_rule(_effective_scoring_rule(plugin.manifest, prompt_package))
    except ScoringError as error:
        issues.append(f"Scoring rule is invalid: {error}")
    datasets: list[dict[str, object]] = []
    for descriptor in plugin.manifest.get("datasets", []):
        if not isinstance(descriptor, dict) or not isinstance(descriptor.get("dataset_id"), str):
            continue
        query = select(DatasetVersion).where(DatasetVersion.dataset_id == descriptor["dataset_id"])
        if isinstance(descriptor.get("version"), str):
            query = query.where(DatasetVersion.version == descriptor["version"])
        if isinstance(descriptor.get("revision"), str):
            query = query.where(DatasetVersion.revision == descriptor["revision"])
        dataset = session.scalar(query.order_by(DatasetVersion.created_at.desc()))
        if dataset is None:
            if isinstance(descriptor.get("source_url"), str) and descriptor["source_url"].strip():
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
                datasets.append({"dataset_id": descriptor["dataset_id"], "status": "missing", "will_prepare": False})
        else:
            datasets.append({"id": dataset.id, "dataset_id": dataset.dataset_id, "version": dataset.version, "revision": dataset.revision, "status": dataset.status, "will_prepare": dataset.status != "ready"})
    estimated_input_tokens = sum(_estimate_sample_tokens(sample) for sample in samples)
    estimated_output_tokens = len(samples) * 64
    estimated_cost = (
        ((estimated_input_tokens * endpoint.input_cost_per_million) + (estimated_output_tokens * endpoint.output_cost_per_million)) / 1_000_000
        if endpoint.input_cost_per_million is not None and endpoint.output_cost_per_million is not None
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
        "currency": endpoint.currency,
        "compatibility": compatibility,
        "datasets": datasets,
        "request_body_evidence": _request_body_evidence(
            endpoint=endpoint,
            benchmark_manifest=plugin.manifest,
            suite_snapshot=None,
            request_body_override=request_body_override,
        ),
    }


def create_benchmark_run(
    session: Session,
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
) -> EvaluationRun:
    endpoint = session.get(ModelEndpoint, model_endpoint_id)
    if endpoint is None:
        raise RunCreationError("Model endpoint not found.")
    if endpoint.status != EndpointStatus.AVAILABLE.value:
        raise RunCreationError("Model endpoint must pass a connection test before scheduling a run.")

    definition = session.scalar(
        select(BenchmarkDefinition).where(
            BenchmarkDefinition.benchmark_id == benchmark_id,
            BenchmarkDefinition.version == benchmark_version,
        )
    )
    if definition is not None and definition.status in {"disabled", "deprecated", "broken"}:
        raise RunCreationError(f"Benchmark {benchmark_id}@{benchmark_version} is {definition.status} and cannot be scheduled.")

    plugin = get_installed_plugin(benchmark_id, benchmark_version)
    if plugin is None:
        raise RunCreationError("Benchmark plugin is not installed for the requested version.")
    samples = plugin.samples(sample_limit)
    if not samples:
        raise RunCreationError("At least one benchmark sample is required.")
    compatibility = _capability_compatibility(session, endpoint.id, plugin.manifest)
    if compatibility["unsupported"]:
        raise RunCreationError(
            "Model endpoint is incompatible with required benchmark capabilities: "
            + ", ".join(compatibility["unsupported"])
        )
    prompt_package = session.get(PromptPackage, prompt_package_id) if prompt_package_id else None
    if prompt_package_id and prompt_package is None:
        raise RunCreationError("Prompt package not found.")
    frozen_datasets = _freeze_declared_datasets(
        session,
        declared_datasets if declared_datasets is not None else plugin.manifest.get("datasets"),
    )

    request_body_evidence = _request_body_evidence(
        endpoint=endpoint,
        benchmark_manifest=plugin.manifest,
        suite_snapshot=suite_snapshot,
        request_body_override=request_body_override,
    )
    scoring_rule = _effective_scoring_rule(plugin.manifest, prompt_package)
    try:
        validate_scoring_rule(scoring_rule)
    except ScoringError as error:
        raise RunCreationError(f"Scoring rule is invalid: {error}") from error

    snapshot = {
        "benchmark": {
            "id": benchmark_id,
            "version": benchmark_version,
            "manifest": plugin.manifest,
        },
        "endpoint": {
            "id": endpoint.id,
            "base_url": endpoint.base_url,
            "model_name": endpoint.model_name,
            "protocol_profile": endpoint.protocol_profile,
            "default_request_body": endpoint.default_request_body,
            "timeout_seconds": endpoint.timeout_seconds,
            "custom_headers": endpoint.custom_headers,
            "input_cost_per_million": endpoint.input_cost_per_million,
            "output_cost_per_million": endpoint.output_cost_per_million,
        },
        "sample_ids": [sample.sample_id for sample in samples],
        "datasets": frozen_datasets,
        "capability_compatibility": compatibility,
        "prompt_package": (
            {"id": prompt_package.id, "name": prompt_package.name, "version": prompt_package.version,
             "system_message": prompt_package.system_message, "user_template": prompt_package.user_template,
             "few_shot_examples": prompt_package.few_shot_examples, "scoring_rule": prompt_package.scoring_rule}
            if prompt_package else None
        ),
        "prompt_standardization": (
            {"is_standard": not standardization_flags(prompt_package), "flags": standardization_flags(prompt_package)}
            if prompt_package else {"is_standard": True, "flags": []}
        ),
        "evaluation_suite": suite_snapshot,
        "request_body_evidence": request_body_evidence,
    }
    run = EvaluationRun(
        model_endpoint_id=endpoint.id,
        prompt_package_id=prompt_package.id if prompt_package else None,
        suite_id=suite_id,
        created_by=created_by,
        max_concurrency=max_concurrency,
        benchmark_id=benchmark_id,
        benchmark_version=benchmark_version,
        configuration_snapshot=snapshot,
        status=RunStatus.WAITING_FOR_DATASET.value if frozen_datasets else RunStatus.QUEUED.value,
        total_samples=len(samples),
    )
    session.add(run)
    session.flush()

    dataset_task = TaskUnit(
        run_id=run.id,
        task_type=TaskType.DATASET_PREPARATION.value,
        payload={
            "datasets": frozen_datasets,
            "prepared_inline": not bool(frozen_datasets),
        },
        status=TaskStatus.PENDING.value if frozen_datasets else TaskStatus.SUCCEEDED.value,
    )
    session.add(dataset_task)
    session.flush()
    benchmark_task = TaskUnit(
        run_id=run.id,
        parent_task_id=dataset_task.id,
        task_type=TaskType.BENCHMARK.value,
        payload={"benchmark_id": benchmark_id, "benchmark_version": benchmark_version, "planned_samples": len(samples)},
        status=TaskStatus.PENDING.value if frozen_datasets else TaskStatus.SUCCEEDED.value,
    )
    session.add(benchmark_task)
    session.flush()
    shards = _split_samples_into_shards(samples, plugin.manifest)
    if endpoint.requests_per_second is not None and any(len(shard) > endpoint.requests_per_second for shard in shards):
        shards = [(sample,) for sample in samples]
    for shard_index, shard_samples in enumerate(shards, start=1):
        task = TaskUnit(
            run_id=run.id,
            parent_task_id=benchmark_task.id,
            task_type=TaskType.EVALUATION_SHARD.value,
            payload={
                "sample_ids": [sample.sample_id for sample in shard_samples],
                "estimated_request_count": len(shard_samples),
                "estimated_token_count": sum(_estimate_sample_tokens(sample) for sample in shard_samples),
                "shard_index": shard_index,
                "shard_count": len(shards),
                "retry_policy": {"max_attempts": 3, "base_delay_seconds": 2, "max_delay_seconds": 60},
            },
            status=TaskStatus.PENDING.value,
        )
        session.add(task)
        session.flush()
        session.add_all(
            [
                SampleAttempt(
                    run_id=run.id,
                    task_id=task.id,
                    sample_id=sample.sample_id,
                    input_snapshot={
                        "messages": _build_sample_messages(sample, prompt_package),
                        "modality": _sample_modality(sample),
                        "metadata": dict(sample.metadata),
                        "request_body_evidence": request_body_evidence,
                    },
                    reference_snapshot={"type": str(scoring_rule.get("type", "exact_match")), "answer": sample.reference_answer, "scoring": scoring_rule},
                )
                for sample in shard_samples
            ]
        )
    session.commit()
    session.refresh(run)
    return run


def _freeze_declared_datasets(
    session: Session,
    descriptors: object,
) -> list[dict[str, object]]:
    """Resolve manifest descriptors to immutable registered dataset revisions."""

    if not isinstance(descriptors, list):
        return []
    frozen: list[dict[str, object]] = []
    for descriptor in descriptors:
        if not isinstance(descriptor, dict) or not isinstance(descriptor.get("dataset_id"), str):
            raise RunCreationError("Benchmark dataset descriptors require a dataset_id.")
        existing_id = descriptor.get("dataset_version_id")
        if isinstance(existing_id, str):
            dataset = session.get(DatasetVersion, existing_id)
            if dataset is None:
                raise RunCreationError(f"Declared dataset revision {existing_id} is not registered.")
        else:
            query = select(DatasetVersion).where(DatasetVersion.dataset_id == descriptor["dataset_id"])
            if isinstance(descriptor.get("version"), str):
                query = query.where(DatasetVersion.version == descriptor["version"])
            if isinstance(descriptor.get("revision"), str):
                query = query.where(DatasetVersion.revision == descriptor["revision"])
            dataset = session.scalar(query.order_by(DatasetVersion.created_at.desc()))
            if dataset is None:
                dataset = _register_declared_dataset(session, descriptor)
        frozen.append(
            {
                **descriptor,
                "dataset_version_id": dataset.id,
                "dataset_id": dataset.dataset_id,
                "version": dataset.version,
                "revision": dataset.revision,
                "checksum": dataset.checksum,
            }
        )
    return frozen


def _register_declared_dataset(session: Session, descriptor: dict[str, object]) -> DatasetVersion:
    """Register a manifest-owned remote revision before its preparation task runs.

    Benchmark manifests are the authoritative source for reproducible public
    datasets.  Capturing the descriptor at scheduling time lets the normal
    licence, credential, checksum, download, and preparation workflow run
    without a separate, error-prone administrator registration step.
    """

    source_url = descriptor.get("source_url")
    if not isinstance(source_url, str) or not source_url.strip():
        raise RunCreationError(f"Required dataset {descriptor['dataset_id']} is not registered.")
    version = descriptor.get("version")
    revision = descriptor.get("revision")
    license_text = descriptor.get("license_text")
    credential_binding_id = descriptor.get("credential_binding_id")
    checksum = descriptor.get("checksum")
    dataset = DatasetVersion(
        dataset_id=str(descriptor["dataset_id"]),
        version=version.strip() if isinstance(version, str) and version.strip() else "default",
        revision=revision.strip() if isinstance(revision, str) and revision.strip() else "default",
        source_url=source_url.strip(),
        checksum=checksum.strip() if isinstance(checksum, str) and checksum.strip() else None,
        license_text=license_text.strip() if isinstance(license_text, str) and license_text.strip() else None,
        credential_binding_id=(
            credential_binding_id.strip()
            if isinstance(credential_binding_id, str) and credential_binding_id.strip()
            else None
        ),
        status=("license_required" if isinstance(license_text, str) and license_text.strip() else "not_downloaded"),
    )
    session.add(dataset)
    session.flush()
    return dataset


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

    suite_defaults = (
        suite_snapshot.get("default_request_body")
        if isinstance(suite_snapshot, dict)
        else None
    )
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
        if isinstance(example, dict) and isinstance(example.get("role"), str) and isinstance(example.get("content"), str):
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
        shard_size = 5 if "video" in modalities else 20 if "audio" in modalities else 25 if "image" in modalities else 50
    return tuple(tuple(samples[index : index + shard_size]) for index in range(0, len(samples), shard_size))


def _capability_compatibility(
    session: Session,
    endpoint_id: str,
    manifest: dict[str, object],
) -> dict[str, list[str]]:
    required = [
        capability
        for capability in manifest.get("required_capabilities", [])
        if isinstance(capability, str)
    ]
    records = {
        record.capability_key: record
        for record in session.scalars(
            select(ModelCapability).where(ModelCapability.model_endpoint_id == endpoint_id)
        )
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
