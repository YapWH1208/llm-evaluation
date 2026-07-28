from __future__ import annotations

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
from app.db.models import ModelCapability
from app.db.models import BenchmarkDefinition
from app.services.request_body import resolve_request_body
from app.services.prompt_templates import PromptTemplateError, render_template, standardization_flags


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

    request_body_evidence = _request_body_evidence(
        endpoint=endpoint,
        benchmark_manifest=plugin.manifest,
        suite_snapshot=suite_snapshot,
        request_body_override=request_body_override,
    )
    scoring_rule = _effective_scoring_rule(plugin.manifest, prompt_package)

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
        },
        "sample_ids": [sample.sample_id for sample in samples],
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
        status=RunStatus.QUEUED.value,
        total_samples=len(samples),
    )
    session.add(run)
    session.flush()

    dataset_task = TaskUnit(
        run_id=run.id,
        task_type=TaskType.DATASET_PREPARATION.value,
        payload={
            "dataset_manifest": plugin.manifest.get("dataset_manifest", {}),
            "prepared_inline": True,
        },
        status=TaskStatus.SUCCEEDED.value,
    )
    session.add(dataset_task)
    session.flush()
    benchmark_task = TaskUnit(
        run_id=run.id,
        parent_task_id=dataset_task.id,
        task_type=TaskType.BENCHMARK.value,
        payload={"benchmark_id": benchmark_id, "benchmark_version": benchmark_version, "planned_samples": len(samples)},
        status=TaskStatus.SUCCEEDED.value,
    )
    session.add(benchmark_task)
    session.flush()
    task = TaskUnit(
        run_id=run.id,
        parent_task_id=benchmark_task.id,
        task_type=TaskType.EVALUATION_SHARD.value,
        payload={
            "sample_ids": [sample.sample_id for sample in samples],
            "estimated_request_count": len(samples),
            "estimated_token_count": sum(_estimate_request_tokens(sample.prompt) for sample in samples),
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
                    "messages": _build_messages(sample.prompt, prompt_package),
                    "modality": "text",
                    "request_body_evidence": request_body_evidence,
                },
                reference_snapshot={"type": str(scoring_rule.get("type", "exact_match")), "answer": sample.reference_answer, "scoring": scoring_rule},
            )
            for sample in samples
        ]
    )
    session.commit()
    session.refresh(run)
    return run


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


def _estimate_request_tokens(prompt: str) -> int:
    """Conservative dependency-free estimate used only for TPM admission control."""

    return max(1, (len(prompt) + 3) // 4) + 32


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
