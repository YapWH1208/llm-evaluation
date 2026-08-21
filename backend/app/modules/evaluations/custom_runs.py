from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any

from app.core.content import ContentValidationError, normalize_content_parts
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.endpoints.models import EndpointStatus
from app.modules.evaluations.models import RunStatus, TaskStatus, TaskType
from app.infrastructure.providers.common import resolve_request_body
from app.modules.evaluations.names import format_run_display_name
from app.modules.evaluations.ports import EvaluationRepository
from app.modules.evaluations.planning import attempt_values, endpoint_snapshot, task_values
from app.modules.reports.assets import MediaAssetError, safe_asset_path


def create_custom_multimodal_run(
    repository: EvaluationRepository,
    *,
    data_root: str,
    model_endpoint_id: str,
    sample_id: str,
    messages: list[dict[str, Any]],
    reference_answer: str,
    created_by: str | None = None,
    max_concurrency: int | None = None,
) -> dict[str, Any]:
    endpoint = repository.get_endpoint(model_endpoint_id)
    if endpoint is None:
        raise NotFoundError("Model endpoint not found", context={"endpoint_id": model_endpoint_id})
    if endpoint.get("status") != EndpointStatus.AVAILABLE.value:
        raise ConflictError("Model endpoint must pass a connection test before scheduling a run.")

    normalized_sample_id = sample_id.strip()
    normalized_reference = reference_answer.strip()
    if not normalized_sample_id or not normalized_reference:
        raise ValidationError("Custom samples require a sample ID and reference answer.")

    normalized_messages = _normalize_messages(repository, data_root, messages)
    request_body_evidence = resolve_request_body(
        protocol_profile=str(endpoint.get("protocol_profile", "openai_chat_completions")),
        model_defaults=(
            endpoint.get("default_request_body") if isinstance(endpoint.get("default_request_body"), dict) else None
        ),
    )
    now = datetime.now(timezone.utc)
    run_values = {
        "model_endpoint_id": model_endpoint_id,
        "prompt_package_id": None,
        "suite_id": None,
        "created_by": created_by,
        "max_concurrency": max_concurrency,
        "benchmark_id": "custom-multimodal",
        "benchmark_version": "1.0.0",
        "display_name": format_run_display_name(str(endpoint["model_name"]), "custom-multimodal", now),
        "configuration_snapshot": {
            "benchmark": {"id": "custom-multimodal", "version": "1.0.0", "source": "user"},
            "endpoint": endpoint_snapshot(endpoint),
            "sample_ids": [normalized_sample_id],
            "request_body_evidence": request_body_evidence,
        },
        "status": RunStatus.QUEUED.value,
        "total_samples": 1,
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
            payload={"source": "user", "prepared_inline": True},
            task_status=TaskStatus.SUCCEEDED.value,
            now=now,
        ),
        task_values(
            "benchmark",
            parent_key="dataset",
            task_type=TaskType.BENCHMARK.value,
            payload={
                "benchmark_id": "custom-multimodal",
                "benchmark_version": "1.0.0",
                "planned_samples": 1,
            },
            task_status=TaskStatus.SUCCEEDED.value,
            now=now,
        ),
        task_values(
            "shard-0",
            parent_key="benchmark",
            task_type=TaskType.EVALUATION_SHARD.value,
            payload={
                "sample_ids": [normalized_sample_id],
                "estimated_request_count": 1,
                "estimated_token_count": _estimate_message_tokens(normalized_messages),
                "retry_policy": {"max_attempts": 3, "base_delay_seconds": 2, "max_delay_seconds": 60},
            },
            task_status=TaskStatus.PENDING.value,
            now=now,
        ),
    ]
    attempts = [
        attempt_values(
            "shard-0",
            sample_id=normalized_sample_id,
            input_snapshot={
                "messages": normalized_messages,
                "modality": sample_modality(normalized_messages),
                "metadata": {"capability": "custom", "language": "unknown", "difficulty": "custom"},
                "request_body_evidence": request_body_evidence,
            },
            reference_snapshot={"type": "exact_match", "answer": normalized_reference},
            now=now,
        )
    ]
    return repository.create_run_graph(run_values, tasks, attempts)


def _normalize_messages(
    repository: EvaluationRepository,
    data_root: str,
    messages: list[dict[str, Any]],
) -> list[dict[str, object]]:
    if not messages:
        raise ValidationError("Custom samples require at least one message.")
    normalized_messages: list[dict[str, object]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if not isinstance(role, str) or not role:
            raise ValidationError("Each message requires a role.")
        if isinstance(content, str) and content:
            normalized_messages.append({"role": role, "content": content})
            continue
        if not isinstance(content, list):
            raise ValidationError("Message content must be text or a content-part list.")
        try:
            parts = normalize_content_parts(content)
        except ContentValidationError as error:
            raise ValidationError(str(error)) from error
        normalized_messages.append(
            {
                "role": role,
                "content": [_resolve_asset_source(repository, data_root, part) for part in parts],
            }
        )
    return normalized_messages


def _resolve_asset_source(
    repository: EvaluationRepository,
    data_root: str,
    part: dict[str, Any],
) -> dict[str, object]:
    if part["type"] in {"text", "tool_result"}:
        return part
    source = part["source"]
    if not isinstance(source, dict) or not source.get("asset_id"):
        return part
    asset_id = source["asset_id"]
    if not isinstance(asset_id, str):
        raise ValidationError("Media asset ID must be a string.")
    asset = repository.get_media_asset(asset_id)
    if asset is None:
        raise NotFoundError("Referenced media asset was not found", context={"asset_id": asset_id})
    try:
        path = safe_asset_path(data_root, str(asset["storage_path"]))
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    except MediaAssetError as error:
        raise ValidationError(str(error)) from error
    return {
        "type": part["type"],
        "source": {"asset_id": asset_id, "base64_data": encoded},
        "mime_type": str(asset["mime_type"]),
    }


def sample_modality(messages: list[dict[str, object]]) -> str:
    media_types = {
        part["type"]
        for message in messages
        if isinstance(message.get("content"), list)
        for part in message["content"]
        if isinstance(part, dict) and part.get("type") != "text"
    }
    return "+".join(sorted(media_types | {"text"}))


def _estimate_message_tokens(messages: list[dict[str, object]]) -> int:
    text_length = sum(len(content) for message in messages if isinstance((content := message.get("content")), str))
    return max(32, (text_length + 3) // 4 + 32)
