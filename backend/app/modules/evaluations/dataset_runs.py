from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.benchmarks.registry import BenchmarkSample
from app.core.errors import ApplicationError, ConflictError, NotFoundError, ValidationError
from app.modules.datasets.models import DatasetStatus
from app.modules.endpoints.models import EndpointStatus
from app.modules.evaluations.models import RunStatus, TaskStatus, TaskType
from app.modules.datasets.records import DatasetRecordError, iter_dataset_records
from app.modules.evaluations.names import format_run_display_name
from app.modules.evaluations.ports import EvaluationRepository
from app.modules.evaluations.planning import (
    attempt_values,
    build_sample_messages,
    capability_compatibility,
    endpoint_snapshot,
    estimate_sample_tokens,
    prompt_snapshot,
    record_proxy,
    request_body_evidence,
    split_samples_for_endpoint_budget,
    task_values,
)
from app.modules.benchmarks.prompts import PromptTemplateError, render_template
from app.modules.reviews.scoring import (
    JudgeScoringError,
    is_llm_judge_rule,
    judge_configuration_snapshot,
    judge_preflight_estimate,
    normalize_judge_rule,
    validate_judge_endpoint,
)
from app.modules.benchmarks.scoring import ScoringError, validate_scoring_rule


DATASET_RUN_BENCHMARK_ID = "dataset-evaluation"
DATASET_RUN_BENCHMARK_VERSION = "1.0.0"
DATASET_RUN_DEFAULT_SAMPLE_LIMIT = 100

_FIXED_TEMPLATE_KEYS = {
    "question": "",
    "choices": "",
    "context": "",
    "image": "",
    "audio": "",
    "video": "",
    "language": "",
    "output_schema": "",
}


def _effective_dataset_input_field(input_field: str | None, prompt_package: object | None) -> str | None:
    """The selected input field only applies when no prompt package renders the prompt."""

    if prompt_package is not None:
        return None
    return input_field.strip() if input_field and input_field.strip() else None


def _validate_distinct_dataset_fields(selected_input_field: str | None, reference_field: str) -> str:
    normalized = reference_field.strip()
    if selected_input_field is not None and selected_input_field == normalized:
        raise ConflictError("Input and reference fields must name different dataset columns.")
    return normalized


_DATASET_PROFILE_KEYS = ("capabilities", "languages", "evaluation_type")
_MISSING_PROFILE_VALUE = object()


def _dataset_profile(
    *,
    capabilities: object,
    languages: object,
    evaluation_type: object,
    input_field: str | None,
    reference_field: str,
) -> dict[str, object]:
    return {
        "capabilities": list(capabilities) if isinstance(capabilities, list) else [],
        "languages": list(languages) if isinstance(languages, list) else [],
        "evaluation_type": evaluation_type if isinstance(evaluation_type, str) else "custom",
        "input_field": input_field,
        "reference_field": reference_field,
    }


def _resolved_sample_metadata(
    fields: dict[str, object],
    dataset_profile: dict[str, object],
    *,
    source: str,
    record_number: int,
    dataset_id: str,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "source": source,
        "record_number": str(record_number),
        "dataset": dataset_id,
    }
    record_metadata = fields.get("metadata")
    nested = record_metadata if isinstance(record_metadata, dict) else {}
    for key in _DATASET_PROFILE_KEYS:
        value = nested.get(key, _MISSING_PROFILE_VALUE)
        if value is _MISSING_PROFILE_VALUE:
            value = fields.get(key, _MISSING_PROFILE_VALUE)
        metadata[key] = dataset_profile[key] if value is _MISSING_PROFILE_VALUE else value
    return metadata


def _sample_dataset_profile(sample: BenchmarkSample) -> dict[str, object]:
    return {key: sample.metadata.get(key) for key in _DATASET_PROFILE_KEYS}


def effective_dataset_scoring_rule(
    requested_rule: dict[str, object] | None,
    prompt_package: object | None,
) -> dict[str, object]:
    candidate = requested_rule
    if candidate is None and prompt_package is not None:
        candidate = getattr(prompt_package, "scoring_rule", None)
    rule = dict(candidate) if isinstance(candidate, dict) and candidate else {"type": "exact_match"}
    try:
        validate_scoring_rule(rule)
        if is_llm_judge_rule(rule):
            return normalize_judge_rule(rule)
    except ScoringError as error:
        raise ConflictError(f"Scoring rule is invalid: {error}") from error
    return rule


def _judge_endpoint_for_rule(
    repository: EvaluationRepository,
    *,
    scoring_rule: dict[str, object],
    evaluated_endpoint_id: str,
) -> Any | None:
    if not is_llm_judge_rule(scoring_rule):
        return None
    normalized = normalize_judge_rule(scoring_rule)
    record = repository.get_endpoint(str(normalized["judge_endpoint_id"]))
    endpoint = record_proxy(record) if record is not None else None
    try:
        validate_judge_endpoint(
            normalized,
            evaluated_endpoint_id=evaluated_endpoint_id,
            judge_endpoint=endpoint,
        )
    except JudgeScoringError as error:
        raise ConflictError(str(error)) from error
    return endpoint


_DATASET_RUN_MANIFEST: dict[str, object] = {
    "benchmark_id": DATASET_RUN_BENCHMARK_ID,
    "version": DATASET_RUN_BENCHMARK_VERSION,
    "display_name": "Dataset Evaluation",
    "description": "Records of a registered dataset evaluated through a prompt template.",
    "pack": "user",
    "modalities": ["text"],
    "input_modalities": ["text"],
    "output_modality": "text",
    "required_capabilities": ["text_input"],
    "recommended_capabilities": ["text_input"],
    "capability_categories": ["text_input"],
    "datasets": [],
    "license": "User-registered dataset; license state recorded on the dataset version.",
    "estimated_download_bytes": 0,
    "sample_count": 0,
    "prompt_version": "dataset/1.0.0",
    "scorer_type": "exact_match",
    "scoring": {"type": "exact_match"},
    "languages": ["en"],
    "shard_size": 50,
    "analysis_schema": {"dimensions": ["capability", "language", "difficulty", "modality"], "version": "1.0.0"},
}


def create_dataset_run(
    repository: EvaluationRepository,
    *,
    model_endpoint_id: str,
    dataset_version_id: str,
    prompt_package_id: str | None,
    reference_field: str | None,
    sample_limit: int,
    input_field: str | None = None,
    request_body_override: dict[str, object] | None = None,
    scoring_rule: dict[str, object] | None = None,
    created_by: str | None = None,
    max_concurrency: int | None = None,
    data_root: str,
) -> dict[str, Any]:
    endpoint = repository.get_endpoint(model_endpoint_id)
    if endpoint is None:
        raise NotFoundError("Model endpoint not found.")
    if endpoint.get("status") != EndpointStatus.AVAILABLE.value:
        raise ConflictError("Model endpoint must pass a connection test before scheduling a run.")
    dataset = repository.get_dataset(dataset_version_id)
    if dataset is None:
        raise NotFoundError("Dataset version not found.")
    if dataset.get("status") != DatasetStatus.READY.value or not dataset.get("prepared_path"):
        raise ConflictError(
            f"Dataset {dataset['dataset_id']} v{dataset['version']} is not ready; "
            "download and verify it before running."
        )
    prompt_package = repository.get_prompt_package(prompt_package_id) if prompt_package_id else None
    if prompt_package_id and prompt_package is None:
        raise NotFoundError("Prompt package not found.")
    prompt_proxy = record_proxy(prompt_package) if prompt_package else None
    resolved_reference_field = reference_field or dataset.get("reference_field")
    if not isinstance(resolved_reference_field, str) or not resolved_reference_field.strip():
        raise ConflictError("A reference field is required.")
    stored_input_field = dataset.get("input_field")
    resolved_input_field = (
        input_field if input_field is not None else stored_input_field if isinstance(stored_input_field, str) else None
    )
    selected_input_field = _effective_dataset_input_field(resolved_input_field, prompt_proxy)
    normalized_reference_field = _validate_distinct_dataset_fields(selected_input_field, resolved_reference_field)
    dataset_profile = _dataset_profile(
        capabilities=dataset.get("capabilities", []),
        languages=dataset.get("languages", []),
        evaluation_type=dataset.get("evaluation_type", "custom"),
        input_field=selected_input_field,
        reference_field=normalized_reference_field,
    )
    try:
        samples, skipped = _build_dataset_samples(
            prepared_path=str(dataset["prepared_path"]),
            data_root=data_root,
            sample_limit=sample_limit,
            input_field=selected_input_field,
            reference_field=normalized_reference_field,
            prompt_package=prompt_proxy,
            dataset_id=str(dataset["dataset_id"]),
            dataset_version=str(dataset["version"]),
            dataset_profile=dataset_profile,
        )
    except DatasetRecordError as error:
        raise ConflictError(str(error)) from error
    if not samples:
        raise ConflictError(
            _empty_dataset_samples_message(
                sample_limit=sample_limit,
                input_field=selected_input_field,
                reference_field=normalized_reference_field,
            )
        )
    compatibility = capability_compatibility(repository.list_capabilities(model_endpoint_id), _DATASET_RUN_MANIFEST)
    if compatibility["unsupported"]:
        raise ConflictError(
            "Model endpoint is incompatible with dataset evaluation: " + ", ".join(compatibility["unsupported"])
        )
    effective_scoring_rule = effective_dataset_scoring_rule(scoring_rule, prompt_proxy)
    judge_endpoint = _judge_endpoint_for_rule(
        repository,
        scoring_rule=effective_scoring_rule,
        evaluated_endpoint_id=model_endpoint_id,
    )
    judge_configuration = (
        judge_configuration_snapshot(
            effective_scoring_rule,
            judge_endpoint=judge_endpoint,
            reference_field=normalized_reference_field,
        )
        if judge_endpoint is not None
        else None
    )
    endpoint_proxy = record_proxy(endpoint)
    frozen_request_body = request_body_evidence(
        endpoint=endpoint_proxy,
        benchmark_manifest=_DATASET_RUN_MANIFEST,
        suite_snapshot=None,
        request_body_override=request_body_override,
    )
    frozen_datasets = [
        {
            "dataset_id": dataset["dataset_id"],
            "version": dataset["version"],
            "revision": dataset.get("revision", "default"),
            "dataset_version_id": dataset["id"],
        }
    ]
    snapshot: dict[str, Any] = {
        "benchmark": {
            "id": DATASET_RUN_BENCHMARK_ID,
            "version": DATASET_RUN_BENCHMARK_VERSION,
            "source": "user",
            "manifest": _DATASET_RUN_MANIFEST,
        },
        "endpoint": endpoint_snapshot(endpoint),
        "datasets": frozen_datasets,
        "dataset_version": {
            "id": dataset["id"],
            "dataset_id": dataset["dataset_id"],
            "version": dataset["version"],
            "revision": dataset.get("revision", "default"),
        },
        "input_field": selected_input_field,
        "reference_field": normalized_reference_field,
        "dataset_profile": dataset_profile,
        "sample_limit": sample_limit,
        "skipped_records": skipped,
        "sample_ids": [sample.sample_id for sample in samples],
        "scoring_rule": effective_scoring_rule,
        "capability_compatibility": compatibility,
        "prompt_package": prompt_snapshot(prompt_package),
        "request_body_evidence": frozen_request_body,
    }
    if judge_configuration is not None:
        snapshot["judge"] = judge_configuration
    now = datetime.now(timezone.utc)
    try:
        shards = split_samples_for_endpoint_budget(tuple(samples), _DATASET_RUN_MANIFEST, endpoint_proxy)
    except ValidationError as error:
        raise ConflictError(str(error)) from error
    tasks = [
        task_values(
            "dataset",
            task_type=TaskType.DATASET_PREPARATION.value,
            payload={"datasets": frozen_datasets, "prepared_inline": False},
            task_status=TaskStatus.PENDING.value,
            now=now,
        ),
        task_values(
            "benchmark",
            parent_key="dataset",
            task_type=TaskType.BENCHMARK.value,
            payload={
                "benchmark_id": DATASET_RUN_BENCHMARK_ID,
                "benchmark_version": DATASET_RUN_BENCHMARK_VERSION,
                "planned_samples": len(samples),
            },
            task_status=TaskStatus.PENDING.value,
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
                    "messages": build_sample_messages(sample, None),
                    "modality": "text",
                    "metadata": dict(sample.metadata),
                    "request_body_evidence": frozen_request_body,
                },
                reference_snapshot={
                    "type": str(effective_scoring_rule.get("type", "exact_match")),
                    "answer": sample.reference_answer,
                    "scoring": effective_scoring_rule,
                    "dataset_profile": _sample_dataset_profile(sample),
                    **({"judge": judge_configuration} if judge_configuration is not None else {}),
                },
                now=now,
            )
            for sample in shard_samples
        )
    return repository.create_run_graph(
        {
            "model_endpoint_id": model_endpoint_id,
            "prompt_package_id": prompt_package_id,
            "suite_id": None,
            "created_by": created_by,
            "max_concurrency": max_concurrency,
            "benchmark_id": DATASET_RUN_BENCHMARK_ID,
            "benchmark_version": DATASET_RUN_BENCHMARK_VERSION,
            "display_name": format_run_display_name(str(endpoint["model_name"]), str(dataset["dataset_id"]), now),
            "configuration_snapshot": snapshot,
            "status": RunStatus.QUEUED.value,
            "total_samples": len(samples),
            "completed_samples": 0,
            "successful_samples": 0,
            "failed_samples": 0,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "archived_at": None,
        },
        tasks,
        attempts,
    )


def preflight_dataset_run(
    repository: EvaluationRepository,
    *,
    model_endpoint_id: str,
    dataset_version_id: str,
    prompt_package_id: str | None,
    reference_field: str | None,
    sample_limit: int,
    input_field: str | None = None,
    request_body_override: dict[str, object] | None = None,
    scoring_rule: dict[str, object] | None = None,
    data_root: str,
) -> dict[str, object]:
    issues: list[str] = []
    endpoint = repository.get_endpoint(model_endpoint_id)
    if endpoint is None:
        issues.append("Model endpoint not found.")
    elif endpoint.get("status") != EndpointStatus.AVAILABLE.value:
        issues.append("Model endpoint must pass a connection test before scheduling a run.")
    dataset = repository.get_dataset(dataset_version_id)
    if dataset is None:
        issues.append("Dataset version not found.")
    elif dataset.get("status") != DatasetStatus.READY.value or not dataset.get("prepared_path"):
        issues.append(
            f"Dataset {dataset['dataset_id']} v{dataset['version']} is not ready; download and verify it first."
        )
    prompt_package = repository.get_prompt_package(prompt_package_id) if prompt_package_id else None
    if prompt_package_id and prompt_package is None:
        issues.append("Prompt package not found.")
    prompt_proxy = record_proxy(prompt_package) if prompt_package else None
    resolved_reference_field = reference_field or (dataset.get("reference_field") if dataset is not None else None)
    if not isinstance(resolved_reference_field, str) or not resolved_reference_field.strip():
        issues.append("A reference field is required.")
    stored_input_field = dataset.get("input_field") if dataset is not None else None
    resolved_input_field = (
        input_field if input_field is not None else stored_input_field if isinstance(stored_input_field, str) else None
    )
    selected_input_field = _effective_dataset_input_field(resolved_input_field, prompt_proxy)
    effective_scoring_rule: dict[str, object] | None = None
    try:
        effective_scoring_rule = effective_dataset_scoring_rule(scoring_rule, prompt_proxy)
    except ApplicationError as error:
        issues.append(str(error))
    judge_endpoint: Any | None = None
    if effective_scoring_rule is not None:
        try:
            judge_endpoint = _judge_endpoint_for_rule(
                repository,
                scoring_rule=effective_scoring_rule,
                evaluated_endpoint_id=model_endpoint_id,
            )
        except ApplicationError as error:
            issues.append(str(error))
    samples: list[BenchmarkSample] = []
    datasets: list[dict[str, object]] = []
    if dataset is not None and dataset.get("status") == "ready" and dataset.get("prepared_path"):
        datasets.append(
            {
                "id": dataset["id"],
                "dataset_id": dataset["dataset_id"],
                "version": dataset["version"],
                "revision": dataset.get("revision", "default"),
                "status": dataset["status"],
                "will_prepare": False,
            }
        )
        try:
            normalized_reference_field = _validate_distinct_dataset_fields(
                selected_input_field,
                resolved_reference_field if isinstance(resolved_reference_field, str) else "",
            )
            dataset_profile = _dataset_profile(
                capabilities=dataset.get("capabilities", []),
                languages=dataset.get("languages", []),
                evaluation_type=dataset.get("evaluation_type", "custom"),
                input_field=selected_input_field,
                reference_field=normalized_reference_field,
            )
            samples, _skipped = _build_dataset_samples(
                prepared_path=str(dataset["prepared_path"]),
                data_root=data_root,
                sample_limit=sample_limit,
                input_field=selected_input_field,
                reference_field=normalized_reference_field,
                prompt_package=prompt_proxy,
                dataset_id=str(dataset["dataset_id"]),
                dataset_version=str(dataset["version"]),
                dataset_profile=dataset_profile,
            )
            if not samples:
                issues.append(
                    _empty_dataset_samples_message(
                        sample_limit=sample_limit,
                        input_field=selected_input_field,
                        reference_field=normalized_reference_field,
                    )
                )
        except (DatasetRecordError, ApplicationError) as error:
            issues.append(str(error))
    compatibility = (
        capability_compatibility(repository.list_capabilities(model_endpoint_id), _DATASET_RUN_MANIFEST)
        if endpoint is not None and endpoint.get("status") == EndpointStatus.AVAILABLE.value
        else {"required": ["text_input"], "unsupported": [], "unverified": []}
    )
    if compatibility["unsupported"]:
        issues.append(
            "Model endpoint is incompatible with dataset evaluation: " + ", ".join(compatibility["unsupported"])
        )
    estimated_input_tokens = sum(estimate_sample_tokens(sample) for sample in samples)
    estimated_output_tokens = len(samples) * 64
    input_cost = endpoint.get("input_cost_per_million") if endpoint is not None else None
    output_cost = endpoint.get("output_cost_per_million") if endpoint is not None else None
    estimated_cost = (
        ((estimated_input_tokens * float(input_cost)) + (estimated_output_tokens * float(output_cost))) / 1_000_000
        if input_cost is not None and output_cost is not None
        else None
    )
    judge_estimate = (
        judge_preflight_estimate(
            sample_count=len(samples),
            target_input_tokens=estimated_input_tokens,
            judge_endpoint=judge_endpoint,
        )
        if judge_endpoint is not None
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
        "judge_estimate": judge_estimate,
        "compatibility": compatibility,
        "datasets": datasets,
        "request_body_evidence": (
            request_body_evidence(
                endpoint=record_proxy(endpoint),
                benchmark_manifest=_DATASET_RUN_MANIFEST,
                suite_snapshot=None,
                request_body_override=request_body_override,
            )
            if endpoint is not None
            else None
        ),
    }


def _build_dataset_samples(
    *,
    prepared_path: str,
    data_root: str,
    sample_limit: int,
    input_field: str | None,
    reference_field: str,
    prompt_package: object | None,
    dataset_id: str,
    dataset_version: str,
    dataset_profile: dict[str, object],
) -> tuple[list[BenchmarkSample], int]:
    """Materialize up to ``sample_limit`` usable records as benchmark samples.

    Records missing the reference field, or that render no prompt, are counted
    as skipped.  The prompt is fully rendered here (template applied with the
    record fields), so callers must pass ``None`` as the prompt package when
    building attempt messages to avoid double rendering.
    """

    samples: list[BenchmarkSample] = []
    skipped = 0
    for entry in iter_dataset_records(prepared_path, data_root, limit=sample_limit):
        fields = {str(key): value for key, value in entry["fields"].items()}
        reference = fields.get(reference_field)
        prompt = _render_record_prompt(fields, prompt_package, input_field)
        if reference is None or prompt is None:
            skipped += 1
            continue
        samples.append(
            BenchmarkSample(
                sample_id=f"{dataset_id}:{dataset_version}:{entry['source']}#{entry['record_number']}",
                prompt=prompt,
                reference_answer=str(reference),
                metadata=_resolved_sample_metadata(
                    fields,
                    dataset_profile,
                    source=str(entry["source"]),
                    record_number=int(entry["record_number"]),
                    dataset_id=dataset_id,
                ),
                messages=tuple(_build_record_messages(prompt_package, prompt)),
            )
        )
    return samples, skipped


def _render_record_prompt(
    fields: dict[str, object],
    prompt_package: object | None,
    input_field: str | None,
) -> str | None:
    if prompt_package is not None:
        try:
            return render_template(
                prompt_package.user_template,
                {**_FIXED_TEMPLATE_KEYS, **fields},
                extra_variables=frozenset(fields),
            )
        except PromptTemplateError as error:
            raise ConflictError(str(error)) from error
    if input_field is not None:
        value = fields.get(input_field)
        if value is None or value == "":
            return None
        return str(value)
    for value in fields.values():
        if isinstance(value, str) and value:
            return value
    return None


def _empty_dataset_samples_message(
    *,
    sample_limit: int,
    input_field: str | None,
    reference_field: str,
) -> str:
    if input_field is not None:
        return (
            f"None of the first {sample_limit} records contain usable values for "
            f"input field {input_field!r} and reference field {reference_field!r}; "
            "check the field names or register a different dataset."
        )
    return (
        f"None of the first {sample_limit} records contain the reference field {reference_field!r}; "
        "check the field name or register a different dataset."
    )


def _build_record_messages(
    prompt_package: object | None,
    rendered_prompt: str,
) -> list[dict[str, object]]:
    """Build the full attempt message list from a prompt package and record render.

    Mirrors the benchmark path: system message, few-shot examples, then the
    rendered user message.  The prompt is fully rendered here (record fields
    applied), so callers must not re-apply the package when storing attempts.
    """

    messages: list[dict[str, object]] = []
    if prompt_package is not None and prompt_package.system_message:
        messages.append({"role": "system", "content": prompt_package.system_message})
    for example in prompt_package.few_shot_examples if prompt_package is not None else []:
        if (
            isinstance(example, dict)
            and isinstance(example.get("role"), str)
            and isinstance(example.get("content"), str)
        ):
            messages.append({"role": example["role"], "content": example["content"]})
    messages.append({"role": "user", "content": rendered_prompt})
    return messages
