from __future__ import annotations

import ipaddress
from collections.abc import Iterable
from socket import SOCK_STREAM, getaddrinfo
from urllib.parse import urlparse

import httpx


class OutboundNetworkError(ValueError):
    """Raised when an outbound request target is not safe to contact."""


class OutboundResponseTooLargeError(ValueError):
    """Raised before an oversized provider response enters application storage."""


class OutboundRedirectError(ValueError):
    """Raised when a provider asks the client to follow a new destination."""


def validate_outbound_url(
    value: str,
    *,
    allow_loopback: bool = False,
    resolve_hostname: bool = True,
) -> tuple[str, ...]:
    """Validate a provider URL and every currently resolved destination address.

    The caller performs this immediately before sending the request.  This closes
    hostname aliases and common DNS rebinding paths without treating a hostname
    as intrinsically safe.  Redirects must remain disabled at the HTTP layer.
    """

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise OutboundNetworkError("Outbound endpoint URLs must be absolute HTTP or HTTPS URLs.")
    if parsed.username or parsed.password:
        raise OutboundNetworkError("Outbound endpoint URLs must not include credentials.")
    host = parsed.hostname
    if host is None:
        raise OutboundNetworkError("Outbound endpoint URLs must include a hostname.")
    if not resolve_hostname:
        _validate_literal_host(host, allow_loopback=allow_loopback)
        return ()
    try:
        addresses = tuple(sorted({entry[4][0] for entry in getaddrinfo(host, parsed.port, type=SOCK_STREAM)}))
    except OSError as error:
        raise OutboundNetworkError("Outbound endpoint hostname could not be resolved.") from error
    if not addresses:
        raise OutboundNetworkError("Outbound endpoint hostname did not resolve to an address.")
    for address in addresses:
        _validate_address(address, allow_loopback=allow_loopback)
    return addresses


def _validate_literal_host(host: str, *, allow_loopback: bool) -> None:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return
    _validate_address(host, allow_loopback=allow_loopback)


def _validate_address(value: str, *, allow_loopback: bool) -> None:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as error:
        raise OutboundNetworkError("Outbound endpoint resolution returned an invalid IP address.") from error
    mapped = address.ipv4_mapped if isinstance(address, ipaddress.IPv6Address) else None
    if mapped is not None:
        address = mapped
    if address.is_loopback and allow_loopback:
        return
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        raise OutboundNetworkError("Outbound endpoint resolves to a private or restricted network address.")


def read_bounded_response(response: httpx.Response, *, max_bytes: int) -> bytes:
    """Read an HTTP response incrementally, refusing redirects and oversized bodies."""

    if response.is_redirect:
        raise OutboundRedirectError("Provider redirects are not allowed.")
    content_length = response.headers.get("content-length")
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError:
            declared_length = None
        if declared_length is not None and declared_length > max_bytes:
            raise OutboundResponseTooLargeError(
                f"Provider response exceeds the configured {max_bytes} byte limit."
            )
    return _read_chunks(response.iter_bytes(), max_bytes=max_bytes)


def _read_chunks(chunks: Iterable[bytes], *, max_bytes: int) -> bytes:
    body = bytearray()
    for chunk in chunks:
        body.extend(chunk)
        if len(body) > max_bytes:
            raise OutboundResponseTooLargeError(
                f"Provider response exceeds the configured {max_bytes} byte limit."
            )
    return bytes(body)
