from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
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

        allowed_defaults = {
            key: value
            for key, value in (endpoint.default_request_body or {}).items()
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
