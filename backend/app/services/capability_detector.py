from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx

from app.db.models import CapabilityDetection, ModelEndpoint
from app.services.connection_tester import PROTECTED_REQUEST_FIELDS


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

    ADAPTER_VERSION = "openai-chat-completions/1"

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
        if capability_key not in DEFAULT_CAPABILITY_KEYS or capability_key == "video_input":
            return CapabilityDetectionResult(
                capability_key,
                CapabilityDetection.UNSUPPORTED_BY_ADAPTER,
                self._evidence("not_run", reason="This adapter has no safe probe for the requested capability."),
            )

        messages: list[dict[str, object]] = [{"role": "user", "content": "Reply with OK."}]
        if capability_key == "system_message":
            messages.insert(0, {"role": "system", "content": "Reply with the single token OK."})
        if capability_key == "image_input":
            messages = [{"role": "user", "content": [{"type": "text", "text": "Reply with OK."}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{_ONE_PIXEL_PNG}"}}]}]
        if capability_key == "audio_input":
            messages = [{"role": "user", "content": [{"type": "text", "text": "Reply with OK."}, {"type": "input_audio", "input_audio": {"data": _SILENT_WAV, "format": "wav"}}]}]

        try:
            with httpx.Client(
                timeout=endpoint.timeout_seconds,
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                response = client.post(
                    f"{endpoint.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
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

        if not isinstance(payload, dict) or not isinstance(payload.get("choices"), list):
            return CapabilityDetectionResult(
                capability_key,
                CapabilityDetection.FAILED,
                self._evidence("unexpected_response", provider_status_code=response.status_code),
            )
        if capability_key == "usage_reporting" and not isinstance(payload.get("usage"), dict):
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
        allowed_defaults = {
            key: value
            for key, value in (endpoint.default_request_body or {}).items()
            if key not in PROTECTED_REQUEST_FIELDS
        }
        return {
            **allowed_defaults,
            "model": endpoint.model_name,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 8,
            "stream": False,
        }
