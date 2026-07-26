from __future__ import annotations

import base64
import binascii
import ipaddress
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import perf_counter
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from app.db import ModelEndpoint
from app.services.connection_tester import PROTECTED_REQUEST_FIELDS
from app.services.content_ir import ContentValidationError, normalize_content_parts
from app.services.provider_headers import provider_headers
from app.services.request_body import effective_request_options, request_snapshot_metadata


@dataclass(frozen=True, slots=True)
class SampleExecutionResult:
    success: bool
    request_snapshot: dict[str, Any]
    raw_response: str | None
    prediction: str | None
    error_type: str | None = None
    error_message: str | None = None
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    retry_after_seconds: float | None = None


class ModelExecutor(Protocol):
    def execute(
        self,
        endpoint: ModelEndpoint,
        api_key: str,
        input_snapshot: dict[str, object],
    ) -> SampleExecutionResult: ...


class OpenAIChatCompletionsExecutor:
    """Executes one sample through an OpenAI-compatible Chat or Responses endpoint."""

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport

    def execute(
        self,
        endpoint: ModelEndpoint,
        api_key: str,
        input_snapshot: dict[str, object],
    ) -> SampleExecutionResult:
        started_at = perf_counter()
        try:
            outbound_request = self._build_request(endpoint, input_snapshot)
            request_snapshot = _snapshot_with_request_evidence(outbound_request, input_snapshot)
        except ValueError as error:
            return SampleExecutionResult(
                False,
                {},
                None,
                None,
                "invalid_sample",
                str(error),
                latency_ms=_elapsed_ms(started_at),
            )
        try:
            with httpx.Client(
                timeout=endpoint.timeout_seconds,
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                response = client.post(
                    _endpoint_url(endpoint),
                    headers=provider_headers(endpoint, api_key),
                    json=outbound_request,
                )
        except httpx.TimeoutException:
            return SampleExecutionResult(
                False,
                request_snapshot,
                None,
                None,
                "timeout",
                "Provider request timed out.",
                latency_ms=_elapsed_ms(started_at),
            )
        except httpx.RequestError:
            return SampleExecutionResult(
                False,
                request_snapshot,
                None,
                None,
                "connection_error",
                "Could not connect to the provider.",
                latency_ms=_elapsed_ms(started_at),
            )

        raw_response = response.text
        if response.is_error:
            return SampleExecutionResult(
                False,
                request_snapshot,
                raw_response,
                None,
                f"http_{response.status_code}",
                f"Provider returned HTTP {response.status_code}.",
                latency_ms=_elapsed_ms(started_at),
                retry_after_seconds=_parse_retry_after(response.headers.get("retry-after")),
            )

        try:
            payload = response.json()
            prediction = _extract_prediction(payload, _protocol_profile(endpoint))
            input_tokens, output_tokens = _extract_usage(payload)
        except (IndexError, KeyError, TypeError, ValueError):
            return SampleExecutionResult(
                False,
                request_snapshot,
                raw_response,
                None,
                "response_parse_error",
                "Provider returned an unexpected response payload.",
                latency_ms=_elapsed_ms(started_at),
            )

        if not isinstance(prediction, str):
            return SampleExecutionResult(
                False,
                request_snapshot,
                raw_response,
                None,
                "response_parse_error",
                "Provider response did not contain text content.",
                latency_ms=_elapsed_ms(started_at),
            )

        return SampleExecutionResult(
            True,
            request_snapshot,
            raw_response,
            prediction,
            latency_ms=_elapsed_ms(started_at),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    @staticmethod
    def _build_request(
        endpoint: ModelEndpoint,
        input_snapshot: dict[str, object],
    ) -> dict[str, Any]:
        messages = input_snapshot.get("messages")
        if not isinstance(messages, list):
            raise ValueError("Text sample input must contain a messages list.")
        protocol_profile = _protocol_profile(endpoint)
        request_options = effective_request_options(
            input_snapshot,
            protocol_profile=protocol_profile,
            model_defaults=endpoint.default_request_body,
        )
        if protocol_profile == "openai_chat_completions":
            return _build_chat_request(endpoint, messages, request_options)
        if protocol_profile == "openai_responses":
            return _build_responses_request(endpoint, messages, request_options)
        raise ValueError(f"Unsupported execution protocol profile: {protocol_profile}.")

def _protocol_profile(endpoint: ModelEndpoint) -> str:
    return str(getattr(endpoint, "protocol_profile", None) or "openai_chat_completions")


def _endpoint_url(endpoint: ModelEndpoint) -> str:
    suffix = "/responses" if _protocol_profile(endpoint) == "openai_responses" else "/chat/completions"
    return f"{endpoint.base_url}{suffix}"


def _allowed_defaults(defaults: dict[str, object]) -> dict[str, Any]:
    return {
        key: value
        for key, value in defaults.items()
        if key not in PROTECTED_REQUEST_FIELDS
    }


def _build_chat_request(
    endpoint: ModelEndpoint,
    messages: list[object],
    request_options: dict[str, object],
) -> dict[str, Any]:
    return {
        **_allowed_defaults(request_options),
        "model": endpoint.model_name,
        "messages": _translate_messages(messages),
        "stream": False,
    }


def _build_responses_request(
    endpoint: ModelEndpoint,
    messages: list[object],
    request_options: dict[str, object],
) -> dict[str, Any]:
    return {
        **_allowed_defaults(request_options),
        "model": endpoint.model_name,
        "input": _translate_responses_messages(messages),
        "stream": False,
        "store": False,
    }


def _snapshot_with_request_evidence(
    outbound_request: dict[str, Any],
    input_snapshot: dict[str, object],
) -> dict[str, Any]:
    """Persist provider request and locally generated merge evidence separately."""

    snapshot = dict(outbound_request)
    evidence = request_snapshot_metadata(input_snapshot)
    if evidence is not None:
        snapshot["_evaluation"] = {"request_body_evidence": evidence}
    return snapshot


def _extract_prediction(payload: dict[str, Any], protocol_profile: str) -> str:
    if protocol_profile == "openai_chat_completions":
        prediction = payload["choices"][0]["message"]["content"]
        if not isinstance(prediction, str):
            raise ValueError("Chat Completions response did not contain text content.")
        return prediction
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return output_text
    fragments: list[str] = []
    output = payload.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, dict) and part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    fragments.append(part["text"])
    if not fragments:
        raise ValueError("Responses API response did not contain output text.")
    return "".join(fragments)


def _translate_responses_messages(messages: list[object]) -> list[dict[str, object]]:
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
        elif isinstance(content, list):
            try:
                normalized = normalize_content_parts(content)
            except ContentValidationError as error:
                raise ValueError(str(error)) from error
            parts = [_translate_responses_content_part(part) for part in normalized if part["type"] != "tool_result"]
            tool_results = [{"type": "function_call_output", "call_id": part["tool_call_id"], "output": part["content"]} for part in normalized if part["type"] == "tool_result"]
        else:
            raise ValueError("Message content must be text or a list of content parts.")
        if parts:
            translated.append({"role": role, "content": parts})
        translated.extend(tool_results)
    return translated


def _translate_responses_content_part(part: dict[str, Any]) -> dict[str, object]:
    part_type = part["type"]
    if part_type == "text":
        return {"type": "input_text", "text": part["text"]}
    if part_type == "image":
        return {"type": "input_image", "image_url": _source_as_data_or_remote_url(part)}
    if part_type == "audio":
        source = part["source"]
        encoded = source.get("base64_data") if isinstance(source, dict) else None
        if not isinstance(encoded, str):
            raise ValueError("Responses API audio content requires base64_data.")
        _validate_base64(encoded)
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
            _validate_remote_media_url(source["url"])
            return {"type": "input_file", "file_url": source["url"], "filename": filename}
        if isinstance(source.get("base64_data"), str):
            _validate_base64(source["base64_data"])
            return {"type": "input_file", "file_data": source["base64_data"], "filename": filename}
        raise ValueError("Responses API file and video content requires base64_data or a remote URL.")
    raise ValueError(f"Responses API does not support {part_type} content through this adapter.")


def normalize_exact_match(value: str) -> str:
    return " ".join(value.strip().split())


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)


def _extract_usage(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None, None
    input_value = usage.get("prompt_tokens", usage.get("input_tokens"))
    output_value = usage.get("completion_tokens", usage.get("output_tokens"))
    return _nonnegative_int(input_value), _nonnegative_int(output_value)


def _nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _parse_retry_after(value: str | None, now: datetime | None = None) -> float | None:
    """Return a non-negative Retry-After delay from a provider response header."""

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


def _translate_messages(messages: list[object]) -> list[dict[str, object]]:
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
        if not isinstance(content, list):
            raise ValueError("Message content must be text or a list of content parts.")
        try:
            parts = normalize_content_parts(content)
        except ContentValidationError as error:
            raise ValueError(str(error)) from error
        tool_results = [part for part in parts if part["type"] == "tool_result"]
        if tool_results:
            if len(parts) != 1 or role != "tool":
                raise ValueError("Chat Completions tool results must be a standalone message with role tool.")
            translated.append({"role": "tool", "tool_call_id": tool_results[0]["tool_call_id"], "content": tool_results[0]["content"]})
            continue
        translated.append({"role": role, "content": [_translate_content_part(part) for part in parts]})
    return translated


def _translate_content_part(part: dict[str, Any]) -> dict[str, object]:
    part_type = part["type"]
    if part_type == "text":
        return {"type": "text", "text": part["text"]}
    if part_type == "image":
        return {"type": "image_url", "image_url": {"url": _source_as_data_or_remote_url(part)}}
    if part_type == "audio":
        source = part["source"]
        encoded = source.get("base64_data") if isinstance(source, dict) else None
        if not isinstance(encoded, str):
            raise ValueError("OpenAI Chat Completions audio content requires base64_data.")
        _validate_base64(encoded)
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


def _source_as_data_or_remote_url(part: dict[str, Any]) -> str:
    source = part["source"]
    if not isinstance(source, dict):
        raise ValueError("Media content parts require a source object.")
    remote_url = source.get("url")
    if isinstance(remote_url, str):
        _validate_remote_media_url(remote_url)
        return remote_url
    encoded = source.get("base64_data")
    if isinstance(encoded, str):
        _validate_base64(encoded)
        return f"data:{part['mime_type']};base64,{encoded}"
    if source.get("asset_id"):
        raise ValueError("Stored media assets must be resolved to base64_data or a remote URL before execution.")
    raise ValueError("Media content part has no usable provider source.")


def _validate_base64(value: str) -> None:
    try:
        base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("Media base64_data must be valid base64.") from error


def _validate_remote_media_url(value: str) -> None:
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
