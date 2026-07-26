from __future__ import annotations

import base64
import binascii
import ipaddress
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from app.db import ModelEndpoint
from app.services.connection_tester import PROTECTED_REQUEST_FIELDS
from app.services.content_ir import ContentValidationError, normalize_content_parts


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


class ModelExecutor(Protocol):
    def execute(
        self,
        endpoint: ModelEndpoint,
        api_key: str,
        input_snapshot: dict[str, object],
    ) -> SampleExecutionResult: ...


class OpenAIChatCompletionsExecutor:
    """Executes one text sample through an OpenAI-compatible endpoint."""

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
            request_snapshot = self._build_request(endpoint, input_snapshot)
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
                    f"{endpoint.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=request_snapshot,
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
            )

        try:
            payload = response.json()
            prediction = payload["choices"][0]["message"]["content"]
            input_tokens, output_tokens = _extract_usage(payload)
        except (IndexError, KeyError, TypeError, ValueError):
            return SampleExecutionResult(
                False,
                request_snapshot,
                raw_response,
                None,
                "response_parse_error",
                "Provider returned an unexpected Chat Completions response.",
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
        protocol_profile = endpoint.protocol_profile or "openai_chat_completions"
        if protocol_profile != "openai_chat_completions":
            raise ValueError(f"Unsupported execution protocol profile: {protocol_profile}.")

        allowed_defaults = {
            key: value
            for key, value in (endpoint.default_request_body or {}).items()
            if key not in PROTECTED_REQUEST_FIELDS
        }
        return {
            **allowed_defaults,
            "model": endpoint.model_name,
            "messages": _translate_messages(messages),
            "stream": False,
            "temperature": 0,
            "max_tokens": 32,
        }

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
