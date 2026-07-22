from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.db import ModelEndpoint

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
                    f"{endpoint.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
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

        if not isinstance(payload, dict) or not isinstance(payload.get("choices"), list):
            return ConnectionTestResult(
                False,
                "Provider returned an unexpected Chat Completions response.",
                response.status_code,
            )

        return ConnectionTestResult(True, "Connection succeeded.", response.status_code)

    @staticmethod
    def _build_request_body(endpoint: ModelEndpoint) -> dict[str, object]:
        allowed_defaults = {
            key: value
            for key, value in endpoint.default_request_body.items()
            if key not in PROTECTED_REQUEST_FIELDS
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
