from __future__ import annotations

from sqlalchemy.orm import Session

from app.benchmarks import TEXT_QUICK_CHECK
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


class RunCreationError(ValueError):
    """Raised when a requested evaluation run cannot be scheduled."""


def create_text_quick_check_run(
    session: Session,
    *,
    model_endpoint_id: str,
    sample_limit: int | None,
    prompt_package_id: str | None = None,
) -> EvaluationRun:
    endpoint = session.get(ModelEndpoint, model_endpoint_id)
    if endpoint is None:
        raise RunCreationError("Model endpoint not found.")
    if endpoint.status != EndpointStatus.AVAILABLE.value:
        raise RunCreationError("Model endpoint must pass a connection test before scheduling a run.")

    samples = TEXT_QUICK_CHECK.samples[:sample_limit]
    if not samples:
        raise RunCreationError("At least one benchmark sample is required.")
    prompt_package = session.get(PromptPackage, prompt_package_id) if prompt_package_id else None
    if prompt_package_id and prompt_package is None:
        raise RunCreationError("Prompt package not found.")

    snapshot = {
        "benchmark": {
            "id": TEXT_QUICK_CHECK.identifier,
            "version": TEXT_QUICK_CHECK.version,
        },
        "endpoint": {
            "id": endpoint.id,
            "base_url": endpoint.base_url,
            "model_name": endpoint.model_name,
            "protocol_profile": endpoint.protocol_profile,
            "default_request_body": endpoint.default_request_body,
        },
        "sample_ids": [sample.sample_id for sample in samples],
        "prompt_package": (
            {"id": prompt_package.id, "name": prompt_package.name, "version": prompt_package.version,
             "system_message": prompt_package.system_message, "user_template": prompt_package.user_template,
             "few_shot_examples": prompt_package.few_shot_examples}
            if prompt_package else None
        ),
    }
    run = EvaluationRun(
        model_endpoint_id=endpoint.id,
        prompt_package_id=prompt_package.id if prompt_package else None,
        benchmark_id=TEXT_QUICK_CHECK.identifier,
        benchmark_version=TEXT_QUICK_CHECK.version,
        configuration_snapshot=snapshot,
        status=RunStatus.QUEUED.value,
        total_samples=len(samples),
    )
    session.add(run)
    session.flush()

    task = TaskUnit(
        run_id=run.id,
        task_type="evaluation_shard",
        payload={"sample_ids": [sample.sample_id for sample in samples]},
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
