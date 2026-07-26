from __future__ import annotations

import base64
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
    TaskUnit,
)
from app.services.content_ir import ContentValidationError, normalize_content_parts
from app.services.media_assets import MediaAssetError, safe_asset_path


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
) -> EvaluationRun:
    endpoint = session.get(ModelEndpoint, model_endpoint_id)
    if endpoint is None:
        raise CustomRunError("Model endpoint not found.")
    if endpoint.status != EndpointStatus.AVAILABLE.value:
        raise CustomRunError("Model endpoint must pass a connection test before scheduling a run.")
    if not sample_id.strip() or not reference_answer.strip():
        raise CustomRunError("Custom samples require a sample ID and reference answer.")
    normalized_messages = _normalize_messages(session, data_root, messages)
    run = EvaluationRun(
        model_endpoint_id=endpoint.id,
        benchmark_id="custom-multimodal",
        benchmark_version="1.0.0",
        configuration_snapshot={
            "benchmark": {"id": "custom-multimodal", "version": "1.0.0", "source": "user"},
            "endpoint": {
                "id": endpoint.id,
                "model_name": endpoint.model_name,
                "protocol_profile": endpoint.protocol_profile,
            },
            "sample_ids": [sample_id],
        },
        status=RunStatus.QUEUED.value,
        total_samples=1,
    )
    session.add(run)
    session.flush()
    task = TaskUnit(
        run_id=run.id,
        task_type="evaluation_shard",
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
            input_snapshot={"messages": normalized_messages, "modality": _sample_modality(normalized_messages)},
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
    if part["type"] == "text":
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
    return {"type": part["type"], "source": {"base64_data": encoded}, "mime_type": asset.mime_type}


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
