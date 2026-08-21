from __future__ import annotations

import ipaddress
from collections.abc import Iterable
from socket import SOCK_STREAM, getaddrinfo
from urllib.parse import urlparse

import httpcore
import httpx
from httpx._transports.default import map_httpcore_exceptions


class OutboundNetworkError(ValueError):
    """Raised when an outbound request target is not safe to contact."""


class OutboundResponseTooLargeError(ValueError):
    """Raised before an oversized provider response enters application storage."""


class OutboundRedirectError(ValueError):
    """Raised when a provider asks the client to follow a new destination."""


class _PinnedNetworkBackend(httpcore.SyncBackend):
    """Connect an httpcore pool to validated addresses without another DNS lookup."""

    def __init__(self, addresses: tuple[str, ...]) -> None:
        super().__init__()
        self._addresses = addresses
        self._next_address = 0

    def connect_tcp(self, host: str, port: int, **kwargs: object) -> httpcore.NetworkStream:
        del host
        address = self._addresses[self._next_address % len(self._addresses)]
        self._next_address += 1
        return super().connect_tcp(address, port, **kwargs)


class _PinnedResponseStream(httpx.SyncByteStream):
    def __init__(self, stream: Iterable[bytes]) -> None:
        self._stream = stream

    def __iter__(self) -> Iterable[bytes]:
        yield from self._stream

    def close(self) -> None:
        close = getattr(self._stream, "close", None)
        if callable(close):
            close()


class PinnedHTTPTransport(httpx.BaseTransport):
    """HTTP transport that pins connection establishment to safe DNS answers.

    The pool still receives the original request hostname, so its Host header
    and TLS SNI/certificate validation remain correct.  Only the socket target
    is substituted, preventing a later DNS resolution from being rebound to an
    internal address.
    """

    def __init__(self, addresses: tuple[str, ...]) -> None:
        if not addresses:
            raise ValueError("Pinned outbound transport requires a resolved address.")
        self._pool = httpcore.ConnectionPool(network_backend=_PinnedNetworkBackend(addresses))

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        core_request = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        with map_httpcore_exceptions():
            response = self._pool.handle_request(core_request)
        return httpx.Response(
            status_code=response.status,
            headers=response.headers,
            stream=_PinnedResponseStream(response.stream),
            extensions=response.extensions,
        )

    def close(self) -> None:
        self._pool.close()


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


def pinned_outbound_transport(
    addresses: tuple[str, ...], *, injected_transport: httpx.BaseTransport | None = None
) -> httpx.BaseTransport:
    """Use an injected transport in tests, otherwise pin to validated DNS answers."""

    return injected_transport if injected_transport is not None else PinnedHTTPTransport(addresses)


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
            raise OutboundResponseTooLargeError(f"Provider response exceeds the configured {max_bytes} byte limit.")
    return _read_chunks(response.iter_bytes(), max_bytes=max_bytes)


def _read_chunks(chunks: Iterable[bytes], *, max_bytes: int) -> bytes:
    body = bytearray()
    for chunk in chunks:
        body.extend(chunk)
        if len(body) > max_bytes:
            raise OutboundResponseTooLargeError(f"Provider response exceeds the configured {max_bytes} byte limit.")
    return bytes(body)
