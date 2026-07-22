from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.db import ModelEndpoint
from app.services.connection_tester import PROTECTED_REQUEST_FIELDS


@dataclass(frozen=True, slots=True)
class SampleExecutionResult:
    success: bool
    request_snapshot: dict[str, Any]
    raw_response: str | None
    prediction: str | None
    error_type: str | None = None
    error_message: str | None = None


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
            )
        except httpx.RequestError:
            return SampleExecutionResult(
                False,
                request_snapshot,
                None,
                None,
                "connection_error",
                "Could not connect to the provider.",
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
            )

        try:
            payload = response.json()
            prediction = payload["choices"][0]["message"]["content"]
        except (IndexError, KeyError, TypeError, ValueError):
            return SampleExecutionResult(
                False,
                request_snapshot,
                raw_response,
                None,
                "response_parse_error",
                "Provider returned an unexpected Chat Completions response.",
            )

        if not isinstance(prediction, str):
            return SampleExecutionResult(
                False,
                request_snapshot,
                raw_response,
                None,
                "response_parse_error",
                "Provider response did not contain text content.",
            )

        return SampleExecutionResult(True, request_snapshot, raw_response, prediction)

    @staticmethod
    def _build_request(
        endpoint: ModelEndpoint,
        input_snapshot: dict[str, object],
    ) -> dict[str, Any]:
        messages = input_snapshot.get("messages")
        if not isinstance(messages, list):
            raise ValueError("Text sample input must contain a messages list.")

        allowed_defaults = {
            key: value
            for key, value in endpoint.default_request_body.items()
            if key not in PROTECTED_REQUEST_FIELDS
        }
        return {
            **allowed_defaults,
            "model": endpoint.model_name,
            "messages": messages,
            "stream": False,
            "temperature": 0,
            "max_tokens": 32,
        }

def normalize_exact_match(value: str) -> str:
    return " ".join(value.strip().split())
