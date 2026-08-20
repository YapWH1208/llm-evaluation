from __future__ import annotations

from typing import Any

from app.core.content import ContentValidationError, normalize_content_parts
from app.infrastructure.providers.common import source_as_data_or_remote_url, validate_base64


def translate_chat_messages(messages: list[object]) -> list[dict[str, object]]:
    translated: list[dict[str, object]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Each message must be an object.")
        role = message.get("role")
        content = message.get("content")
        if not isinstance(role, str) or not role:
            raise ValueError("Each message must include a role.")
        if isinstance(content, str):
            translated.append({"role": role, "content": content})
            continue
        parts = _normalize_content_parts(content)
        tool_results = [part for part in parts if part["type"] == "tool_result"]
        if tool_results:
            if len(parts) != 1 or role != "tool":
                raise ValueError("Chat Completions tool results must be a standalone message with role tool.")
            translated.append(
                {"role": "tool", "tool_call_id": tool_results[0]["tool_call_id"], "content": tool_results[0]["content"]}
            )
            continue
        translated.append({"role": role, "content": [_translate_chat_part(part) for part in parts]})
    return translated


def _normalize_content_parts(content: object) -> list[dict[str, Any]]:
    if not isinstance(content, list):
        raise ValueError("Message content must be text or a list of content parts.")
    try:
        return normalize_content_parts(content)
    except ContentValidationError as error:
        raise ValueError(str(error)) from error


def _translate_chat_part(part: dict[str, Any]) -> dict[str, object]:
    part_type = part["type"]
    if part_type == "text":
        return {"type": "text", "text": part["text"]}
    if part_type == "image":
        return {"type": "image_url", "image_url": {"url": source_as_data_or_remote_url(part)}}
    if part_type == "audio":
        source = part["source"]
        encoded = source.get("base64_data") if isinstance(source, dict) else None
        if not isinstance(encoded, str):
            raise ValueError("OpenAI Chat Completions audio content requires base64_data.")
        validate_base64(encoded)
        audio_format = part["mime_type"].split("/", 1)[1]
        if audio_format == "mpeg":
            audio_format = "mp3"
        if audio_format not in {"wav", "mp3"}:
            raise ValueError("OpenAI Chat Completions audio supports WAV or MP3 content only.")
        return {"type": "input_audio", "input_audio": {"data": encoded, "format": audio_format}}
    raise ValueError(
        f"OpenAI Chat Completions does not support {part_type} content through this adapter. "
        "Use a compatible protocol adapter for video or file inputs."
    )
