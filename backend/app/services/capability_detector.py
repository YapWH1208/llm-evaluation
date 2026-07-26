from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx

from app.db.models import CapabilityDetection, ModelEndpoint
from app.services.model_executor import OpenAIChatCompletionsExecutor, _endpoint_url, _extract_prediction, _extract_usage
from app.services.provider_headers import provider_headers


DEFAULT_CAPABILITY_KEYS = (
    "text_input",
    "image_input",
    "audio_input",
    "video_input",
    "system_message",
    "usage_reporting",
)
_ONE_PIXEL_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLdfQAAAABJRU5ErkJggg=="
_SILENT_WAV = "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA="


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

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport

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

        messages: list[dict[str, object]] = [{"role": "user", "content": "Reply with OK."}]
        if capability_key == "system_message":
            messages.insert(0, {"role": "system", "content": "Reply with the single token OK."})
        if capability_key == "image_input":
            messages = [{"role": "user", "content": [{"type": "text", "text": "Reply with OK."}, {"type": "image", "source": {"base64_data": _ONE_PIXEL_PNG}, "mime_type": "image/png"}]}]
        if capability_key == "audio_input":
            messages = [{"role": "user", "content": [{"type": "text", "text": "Reply with OK."}, {"type": "audio", "source": {"base64_data": _SILENT_WAV}, "mime_type": "audio/wav"}]}]

        try:
            with httpx.Client(
                timeout=endpoint.timeout_seconds,
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                response = client.post(
                    _endpoint_url(endpoint),
                    headers=provider_headers(endpoint, api_key),
                    json=self._request_body(endpoint, messages),
                )
        except httpx.TimeoutException:
            return CapabilityDetectionResult(
                capability_key,
                CapabilityDetection.INCONCLUSIVE,
                self._evidence("timeout", reason="Provider request timed out."),
            )
        except httpx.RequestError:
            return CapabilityDetectionResult(
                capability_key,
                CapabilityDetection.INCONCLUSIVE,
                self._evidence("connection_error", reason="Could not connect to the provider."),
            )

        if response.is_error:
            status = (
                CapabilityDetection.FAILED
                if response.status_code in {400, 404, 405, 415, 422}
                else CapabilityDetection.INCONCLUSIVE
            )
            return CapabilityDetectionResult(
                capability_key,
                status,
                self._evidence("http_error", provider_status_code=response.status_code),
            )

        try:
            payload = response.json()
        except ValueError:
            return CapabilityDetectionResult(
                capability_key,
                CapabilityDetection.FAILED,
                self._evidence("invalid_json", provider_status_code=response.status_code),
            )

        if not isinstance(payload, dict) or not _has_expected_response_shape(endpoint, payload):
            return CapabilityDetectionResult(
                capability_key,
                CapabilityDetection.FAILED,
                self._evidence("unexpected_response", provider_status_code=response.status_code),
            )
        if capability_key == "usage_reporting" and _extract_usage(payload) == (None, None):
            return CapabilityDetectionResult(
                capability_key,
                CapabilityDetection.FAILED,
                self._evidence("usage_missing", provider_status_code=response.status_code),
            )
        return CapabilityDetectionResult(
            capability_key,
            CapabilityDetection.PASSED,
            self._evidence("passed", provider_status_code=response.status_code),
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
    def _request_body(endpoint: ModelEndpoint, messages: list[dict[str, object]]) -> dict[str, Any]:
        profile = _protocol_profile(endpoint)
        options: dict[str, object] = {"temperature": 0}
        if profile == "openai_responses":
            options["max_output_tokens"] = 8
        else:
            options["max_tokens"] = 8
        return OpenAIChatCompletionsExecutor._build_request(
            endpoint,
            {"messages": messages, "request_body_evidence": {"effective_request_body": options}},
        )


def _protocol_profile(endpoint: ModelEndpoint) -> str:
    return str(getattr(endpoint, "protocol_profile", None) or "openai_chat_completions")


def _has_expected_response_shape(endpoint: ModelEndpoint, payload: dict[str, object]) -> bool:
    try:
        return bool(_extract_prediction(payload, _protocol_profile(endpoint)))
    except (IndexError, KeyError, TypeError, ValueError):
        return False


def _supported_probe_capabilities(endpoint: ModelEndpoint) -> set[str]:
    profile = _protocol_profile(endpoint)
    if profile in {"openai_chat_completions", "openai_responses", "azure_openai_chat_completions"}:
        return set(DEFAULT_CAPABILITY_KEYS) - {"video_input"}
    if profile in {"anthropic_messages", "gemini_generate_content"}:
        return {"text_input", "image_input", "system_message", "usage_reporting"}
    if profile == "ollama_chat":
        return {"text_input", "image_input", "system_message", "usage_reporting"}
    if profile == "custom_http_json":
        return {"text_input"}
    return set()
