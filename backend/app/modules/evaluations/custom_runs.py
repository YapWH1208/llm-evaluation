from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    EndpointStatus,
    EvaluationRun,
    MediaAsset,
    ModelEndpoint,
    RunStatus,
    SampleAttempt,
    TaskStatus,
    TaskType,
    TaskUnit,
)
from app.core.content import ContentValidationError, normalize_content_parts
from app.modules.reports.assets import MediaAssetError, safe_asset_path
from app.infrastructure.providers.common import resolve_request_body
from app.modules.evaluations.names import format_run_display_name


class CustomRunError(ValueError):
    pass


def create_custom_multimodal_run(
    session: Session,
    *,
    data_root: str,
    model_endpoint_id: str,
    sample_id: str,
    messages: list[dict[str, Any]],
    reference_answer: str,
    created_by: str | None = None,
    max_concurrency: int | None = None,
) -> EvaluationRun:
    endpoint = session.get(ModelEndpoint, model_endpoint_id)
    if endpoint is None:
        raise CustomRunError("Model endpoint not found.")
    if endpoint.status != EndpointStatus.AVAILABLE.value:
        raise CustomRunError("Model endpoint must pass a connection test before scheduling a run.")
    if not sample_id.strip() or not reference_answer.strip():
        raise CustomRunError("Custom samples require a sample ID and reference answer.")
    normalized_messages = _normalize_messages(session, data_root, messages)
    request_body_evidence = resolve_request_body(
        protocol_profile=str(endpoint.protocol_profile),
        model_defaults=endpoint.default_request_body,
    )
    created_at = datetime.now(timezone.utc)
    run = EvaluationRun(
        model_endpoint_id=endpoint.id,
        created_by=created_by,
        max_concurrency=max_concurrency,
        benchmark_id="custom-multimodal",
        benchmark_version="1.0.0",
        display_name=format_run_display_name(endpoint.model_name, "custom-multimodal", created_at),
        created_at=created_at,
        configuration_snapshot={
            "benchmark": {"id": "custom-multimodal", "version": "1.0.0", "source": "user"},
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
            "sample_ids": [sample_id],
            "request_body_evidence": request_body_evidence,
        },
        status=RunStatus.QUEUED.value,
        total_samples=1,
    )
    session.add(run)
    session.flush()
    dataset_task = TaskUnit(
        run_id=run.id,
        task_type=TaskType.DATASET_PREPARATION.value,
        payload={"source": "user", "prepared_inline": True},
        status=TaskStatus.SUCCEEDED.value,
    )
    session.add(dataset_task)
    session.flush()
    benchmark_task = TaskUnit(
        run_id=run.id,
        parent_task_id=dataset_task.id,
        task_type=TaskType.BENCHMARK.value,
        payload={"benchmark_id": "custom-multimodal", "benchmark_version": "1.0.0", "planned_samples": 1},
        status=TaskStatus.SUCCEEDED.value,
    )
    session.add(benchmark_task)
    session.flush()
    task = TaskUnit(
        run_id=run.id,
        parent_task_id=benchmark_task.id,
        task_type=TaskType.EVALUATION_SHARD.value,
        payload={
            "sample_ids": [sample_id],
            "estimated_request_count": 1,
            "estimated_token_count": _estimate_message_tokens(normalized_messages),
            "retry_policy": {"max_attempts": 3, "base_delay_seconds": 2, "max_delay_seconds": 60},
        },
        status=TaskStatus.PENDING.value,
    )
    session.add(task)
    session.flush()
    session.add(
        SampleAttempt(
            run_id=run.id,
            task_id=task.id,
            sample_id=sample_id.strip(),
            input_snapshot={"messages": normalized_messages, "modality": _sample_modality(normalized_messages), "request_body_evidence": request_body_evidence},
            reference_snapshot={"type": "exact_match", "answer": reference_answer},
        )
    )
    session.commit()
    session.refresh(run)
    return run


def _normalize_messages(
    session: Session,
    data_root: str,
    messages: list[dict[str, Any]],
) -> list[dict[str, object]]:
    if not messages:
        raise CustomRunError("Custom samples require at least one message.")
    normalized_messages: list[dict[str, object]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if not isinstance(role, str) or not role:
            raise CustomRunError("Each message requires a role.")
        if isinstance(content, str) and content:
            normalized_messages.append({"role": role, "content": content})
            continue
        if not isinstance(content, list):
            raise CustomRunError("Message content must be text or a content-part list.")
        try:
            parts = normalize_content_parts(content)
        except ContentValidationError as error:
            raise CustomRunError(str(error)) from error
        normalized_messages.append(
            {"role": role, "content": [_resolve_asset_source(session, data_root, part) for part in parts]}
        )
    return normalized_messages


def _resolve_asset_source(
    session: Session,
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
        raise CustomRunError("Media asset ID must be a string.")
    asset = session.get(MediaAsset, asset_id)
    if asset is None:
        raise CustomRunError("Referenced media asset was not found.")
    try:
        path = safe_asset_path(data_root, asset.storage_path)
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    except MediaAssetError as error:
        raise CustomRunError(str(error)) from error
    return {
        "type": part["type"],
        "source": {"asset_id": asset.id, "base64_data": encoded},
        "mime_type": asset.mime_type,
    }


def _sample_modality(messages: list[dict[str, object]]) -> str:
    media_types = {
        part["type"]
        for message in messages
        if isinstance(message.get("content"), list)
        for part in message["content"]
        if isinstance(part, dict) and part.get("type") != "text"
    }
    return "+".join(sorted(media_types | {"text"}))


def _estimate_message_tokens(messages: list[dict[str, object]]) -> int:
    text_length = sum(
        len(content)
        for message in messages
        if isinstance((content := message.get("content")), str)
    )
    return max(32, (text_length + 3) // 4 + 32)
