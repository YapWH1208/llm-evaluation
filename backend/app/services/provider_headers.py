from __future__ import annotations

from typing import Any


_BLOCKED_HEADERS = frozenset({"authorization", "cookie", "host", "content-length"})


def validate_custom_headers(value: dict[str, Any]) -> dict[str, str]:
    """Allow provider routing headers while reserving authentication for the secret vault."""

    if len(value) > 32:
        raise ValueError("custom_headers may contain at most 32 headers.")
    normalized: dict[str, str] = {}
    for name, header_value in value.items():
        if not isinstance(name, str) or not name.strip() or any(char in name for char in "\r\n:"):
            raise ValueError("custom_headers contains an invalid header name.")
        if name.lower() in _BLOCKED_HEADERS:
            raise ValueError(f"custom_headers cannot set protected header: {name}.")
        if not isinstance(header_value, str) or "\r" in header_value or "\n" in header_value:
            raise ValueError(f"custom_headers contains an invalid value for {name}.")
        if len(header_value) > 4096:
            raise ValueError(f"custom_headers value for {name} is too long.")
        normalized[name] = header_value
    return normalized


def provider_headers(endpoint: Any, api_key: str) -> dict[str, str]:
    custom_headers = getattr(endpoint, "custom_headers", None) or {}
    headers = {str(name): str(value) for name, value in custom_headers.items()}
    headers["Authorization"] = f"Bearer {api_key}"
    return headers
