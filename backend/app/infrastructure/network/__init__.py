"""Network-bound infrastructure with SSRF and bounded-response protections."""

from app.infrastructure.network.outbound import (
    OutboundNetworkError,
    OutboundRedirectError,
    OutboundResponseTooLargeError,
    PinnedHTTPTransport,
    pinned_outbound_transport,
    read_bounded_response,
    validate_outbound_url,
)

__all__ = [
    "OutboundNetworkError",
    "OutboundRedirectError",
    "OutboundResponseTooLargeError",
    "PinnedHTTPTransport",
    "pinned_outbound_transport",
    "read_bounded_response",
    "validate_outbound_url",
]
