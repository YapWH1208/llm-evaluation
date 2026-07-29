from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx

from app.db.models import CapabilityDetection, ModelEndpoint
from app.services.model_executor import OpenAIChatCompletionsExecutor, _endpoint_url, _extract_prediction, _extract_usage
from app.services.outbound_network import (
    OutboundNetworkError,
    OutboundRedirectError,
    OutboundResponseTooLargeError,
    read_bounded_response,
    validate_outbound_url,
)
from app.services.provider_headers import provider_headers


DEFAULT_CAPABILITY_KEYS = (
    "text_input",
    "image_input",
    "audio_input",
    "video_input",
    "multiple_images",
    "multiple_audio_files",
    "multiple_videos",
    "mixed_media_input",
    "text_output",
    "image_output",
    "audio_output",
    "video_output",
    "file_output",
    "system_message",
    "multi_turn_conversation",
    "tool_calling",
    "parallel_tool_calling",
    "structured_output",
    "json_mode",
    "json_schema",
    "streaming",
    "seed",
    "logprobs",
    "usage_reporting",
    "maximum_context_length",
    "maximum_output_length",
    "supported_mime_types",
    "supported_languages",
)
_ONE_PIXEL_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLdfQAAAABJRU5ErkJggg=="
_SILENT_WAV = "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA="
_MINIMAL_VIDEO = "AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDE="


@dataclass(frozen=True, slots=True)
class CapabilityDetectionResult:
    capability_key: str
    status: CapabilityDetection
    evidence: dict[str, object]


class CapabilityDetector(Protocol):
    def detect(
        self,
        endpoint: ModelEndpoint,
        api_key: str,
        capability_keys: list[str],
    ) -> list[CapabilityDetectionResult]: ...


class OpenAIChatCompletionsCapabilityDetector:
    """Runs inexpensive OpenAI Chat Completions probes without storing secrets or media."""

    ADAPTER_VERSION = "provider-protocols/1"

    def __init__(self, transport: httpx.BaseTransport | None = None, *, max_response_bytes: int = 4 * 1024 * 1024) -> None:
        self._transport = transport
        self._max_response_bytes = max_response_bytes

    def detect(
        self,
        endpoint: ModelEndpoint,
        api_key: str,
        capability_keys: list[str],
    ) -> list[CapabilityDetectionResult]:
        return [self._detect_one(endpoint, api_key, key) for key in capability_keys]

    def _detect_one(
        self,
        endpoint: ModelEndpoint,
        api_key: str,
        capability_key: str,
    ) -> CapabilityDetectionResult:
        if capability_key not in _supported_probe_capabilities(endpoint):
            return CapabilityDetectionResult(
                capability_key,
                CapabilityDetection.UNSUPPORTED_BY_ADAPTER,
                self._evidence("not_run", reason="This adapter has no safe probe for the requested capability."),
            )

        messages = _probe_messages(capability_key)
        if capability_key == "system_message":
            messages.insert(0, {"role": "system", "content": "Reply with the single token OK."})
        if capability_key == "multi_turn_conversation":
            messages = [
                {"role": "user", "content": "Remember the word OK."},
                {"role": "assistant", "content": "OK"},
                {"role": "user", "content": "Reply with the remembered word."},
            ]
        try:
            request_body = self._request_body(endpoint, messages, capability_key)
            request_summary = _safe_request_summary(capability_key, messages, request_body)
            endpoint_url = _endpoint_url(endpoint)
            validate_outbound_url(endpoint_url, allow_loopback=str(getattr(endpoint, "protocol_profile", "")) == "ollama_chat")
            with httpx.Client(
                timeout=endpoint.timeout_seconds,
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                with client.stream(
                    "POST",
                    endpoint_url,
                    headers=provider_headers(endpoint, api_key),
                    json=request_body,
                ) as response:
                    body = read_bounded_response(response, max_bytes=self._max_response_bytes)
                    status_code = response.status_code
                    is_error = response.is_error
                    content_type = response.headers.get("content-type", "").lower()
        except OutboundNetworkError as error:
            return CapabilityDetectionResult(
                capability_key,
                CapabilityDetection.INCONCLUSIVE,
                self._evidence("unsafe_destination", reason=str(error), request_summary=request_summary),
            )
        except OutboundRedirectError as error:
            return CapabilityDetectionResult(
                capability_key,
                CapabilityDetection.INCONCLUSIVE,
                self._evidence("redirect_blocked", reason=str(error), request_summary=request_summary),
            )
        except OutboundResponseTooLargeError as error:
            return CapabilityDetectionResult(
                capability_key,
                CapabilityDetection.INCONCLUSIVE,
                self._evidence("response_too_large", reason=str(error), request_summary=request_summary),
            )
        except httpx.TimeoutException:
            return CapabilityDetectionResult(
                capability_key,
                CapabilityDetection.INCONCLUSIVE,
                self._evidence("timeout", reason="Provider request timed out.", request_summary=request_summary),
            )
        except httpx.RequestError:
            return CapabilityDetectionResult(
                capability_key,
                CapabilityDetection.INCONCLUSIVE,
                self._evidence("connection_error", reason="Could not connect to the provider.", request_summary=request_summary),
            )

        if is_error:
            status = (
                CapabilityDetection.FAILED
                if status_code in {400, 404, 405, 415, 422}
                else CapabilityDetection.INCONCLUSIVE
            )
            return CapabilityDetectionResult(
                capability_key,
                status,
                self._evidence("http_error", provider_status_code=status_code, request_summary=request_summary, response_summary=f"HTTP {status_code}"),
            )

        if capability_key == "streaming" and content_type.startswith("text/event-stream"):
            return CapabilityDetectionResult(
                capability_key,
                CapabilityDetection.PASSED,
                self._evidence("passed", provider_status_code=status_code, response_mode="sse", request_summary=request_summary, response_summary="SSE response accepted"),
            )

        try:
            payload = json.loads(body)
        except ValueError:
            return CapabilityDetectionResult(
                capability_key,
                CapabilityDetection.FAILED,
                self._evidence("invalid_json", provider_status_code=status_code, request_summary=request_summary, response_summary="Non-JSON response"),
            )

        if not isinstance(payload, dict) or not _has_expected_response_shape(endpoint, payload):
            return CapabilityDetectionResult(
                capability_key,
                CapabilityDetection.FAILED,
                self._evidence("unexpected_response", provider_status_code=status_code, request_summary=request_summary, response_summary="Unexpected provider response shape"),
            )
        if capability_key == "usage_reporting" and _extract_usage(payload) == (None, None):
            return CapabilityDetectionResult(
                capability_key,
                CapabilityDetection.FAILED,
                self._evidence("usage_missing", provider_status_code=status_code, request_summary=request_summary, response_summary="Usage fields absent"),
            )
        return CapabilityDetectionResult(
            capability_key,
            CapabilityDetection.PASSED,
            self._evidence("passed", provider_status_code=status_code, request_summary=request_summary, response_summary="Expected provider response shape"),
        )

    @classmethod
    def _evidence(cls, outcome: str, **details: object) -> dict[str, object]:
        return {
            "adapter_version": cls.ADAPTER_VERSION,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "outcome": outcome,
            **details,
        }

    @staticmethod
    def _request_body(endpoint: ModelEndpoint, messages: list[dict[str, object]], capability_key: str) -> dict[str, Any]:
        profile = _protocol_profile(endpoint)
        options: dict[str, object] = {"temperature": 0}
        if profile == "openai_responses":
            options["max_output_tokens"] = 8
        else:
            options["max_tokens"] = 8
        request = deepcopy(OpenAIChatCompletionsExecutor._build_request(
            endpoint,
            {"messages": messages, "request_body_evidence": {"effective_request_body": options}},
        ))
        request.update(_probe_controls(capability_key))
        return request


def _protocol_profile(endpoint: ModelEndpoint) -> str:
    return str(getattr(endpoint, "protocol_profile", None) or "openai_chat_completions")


def _has_expected_response_shape(endpoint: ModelEndpoint, payload: dict[str, object]) -> bool:
    try:
        return bool(_extract_prediction(payload, _protocol_profile(endpoint)))
    except (IndexError, KeyError, TypeError, ValueError):
        return False


def _probe_messages(capability_key: str) -> list[dict[str, object]]:
    """Return a minimum-size, provider-neutral request for a single probe."""

    text_part: dict[str, object] = {"type": "text", "text": "Reply with OK."}
    image_part: dict[str, object] = {"type": "image", "source": {"base64_data": _ONE_PIXEL_PNG}, "mime_type": "image/png"}
    audio_part: dict[str, object] = {"type": "audio", "source": {"base64_data": _SILENT_WAV}, "mime_type": "audio/wav"}
    video_part: dict[str, object] = {"type": "video", "source": {"base64_data": _MINIMAL_VIDEO}, "mime_type": "video/mp4"}
    parts_by_capability: dict[str, list[dict[str, object]]] = {
        "image_input": [text_part, image_part],
        "multiple_images": [text_part, image_part, dict(image_part)],
        "audio_input": [text_part, audio_part],
        "multiple_audio_files": [text_part, audio_part, dict(audio_part)],
        "video_input": [text_part, video_part],
        "multiple_videos": [text_part, video_part, dict(video_part)],
        "mixed_media_input": [text_part, image_part, audio_part, video_part],
    }
    parts = parts_by_capability.get(capability_key)
    if parts is None:
        return [{"role": "user", "content": "Reply with OK."}]
    return [{"role": "user", "content": parts}]


def _safe_request_summary(capability_key: str, messages: list[dict[str, object]], request: dict[str, object]) -> dict[str, object]:
    """Persist reproducibility metadata without retaining prompt text, media, or credentials."""

    content_types: list[str] = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, list):
            content_types.extend(str(part.get("type", "unknown")) for part in content if isinstance(part, dict))
        elif isinstance(content, str):
            content_types.append("text")
    return {
        "capability": capability_key,
        "message_count": len(messages),
        "content_types": content_types,
        "request_fields": sorted(str(key) for key in request if key not in {"messages", "input", "contents"}),
    }


def _supported_probe_capabilities(endpoint: ModelEndpoint) -> set[str]:
    profile = _protocol_profile(endpoint)
    common_text = {
        "text_input", "text_output", "system_message", "multi_turn_conversation", "usage_reporting",
    }
    multimedia = {
        "image_input", "audio_input", "video_input", "multiple_images", "multiple_audio_files", "multiple_videos", "mixed_media_input",
    }
    advanced = {"tool_calling", "parallel_tool_calling", "structured_output", "json_mode", "json_schema", "streaming", "seed", "logprobs"}
    if profile in {"openai_chat_completions", "azure_openai_chat_completions"}:
        return common_text | advanced | (multimedia - {"video_input", "multiple_videos", "mixed_media_input"})
    if profile == "openai_responses":
        return common_text | multimedia
    if profile in {"anthropic_messages", "gemini_generate_content"}:
        return common_text | {"image_input", "multiple_images"}
    if profile == "ollama_chat":
        return common_text | {"image_input", "multiple_images"}
    if profile == "custom_http_json":
        return {"text_input", "text_output"}
    return set()


def _probe_controls(capability_key: str) -> dict[str, object]:
    """Platform-owned probe fields; never accepted from normal run overrides."""

    if capability_key == "tool_calling":
        return {
            "tools": [{"type": "function", "function": {"name": "probe", "description": "Capability probe", "parameters": {"type": "object", "properties": {}}}}],
            "tool_choice": "none",
        }
    if capability_key == "parallel_tool_calling":
        return {
            "tools": [{"type": "function", "function": {"name": "probe", "description": "Capability probe", "parameters": {"type": "object", "properties": {}}}}],
            "tool_choice": "none",
            "parallel_tool_calls": True,
        }
    if capability_key in {"structured_output", "json_schema"}:
        return {
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "probe", "strict": True, "schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}},
            }
        }
    if capability_key == "json_mode":
        return {"response_format": {"type": "json_object"}}
    if capability_key == "streaming":
        return {"stream": True}
    if capability_key == "seed":
        return {"seed": 42}
    if capability_key == "logprobs":
        return {"logprobs": True, "top_logprobs": 1}
    return {}
