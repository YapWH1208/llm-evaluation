from __future__ import annotations

import base64
import binascii
import ipaddress
import math
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import perf_counter
from typing import Any
from urllib.parse import urlparse

from app.core.content import ContentValidationError, normalize_content_parts


PROTECTED_REQUEST_FIELDS = frozenset(
    {
        "model",
        "messages",
        "input",
        "contents",
        "system",
        "systemInstruction",
        "stream",
        "tools",
        "response_format",
    }
)
_SENSITIVE_BODY_KEYS = frozenset(
    {"api_key", "apikey", "api-key", "token", "access_token", "auth_token", "authorization", "secret", "password"}
)
_BLOCKED_HEADERS = frozenset(
    {"authorization", "cookie", "host", "content-length", "x-api-key", "x-goog-api-key", "api-key"}
)


def is_sensitive_body_key(name: str) -> bool:
    normalized = str(name).lower().replace("_", "-").replace(" ", "-").strip("-")
    return normalized in _SENSITIVE_BODY_KEYS or normalized.endswith(("-key", "-token", "-secret"))


def validate_custom_headers(value: dict[str, Any]) -> dict[str, str]:
    if len(value) > 32:
        raise ValueError("custom_headers may contain at most 32 headers.")
    normalized: dict[str, str] = {}
    for name, header_value in value.items():
        if not isinstance(name, str) or not name.strip() or any(char in name for char in "\r\n:"):
            raise ValueError("custom_headers contains an invalid header name.")
        if name.lower() in _BLOCKED_HEADERS:
            raise ValueError(f"custom_headers cannot set protected header: {name}.")
        if not isinstance(header_value, str) or "\r" in header_value or "\n" in header_value:
            raise ValueError(f"custom_headers contains an invalid value for {name}.")
        if len(header_value) > 4096:
            raise ValueError(f"custom_headers value for {name} is too long.")
        normalized[name] = header_value
    return normalized


def allowed_defaults(defaults: Mapping[str, object]) -> dict[str, Any]:
    return {
        key: value
        for key, value in defaults.items()
        if key not in PROTECTED_REQUEST_FIELDS and not is_sensitive_body_key(key)
    }


def url_without_fragment(value: str) -> str:
    parsed = urlparse(value)
    return parsed._replace(fragment="").geturl()


def normalise_content_parts(content: object) -> list[dict[str, Any]]:
    if not isinstance(content, list):
        raise ValueError("Message content must be text or a list of content parts.")
    try:
        parts = normalize_content_parts(content)
    except ContentValidationError as error:
        raise ValueError(str(error)) from error
    if any(part["type"] == "tool_result" for part in parts):
        raise ValueError("This protocol adapter does not support tool results.")
    return parts


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
        parts = normalise_content_parts(content)
        tool_results = [part for part in parts if part["type"] == "tool_result"]
        if tool_results:
            if len(parts) != 1 or role != "tool":
                raise ValueError("Chat Completions tool results must be a standalone message with role tool.")
            translated.append({"role": "tool", "tool_call_id": tool_results[0]["tool_call_id"], "content": tool_results[0]["content"]})
            continue
        translated.append({"role": role, "content": [translate_chat_part(part) for part in parts]})
    return translated


def translate_chat_part(part: dict[str, Any]) -> dict[str, object]:
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


def translate_responses_messages(messages: list[object]) -> list[dict[str, object]]:
    translated: list[dict[str, object]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Each message must be an object.")
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant", "system", "developer"}:
            raise ValueError("Responses API messages require a user, assistant, system, or developer role.")
        if isinstance(content, str):
            parts = [{"type": "input_text", "text": content}]
            tool_results: list[dict[str, object]] = []
        else:
            try:
                normalized = normalize_content_parts(content) if isinstance(content, list) else None
            except ContentValidationError as error:
                raise ValueError(str(error)) from error
            if normalized is None:
                raise ValueError("Message content must be text or a list of content parts.")
            parts = [translate_responses_part(part) for part in normalized if part["type"] != "tool_result"]
            tool_results = [{"type": "function_call_output", "call_id": part["tool_call_id"], "output": part["content"]} for part in normalized if part["type"] == "tool_result"]
        if parts:
            translated.append({"role": role, "content": parts})
        translated.extend(tool_results)
    return translated


def translate_responses_part(part: dict[str, Any]) -> dict[str, object]:
    part_type = part["type"]
    if part_type == "text":
        return {"type": "input_text", "text": part["text"]}
    if part_type == "image":
        return {"type": "input_image", "image_url": source_as_data_or_remote_url(part)}
    if part_type == "audio":
        source = part["source"]
        encoded = source.get("base64_data") if isinstance(source, dict) else None
        if not isinstance(encoded, str):
            raise ValueError("Responses API audio content requires base64_data.")
        validate_base64(encoded)
        audio_format = part["mime_type"].split("/", 1)[1]
        if audio_format == "mpeg":
            audio_format = "mp3"
        if audio_format not in {"wav", "mp3"}:
            raise ValueError("Responses API audio supports WAV or MP3 content only.")
        return {"type": "input_audio", "input_audio": {"data": encoded, "format": audio_format}}
    if part_type in {"file", "video"}:
        source = part["source"]
        if not isinstance(source, dict):
            raise ValueError("File and video content parts require a source object.")
        filename = "input-video" if part_type == "video" else "input-file"
        if isinstance(source.get("url"), str):
            validate_remote_media_url(source["url"])
            return {"type": "input_file", "file_url": source["url"], "filename": filename}
        if isinstance(source.get("base64_data"), str):
            validate_base64(source["base64_data"])
            return {"type": "input_file", "file_data": source["base64_data"], "filename": filename}
        raise ValueError("Responses API file and video content requires base64_data or a remote URL.")
    raise ValueError(f"Responses API does not support {part_type} content through this adapter.")


def translate_anthropic_messages(messages: list[object]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    system_parts: list[dict[str, object]] = []
    translated: list[dict[str, object]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Each message must be an object.")
        role = message.get("role")
        content = translate_anthropic_content(message.get("content"))
        if role in {"system", "developer"}:
            system_parts.extend(content)
        elif role in {"user", "assistant"}:
            translated.append({"role": role, "content": content})
        else:
            raise ValueError("Anthropic Messages supports system, user, and assistant messages only.")
    return translated, system_parts


def translate_anthropic_content(content: object) -> list[dict[str, object]]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    translated: list[dict[str, object]] = []
    for part in normalise_content_parts(content):
        if part["type"] == "text":
            translated.append({"type": "text", "text": part["text"]})
        elif part["type"] == "image":
            source = part["source"]
            if not isinstance(source, dict):
                raise ValueError("Anthropic image content requires a source object.")
            if isinstance(source.get("base64_data"), str):
                validate_base64(source["base64_data"])
                translated.append({"type": "image", "source": {"type": "base64", "media_type": part["mime_type"], "data": source["base64_data"]}})
            elif isinstance(source.get("url"), str):
                validate_remote_media_url(source["url"])
                translated.append({"type": "image", "source": {"type": "url", "url": source["url"]}})
            else:
                raise ValueError("Anthropic image content requires base64_data or a remote URL.")
        else:
            raise ValueError(f"Anthropic Messages does not support {part['type']} content through this adapter.")
    return translated


def translate_gemini_messages(messages: list[object]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    contents: list[dict[str, object]] = []
    system_parts: list[dict[str, object]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Each message must be an object.")
        role = message.get("role")
        parts = translate_gemini_content(message.get("content"))
        if role in {"system", "developer"}:
            system_parts.extend(parts)
        elif role == "assistant":
            contents.append({"role": "model", "parts": parts})
        elif role == "user":
            contents.append({"role": "user", "parts": parts})
        else:
            raise ValueError("Gemini GenerateContent supports system, user, and assistant messages only.")
    return contents, system_parts


def translate_gemini_content(content: object) -> list[dict[str, object]]:
    if isinstance(content, str):
        return [{"text": content}]
    translated: list[dict[str, object]] = []
    for part in normalise_content_parts(content):
        if part["type"] == "text":
            translated.append({"text": part["text"]})
            continue
        source = part["source"]
        encoded = source.get("base64_data") if isinstance(source, dict) else None
        if not isinstance(encoded, str):
            raise ValueError(f"Gemini {part['type']} content requires base64_data through this adapter.")
        validate_base64(encoded)
        translated.append({"inlineData": {"mimeType": part["mime_type"], "data": encoded}})
    return translated


def translate_ollama_messages(messages: list[object]) -> list[dict[str, object]]:
    translated: list[dict[str, object]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Each message must be an object.")
        role = message.get("role")
        if role not in {"system", "user", "assistant"}:
            raise ValueError("Ollama Chat supports system, user, and assistant messages only.")
        content = message.get("content")
        if isinstance(content, str):
            translated.append({"role": role, "content": content})
            continue
        parts = normalise_content_parts(content)
        text = "".join(part["text"] for part in parts if part["type"] == "text")
        images: list[str] = []
        for part in parts:
            if part["type"] == "text":
                continue
            if part["type"] != "image":
                raise ValueError(f"Ollama Chat does not support {part['type']} content through this adapter.")
            source = part["source"]
            encoded = source.get("base64_data") if isinstance(source, dict) else None
            if not isinstance(encoded, str):
                raise ValueError("Ollama image content requires base64_data through this adapter.")
            validate_base64(encoded)
            images.append(encoded)
        rendered: dict[str, object] = {"role": role, "content": text}
        if images:
            rendered["images"] = images
        translated.append(rendered)
    return translated


def source_as_data_or_remote_url(part: dict[str, Any]) -> str:
    source = part["source"]
    if not isinstance(source, dict):
        raise ValueError("Media content parts require a source object.")
    remote_url = source.get("url")
    if isinstance(remote_url, str):
        validate_remote_media_url(remote_url)
        return remote_url
    encoded = source.get("base64_data")
    if isinstance(encoded, str):
        validate_base64(encoded)
        return f"data:{part['mime_type']};base64,{encoded}"
    if source.get("asset_id"):
        raise ValueError("Stored media assets must be resolved to base64_data or a remote URL before execution.")
    raise ValueError("Media content part has no usable provider source.")


def validate_base64(value: str) -> None:
    try:
        base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("Media base64_data must be valid base64.") from error


def validate_remote_media_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Remote media URLs must be absolute HTTP or HTTPS URLs.")
    host = parsed.hostname
    if host is None:
        raise ValueError("Remote media URL host is missing.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
        raise ValueError("Remote media URLs must not target private or local IP addresses.")


def extract_prediction(payload: dict[str, Any], profile: str) -> str:
    if profile in {"openai_chat_completions", "azure_openai_chat_completions"}:
        prediction = payload["choices"][0]["message"]["content"]
    elif profile == "openai_responses":
        output_text = payload.get("output_text")
        if isinstance(output_text, str):
            return output_text
        fragments = [
            part["text"]
            for item in payload.get("output", [])
            if isinstance(item, dict) and item.get("type") == "message"
            for part in item.get("content", [])
            if isinstance(part, dict) and part.get("type") == "output_text" and isinstance(part.get("text"), str)
        ]
        if fragments:
            return "".join(fragments)
        raise ValueError("Responses API response did not contain output text.")
    elif profile == "anthropic_messages":
        prediction = "".join(part["text"] for part in payload.get("content", []) if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str))
    elif profile == "gemini_generate_content":
        candidates = payload.get("candidates")
        first = candidates[0] if isinstance(candidates, list) and candidates else {}
        prediction = "".join(part["text"] for part in first.get("content", {}).get("parts", []) if isinstance(part, dict) and isinstance(part.get("text"), str)) if isinstance(first, dict) else ""
    elif profile == "ollama_chat":
        prediction = payload.get("message", {}).get("content") if isinstance(payload.get("message"), dict) else None
    else:
        prediction = next((payload.get(key) for key in ("output_text", "text", "response", "prediction") if isinstance(payload.get(key), str)), None)
        if prediction is None:
            choices = payload.get("choices")
            first = choices[0] if isinstance(choices, list) and choices else {}
            message = first.get("message") if isinstance(first, dict) else None
            prediction = message.get("content") if isinstance(message, dict) else None
    if not isinstance(prediction, str) or not prediction:
        raise ValueError("Provider response did not contain text content.")
    return prediction


def extract_usage(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    usage = payload.get("usage")
    if isinstance(usage, dict):
        return nonnegative_int(usage.get("prompt_tokens", usage.get("input_tokens"))), nonnegative_int(usage.get("completion_tokens", usage.get("output_tokens")))
    usage_metadata = payload.get("usageMetadata")
    if isinstance(usage_metadata, dict):
        return nonnegative_int(usage_metadata.get("promptTokenCount")), nonnegative_int(usage_metadata.get("candidatesTokenCount"))
    return nonnegative_int(payload.get("prompt_eval_count")), nonnegative_int(payload.get("eval_count"))


def extract_token_logprobs(payload: dict[str, Any], profile: str) -> tuple[float, ...] | None:
    candidates: object = None
    if profile in {"openai_chat_completions", "azure_openai_chat_completions"}:
        choices = payload.get("choices")
        first = choices[0] if isinstance(choices, list) and choices else None
        logprobs = first.get("logprobs") if isinstance(first, dict) else None
        candidates = logprobs.get("content") if isinstance(logprobs, dict) else None
    elif profile == "ollama_chat":
        candidates = payload.get("logprobs")
    if not isinstance(candidates, list) or not candidates:
        return None
    values: list[float] = []
    for candidate in candidates:
        value = candidate.get("logprob") if isinstance(candidate, dict) else None
        if not isinstance(value, int | float) or isinstance(value, bool):
            return None
        parsed = float(value)
        if not math.isfinite(parsed) or parsed > 0:
            return None
        values.append(parsed)
    return tuple(values)


def nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def parse_retry_after(value: str | None, now: datetime | None = None) -> float | None:
    if not value:
        return None
    try:
        delay = float(value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        delay = (retry_at - (now or datetime.now(timezone.utc))).total_seconds()
    return max(0.0, delay)


def elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)


def adapter_defaults(protocol_profile: str) -> dict[str, object]:
    if protocol_profile == "openai_responses":
        return {"max_output_tokens": 32, "store": False}
    if protocol_profile == "gemini_generate_content":
        return {"max_output_tokens": 32, "temperature": 0}
    if protocol_profile == "ollama_chat":
        return {"max_tokens": 32, "temperature": 0}
    return {"max_tokens": 32, "temperature": 0}


def resolve_request_body(
    *,
    protocol_profile: str,
    model_defaults: Mapping[str, object] | None,
    suite_defaults: Mapping[str, object] | None = None,
    benchmark_defaults: Mapping[str, object] | None = None,
    run_override: Mapping[str, object] | None = None,
    benchmark_forced: Mapping[str, object] | None = None,
) -> dict[str, object]:
    layers: tuple[tuple[str, Mapping[str, object] | None], ...] = (
        ("adapter_defaults", adapter_defaults(protocol_profile)),
        ("model_defaults", model_defaults),
        ("suite_defaults", suite_defaults),
        ("benchmark_defaults", benchmark_defaults),
        ("run_override", run_override),
        ("benchmark_forced", benchmark_forced),
    )
    effective: dict[str, object] = {}
    provenance: dict[str, str] = {}
    overridden_fields: list[dict[str, object]] = []
    ignored_fields: list[dict[str, object]] = []
    snapshots: dict[str, dict[str, object]] = {}
    for layer_name, raw_layer in layers:
        safe_layer = _normalise_layer(raw_layer, layer_name, ignored_fields)
        snapshots[layer_name] = deepcopy(safe_layer)
        _deep_merge(effective, safe_layer, layer_name, provenance, overridden_fields)
    return {"protocol_profile": protocol_profile, "layers": snapshots, "effective_request_body": effective, "overridden_fields": overridden_fields, "ignored_fields": ignored_fields}


def effective_request_options(input_snapshot: Mapping[str, object], *, protocol_profile: str, model_defaults: Mapping[str, object] | None) -> dict[str, object]:
    evidence = input_snapshot.get("request_body_evidence")
    if isinstance(evidence, Mapping) and isinstance(evidence.get("effective_request_body"), Mapping):
        return deepcopy(dict(evidence["effective_request_body"]))
    return dict(resolve_request_body(protocol_profile=protocol_profile, model_defaults=model_defaults)["effective_request_body"])


def request_snapshot_metadata(input_snapshot: Mapping[str, object]) -> dict[str, object] | None:
    evidence = input_snapshot.get("request_body_evidence")
    return deepcopy(dict(evidence)) if isinstance(evidence, Mapping) else None


def _normalise_layer(value: Mapping[str, object] | None, layer_name: str, ignored_fields: list[dict[str, object]]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    safe: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            ignored_fields.append({"layer": layer_name, "field": str(key), "reason": "field names must be strings"})
            continue
        if key in PROTECTED_REQUEST_FIELDS:
            ignored_fields.append({"layer": layer_name, "field": key, "reason": "platform-controlled request field"})
            continue
        safe[key] = deepcopy(item)
    return safe


def _deep_merge(target: dict[str, object], incoming: Mapping[str, object], layer_name: str, provenance: dict[str, str], overridden_fields: list[dict[str, object]], prefix: str = "") -> None:
    for key, value in incoming.items():
        field_path = f"{prefix}.{key}" if prefix else str(key)
        existing = target.get(key)
        if isinstance(existing, dict) and isinstance(value, Mapping):
            _deep_merge(existing, value, layer_name, provenance, overridden_fields, field_path)
            continue
        if key in target and target[key] != value:
            overridden_fields.append({"field": field_path, "previous_layer": provenance.get(field_path), "new_layer": layer_name})
        target[key] = deepcopy(value)
        provenance[field_path] = layer_name
