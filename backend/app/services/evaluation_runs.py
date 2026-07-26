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
    TaskUnit,
)
from app.db.models import ModelCapability


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
) -> EvaluationRun:
    endpoint = session.get(ModelEndpoint, model_endpoint_id)
    if endpoint is None:
        raise RunCreationError("Model endpoint not found.")
    if endpoint.status != EndpointStatus.AVAILABLE.value:
        raise RunCreationError("Model endpoint must pass a connection test before scheduling a run.")

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
             "few_shot_examples": prompt_package.few_shot_examples}
            if prompt_package else None
        ),
        "evaluation_suite": suite_snapshot,
    }
    run = EvaluationRun(
        model_endpoint_id=endpoint.id,
        prompt_package_id=prompt_package.id if prompt_package else None,
        suite_id=suite_id,
        benchmark_id=benchmark_id,
        benchmark_version=benchmark_version,
        configuration_snapshot=snapshot,
        status=RunStatus.QUEUED.value,
        total_samples=len(samples),
    )
    session.add(run)
    session.flush()

    task = TaskUnit(
        run_id=run.id,
        task_type="evaluation_shard",
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
                },
                reference_snapshot={"type": "exact_match", "answer": sample.reference_answer},
            )
            for sample in samples
        ]
    )
    session.commit()
    session.refresh(run)
    return run


def _build_messages(question: str, prompt_package: PromptPackage | None) -> list[dict[str, object]]:
    if prompt_package is None:
        return [{"role": "user", "content": question}]
    template = prompt_package.user_template
    if "{{ question }}" not in template:
        raise RunCreationError("Prompt package user template must contain {{ question }}.")
    messages: list[dict[str, object]] = []
    if prompt_package.system_message:
        messages.append({"role": "system", "content": prompt_package.system_message})
    for example in prompt_package.few_shot_examples:
        if isinstance(example, dict) and isinstance(example.get("role"), str) and isinstance(example.get("content"), str):
            messages.append({"role": example["role"], "content": example["content"]})
    messages.append({"role": "user", "content": template.replace("{{ question }}", question)})
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
