from __future__ import annotations

from typing import Any


_BLOCKED_HEADERS = frozenset(
    {"authorization", "cookie", "host", "content-length", "x-api-key", "x-goog-api-key", "api-key"}
)

PROTECTED_REQUEST_FIELDS = frozenset(
    {
        "model",
        "messages",
        "input",
        "contents",
        "system",
        "systemInstruction",
        "stream",
        "tools",
        "response_format",
    }
)


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
    profile = str(getattr(endpoint, "protocol_profile", None) or "openai_chat_completions")
    if profile == "anthropic_messages":
        headers["x-api-key"] = api_key
        if not any(name.lower() == "anthropic-version" for name in headers):
            headers["anthropic-version"] = "2023-06-01"
    elif profile == "gemini_generate_content":
        headers["x-goog-api-key"] = api_key
    elif profile == "azure_openai_chat_completions":
        headers["api-key"] = api_key
    elif profile != "ollama_chat" or api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers
