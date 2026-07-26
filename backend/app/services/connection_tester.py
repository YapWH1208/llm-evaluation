from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.db import ModelEndpoint
from app.services.model_executor import _endpoint_url, _extract_prediction
from app.services.provider_headers import PROTECTED_REQUEST_FIELDS, provider_headers


@dataclass(frozen=True, slots=True)
class ConnectionTestResult:
    success: bool
    message: str
    provider_status_code: int | None = None


class ConnectionTester(Protocol):
    def test(self, endpoint: ModelEndpoint, api_key: str) -> ConnectionTestResult: ...


class OpenAIChatCompletionsConnectionTester:
    """Performs a bounded, text-only probe for each built-in protocol profile."""

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
        if _protocol_profile(endpoint) == "anthropic_messages":
            return {
                **allowed_defaults,
                "model": endpoint.model_name,
                "messages": [{"role": "user", "content": [{"type": "text", "text": "Respond with the single word OK."}]}],
                "max_tokens": 8,
                "stream": False,
            }
        if _protocol_profile(endpoint) == "gemini_generate_content":
            return {
                **allowed_defaults,
                "contents": [{"role": "user", "parts": [{"text": "Respond with the single word OK."}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 8},
            }
        if _protocol_profile(endpoint) == "ollama_chat":
            return {
                **allowed_defaults,
                "model": endpoint.model_name,
                "messages": [{"role": "user", "content": "Respond with the single word OK."}],
                "options": {"temperature": 0, "num_predict": 8},
                "stream": False,
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


def _has_expected_response_shape(endpoint: ModelEndpoint, payload: dict[str, object]) -> bool:
    try:
        return bool(_extract_prediction(payload, _protocol_profile(endpoint)))
    except (IndexError, KeyError, TypeError, ValueError):
        return False
