from __future__ import annotations

import json
from collections.abc import Mapping
from time import perf_counter
from typing import Any

import httpx

from app.db.models import ModelEndpoint
from app.infrastructure.network.outbound import (
    OutboundNetworkError,
    OutboundRedirectError,
    OutboundResponseTooLargeError,
    pinned_outbound_transport,
    read_bounded_response,
    validate_outbound_url,
)
from app.infrastructure.providers.adapters.base import SANDBOX_ECHO_TOOL_NAME
from app.infrastructure.providers.common import elapsed_ms, effective_request_options, is_sensitive_body_key
from app.infrastructure.providers.contracts import SandboxExecutionResult, SandboxToolCall
from app.infrastructure.providers.registry import ProviderRegistry


_TOOL_SYSTEM_PROMPT = "Use the provided function exactly once. Do not execute tools or perform external actions."
_TOOL_USER_PROMPT = "Call sandbox_echo with message set to sandbox."


class ProviderSandboxRunner:
    """Run one bounded provider request without persisting or executing tool calls."""

    def __init__(
        self,
        transport: httpx.BaseTransport | None = None,
        *,
        registry: ProviderRegistry | None = None,
        max_response_bytes: int = 4 * 1024 * 1024,
    ) -> None:
        self._registry = registry or ProviderRegistry()
        self._transport = transport
        self._max_response_bytes = max_response_bytes

    def execute(
        self,
        endpoint: ModelEndpoint,
        api_key: str,
        *,
        mode: str,
        user_prompt: str,
        system_prompt: str | None,
    ) -> SandboxExecutionResult:
        started_at = perf_counter()
        adapter = self._registry.for_endpoint(endpoint)
        if mode not in {"text", "tool"}:
            return self._failure(adapter.profile, {}, "invalid_mode", "Sandbox mode must be text or tool.", started_at)
        if mode == "tool" and not adapter.sandbox_tool_calling_supported:
            return self._failure(
                adapter.profile,
                {},
                "unsupported_tool_calling",
                f"The {adapter.profile} adapter does not support deterministic tool-calling sandbox tests.",
                started_at,
            )
        try:
            messages = _messages_for(mode, user_prompt, system_prompt)
            options = effective_request_options(
                {},
                protocol_profile=adapter.profile,
                model_defaults=adapter.endpoint_request_defaults(endpoint),
                equivalent_field_groups=adapter.equivalent_request_field_groups(),
            )
            if mode == "tool":
                outbound_request = adapter.build_sandbox_tool_request_with_options(endpoint, messages, options)
            else:
                outbound_request = adapter.build_request_with_options(endpoint, messages, options)
            request_snapshot = _safe_snapshot(outbound_request.body)
        except ValueError as error:
            return self._failure(adapter.profile, {}, "invalid_request", str(error), started_at)

        try:
            addresses = validate_outbound_url(outbound_request.url, allow_loopback=adapter.allow_loopback)
            with httpx.Client(
                timeout=endpoint.timeout_seconds,
                follow_redirects=False,
                transport=pinned_outbound_transport(addresses, injected_transport=self._transport),
            ) as client:
                with client.stream(
                    "POST", outbound_request.url, headers=adapter.headers(endpoint, api_key), json=outbound_request.body
                ) as response:
                    body = read_bounded_response(response, max_bytes=self._max_response_bytes)
                    status_code = response.status_code
                    is_error = response.is_error
        except OutboundNetworkError as error:
            return self._failure(adapter.profile, request_snapshot, "unsafe_destination", str(error), started_at)
        except OutboundRedirectError as error:
            return self._failure(adapter.profile, request_snapshot, "redirect_blocked", str(error), started_at)
        except OutboundResponseTooLargeError as error:
            return self._failure(adapter.profile, request_snapshot, "response_too_large", str(error), started_at)
        except httpx.TimeoutException:
            return self._failure(
                adapter.profile, request_snapshot, "timeout", "Provider request timed out.", started_at
            )
        except httpx.RequestError:
            return self._failure(
                adapter.profile, request_snapshot, "connection_error", "Could not connect to the provider.", started_at
            )

        if is_error:
            return self._failure(
                adapter.profile,
                request_snapshot,
                f"http_{status_code}",
                f"Provider returned HTTP {status_code}.",
                started_at,
                provider_status_code=status_code,
            )
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("Provider response was not a JSON object.")
            input_tokens, output_tokens = adapter.extract_usage(payload)
            if mode == "tool":
                tool_calls = adapter.extract_sandbox_tool_calls(payload)
                validation_error = _validate_tool_calls(tool_calls)
                if validation_error is not None:
                    return SandboxExecutionResult(
                        success=False,
                        protocol_profile=adapter.profile,
                        request_snapshot=request_snapshot,
                        final_text=None,
                        tool_calls=tool_calls,
                        error_type="tool_call_validation",
                        error_message=validation_error,
                        latency_ms=elapsed_ms(started_at),
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        provider_status_code=status_code,
                    )
                return SandboxExecutionResult(
                    success=True,
                    protocol_profile=adapter.profile,
                    request_snapshot=request_snapshot,
                    final_text=None,
                    tool_calls=tool_calls,
                    latency_ms=elapsed_ms(started_at),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    provider_status_code=status_code,
                )
            return SandboxExecutionResult(
                success=True,
                protocol_profile=adapter.profile,
                request_snapshot=request_snapshot,
                final_text=adapter.extract_prediction(payload),
                tool_calls=(),
                latency_ms=elapsed_ms(started_at),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                provider_status_code=status_code,
            )
        except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return self._failure(
                adapter.profile,
                request_snapshot,
                "response_parse_error",
                "Provider returned an unexpected response payload.",
                started_at,
                provider_status_code=status_code,
            )

    @staticmethod
    def _failure(
        protocol_profile: str,
        request_snapshot: dict[str, Any],
        error_type: str,
        error_message: str,
        started_at: float,
        *,
        provider_status_code: int | None = None,
    ) -> SandboxExecutionResult:
        return SandboxExecutionResult(
            success=False,
            protocol_profile=protocol_profile,
            request_snapshot=request_snapshot,
            final_text=None,
            tool_calls=(),
            error_type=error_type,
            error_message=error_message,
            latency_ms=elapsed_ms(started_at),
            provider_status_code=provider_status_code,
        )


def _messages_for(mode: str, user_prompt: str, system_prompt: str | None) -> list[dict[str, str]]:
    if mode == "tool":
        return [
            {"role": "system", "content": _TOOL_SYSTEM_PROMPT},
            {"role": "user", "content": _TOOL_USER_PROMPT},
        ]
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    return messages


def _validate_tool_calls(tool_calls: tuple[SandboxToolCall, ...]) -> str | None:
    if len(tool_calls) != 1:
        return "Provider did not emit exactly one sandbox_echo tool call."
    call = tool_calls[0]
    if call.name != SANDBOX_ECHO_TOOL_NAME:
        return "Provider emitted a tool call with an unexpected name."
    if not isinstance(call.arguments.get("message"), str):
        return "Provider emitted sandbox_echo without a string message argument."
    return None


def _safe_snapshot(value: object) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _safe_snapshot(item)
            for key, item in value.items()
            if isinstance(key, str) and not is_sensitive_body_key(key)
        }
    if isinstance(value, list):
        return [_safe_snapshot(item) for item in value]
    return value


__all__ = ["ProviderSandboxRunner"]
