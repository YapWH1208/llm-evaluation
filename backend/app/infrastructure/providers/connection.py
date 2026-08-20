from __future__ import annotations

import json

import httpx

from app.db.models import ModelEndpoint
from app.infrastructure.providers.contracts import ConnectionTestRequest, ConnectionTestResult
from app.infrastructure.providers.registry import ProviderRegistry
from app.infrastructure.network.outbound import (
    OutboundNetworkError,
    OutboundRedirectError,
    OutboundResponseTooLargeError,
    pinned_outbound_transport,
    read_bounded_response,
    validate_outbound_url,
)


class ProviderConnectionTester:
    def __init__(self, transport: httpx.BaseTransport | None = None, *, registry: ProviderRegistry | None = None, max_response_bytes: int = 4 * 1024 * 1024) -> None:
        self._registry = registry or ProviderRegistry()
        self._transport = transport
        self._max_response_bytes = max_response_bytes

    def test(self, endpoint: ModelEndpoint, api_key: str) -> ConnectionTestResult:
        request = self.build_request(endpoint)
        adapter = self._registry.for_endpoint(endpoint)
        try:
            addresses = validate_outbound_url(request.url, allow_loopback=adapter.allow_loopback)
            with httpx.Client(timeout=endpoint.timeout_seconds, follow_redirects=False, transport=pinned_outbound_transport(addresses, injected_transport=self._transport)) as client:
                with client.stream("POST", request.url, headers=adapter.headers(endpoint, api_key), json=request.body) as response:
                    body = read_bounded_response(response, max_bytes=self._max_response_bytes)
                    status_code = response.status_code
                    is_error = response.is_error
        except (OutboundNetworkError, OutboundRedirectError, OutboundResponseTooLargeError) as error:
            return ConnectionTestResult(False, str(error))
        except httpx.TimeoutException:
            return ConnectionTestResult(False, "Provider request timed out.")
        except httpx.RequestError:
            return ConnectionTestResult(False, "Could not connect to the provider.")
        if is_error:
            return ConnectionTestResult(False, f"Provider returned HTTP {status_code}.", status_code)
        try:
            payload = json.loads(body)
        except (ValueError, TypeError):
            if body.strip():
                return ConnectionTestResult(False, "Provider returned a non-JSON response.", status_code)
            payload = None
        if payload is not None and not isinstance(payload, dict):
            return ConnectionTestResult(False, "Provider returned an unexpected response payload.", status_code)
        return ConnectionTestResult(True, "Connection succeeded.", status_code)

    def build_request(self, endpoint: ModelEndpoint) -> ConnectionTestRequest:
        return build_connection_test_request(endpoint, self._registry)


def build_connection_test_request(endpoint: ModelEndpoint, registry: ProviderRegistry | None = None) -> ConnectionTestRequest:
    adapter = (registry or ProviderRegistry()).for_endpoint(endpoint)
    return ConnectionTestRequest("POST", adapter.endpoint_url(endpoint), adapter.build_connection_body(endpoint))
