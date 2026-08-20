from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime
import json
from types import SimpleNamespace
from typing import Any

from app.core.errors import ValidationError
from app.db.models import ModelEndpoint, PromptPackage, SampleAttemptStatus
from app.infrastructure.providers.common import resolve_request_body
from app.modules.benchmarks.prompts import PromptTemplateError, render_template


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
        raise ValidationError(str(error)) from error
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


def _estimate_retry_attempt_tokens(attempt: object) -> int:
    """Recover a conservative admission estimate from durable attempt evidence."""

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
                    raise ValidationError("A benchmark sample exceeds the configured endpoint request or token budget.")
                shards.append(tuple(current))
                current = []
                current_tokens = 0
                if not _fits_endpoint_budget(endpoint, 1, estimate):
                    raise ValidationError("A benchmark sample exceeds the configured endpoint request or token budget.")
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
