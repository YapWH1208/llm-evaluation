from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.db import ModelEndpoint
from app.services.provider_headers import provider_headers

PROTECTED_REQUEST_FIELDS = frozenset(
    {
        "model",
        "messages",
        "input",
        "stream",
        "tools",
        "response_format",
    }
)


@dataclass(frozen=True, slots=True)
class ConnectionTestResult:
    success: bool
    message: str
    provider_status_code: int | None = None


class ConnectionTester(Protocol):
    def test(self, endpoint: ModelEndpoint, api_key: str) -> ConnectionTestResult: ...


class OpenAIChatCompletionsConnectionTester:
    """Performs a bounded, text-only OpenAI-compatible connection probe."""

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport

    def test(self, endpoint: ModelEndpoint, api_key: str) -> ConnectionTestResult:
        request_body = self._build_request_body(endpoint)
        try:
            with httpx.Client(
                timeout=endpoint.timeout_seconds,
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                response = client.post(
                    _endpoint_url(endpoint),
                    headers=provider_headers(endpoint, api_key),
                    json=request_body,
                )
        except httpx.TimeoutException:
            return ConnectionTestResult(False, "Provider request timed out.")
        except httpx.RequestError:
            return ConnectionTestResult(False, "Could not connect to the provider.")

        if response.is_error:
            return ConnectionTestResult(
                False,
                f"Provider returned HTTP {response.status_code}.",
                response.status_code,
            )

        try:
            payload = response.json()
        except ValueError:
            return ConnectionTestResult(
                False,
                "Provider returned a non-JSON response.",
                response.status_code,
            )

        if not isinstance(payload, dict) or not _has_expected_response_shape(endpoint, payload):
            return ConnectionTestResult(
                False,
                "Provider returned an unexpected response payload.",
                response.status_code,
            )

        return ConnectionTestResult(True, "Connection succeeded.", response.status_code)

    @staticmethod
    def _build_request_body(endpoint: ModelEndpoint) -> dict[str, object]:
        allowed_defaults = {
            key: value
            for key, value in (endpoint.default_request_body or {}).items()
            if key not in PROTECTED_REQUEST_FIELDS
        }
        if _protocol_profile(endpoint) == "openai_responses":
            return {
                **allowed_defaults,
                "model": endpoint.model_name,
                "input": [{"role": "user", "content": [{"type": "input_text", "text": "Respond with the single word OK."}]}],
                "max_output_tokens": 8,
                "stream": False,
                "store": False,
            }
        return {
            **allowed_defaults,
            "model": endpoint.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": "Respond with the single word OK.",
                }
            ],
            "temperature": 0,
            "max_tokens": 8,
            "stream": False,
        }


def _protocol_profile(endpoint: ModelEndpoint) -> str:
    return str(getattr(endpoint, "protocol_profile", None) or "openai_chat_completions")


def _endpoint_url(endpoint: ModelEndpoint) -> str:
    suffix = "/responses" if _protocol_profile(endpoint) == "openai_responses" else "/chat/completions"
    return f"{endpoint.base_url}{suffix}"


def _has_expected_response_shape(endpoint: ModelEndpoint, payload: dict[str, object]) -> bool:
    if _protocol_profile(endpoint) == "openai_responses":
        if isinstance(payload.get("output_text"), str):
            return True
        output = payload.get("output")
        return isinstance(output, list) and any(
            isinstance(item, dict) and item.get("type") == "message" for item in output
        )
    return isinstance(payload.get("choices"), list)
