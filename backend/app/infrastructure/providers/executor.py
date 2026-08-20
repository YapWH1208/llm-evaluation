from __future__ import annotations

import json
from time import perf_counter

import httpx

from app.db.models import ModelEndpoint
from app.infrastructure.providers.common import (
    effective_request_options,
    elapsed_ms,
    extract_token_logprobs,
    extract_usage,
    parse_retry_after,
    request_snapshot_metadata,
)
from app.infrastructure.providers.contracts import ModelExecutor, SampleExecutionResult
from app.infrastructure.providers.registry import ProviderRegistry
from app.infrastructure.network.outbound import (
    OutboundNetworkError,
    OutboundRedirectError,
    OutboundResponseTooLargeError,
    pinned_outbound_transport,
    read_bounded_response,
    validate_outbound_url,
)


class ProviderExecutor:
    """Executes samples through the adapter selected by the composition root."""

    def __init__(self, transport: httpx.BaseTransport | None = None, *, registry: ProviderRegistry | None = None, max_response_bytes: int = 4 * 1024 * 1024) -> None:
        self._registry = registry or ProviderRegistry()
        self._transport = transport
        self._max_response_bytes = max_response_bytes

    def execute(self, endpoint: ModelEndpoint, api_key: str, input_snapshot: dict[str, object]) -> SampleExecutionResult:
        started_at = perf_counter()
        adapter = self._registry.for_endpoint(endpoint)
        try:
            messages = input_snapshot.get("messages")
            if not isinstance(messages, list):
                raise ValueError("Text sample input must contain a messages list.")
            options = effective_request_options(input_snapshot, protocol_profile=adapter.profile, model_defaults=endpoint.default_request_body)
            outbound_request = adapter.build_request_with_options(endpoint, messages, options)
            request_snapshot = dict(outbound_request.body)
            evidence = request_snapshot_metadata(input_snapshot)
            if evidence is not None:
                request_snapshot["_evaluation"] = {"request_body_evidence": evidence}
        except ValueError as error:
            return SampleExecutionResult(False, {}, None, None, "invalid_sample", str(error), latency_ms=elapsed_ms(started_at))

        try:
            addresses = validate_outbound_url(outbound_request.url, allow_loopback=adapter.allow_loopback)
            with httpx.Client(timeout=endpoint.timeout_seconds, follow_redirects=False, transport=pinned_outbound_transport(addresses, injected_transport=self._transport)) as client:
                with client.stream("POST", outbound_request.url, headers=adapter.headers(endpoint, api_key), json=outbound_request.body) as response:
                    body = read_bounded_response(response, max_bytes=self._max_response_bytes)
                    status_code = response.status_code
                    is_error = response.is_error
                    response_headers = response.headers
        except OutboundNetworkError as error:
            return SampleExecutionResult(False, request_snapshot, None, None, "unsafe_destination", str(error), latency_ms=elapsed_ms(started_at))
        except OutboundRedirectError as error:
            return SampleExecutionResult(False, request_snapshot, None, None, "redirect_blocked", str(error), latency_ms=elapsed_ms(started_at))
        except OutboundResponseTooLargeError as error:
            return SampleExecutionResult(False, request_snapshot, None, None, "response_too_large", str(error), latency_ms=elapsed_ms(started_at))
        except httpx.TimeoutException:
            return SampleExecutionResult(False, request_snapshot, None, None, "timeout", "Provider request timed out.", latency_ms=elapsed_ms(started_at))
        except httpx.RequestError:
            return SampleExecutionResult(False, request_snapshot, None, None, "connection_error", "Could not connect to the provider.", latency_ms=elapsed_ms(started_at))

        raw_response = body.decode("utf-8", errors="replace")
        if is_error:
            return SampleExecutionResult(False, request_snapshot, raw_response, None, f"http_{status_code}", f"Provider returned HTTP {status_code}.", latency_ms=elapsed_ms(started_at), retry_after_seconds=parse_retry_after(response_headers.get("retry-after")))
        try:
            payload = json.loads(body)
            prediction = adapter.extract_prediction(payload)
            input_tokens, output_tokens = extract_usage(payload)
            token_logprobs = extract_token_logprobs(payload, adapter.profile)
        except (IndexError, KeyError, TypeError, ValueError):
            return SampleExecutionResult(False, request_snapshot, raw_response, None, "response_parse_error", "Provider returned an unexpected response payload.", latency_ms=elapsed_ms(started_at))
        return SampleExecutionResult(True, request_snapshot, raw_response, prediction, latency_ms=elapsed_ms(started_at), input_tokens=input_tokens, output_tokens=output_tokens, token_logprobs=token_logprobs)


__all__ = ["ModelExecutor", "ProviderExecutor", "SampleExecutionResult"]
