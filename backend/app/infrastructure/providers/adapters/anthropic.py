from __future__ import annotations

from typing import Any

from app.core.content import ContentValidationError, normalize_content_parts
from app.db.models import ModelEndpoint
from app.infrastructure.providers.adapters.base import ProviderAdapter
from app.infrastructure.providers.common import validate_base64, validate_remote_media_url


class AnthropicMessagesAdapter(ProviderAdapter):
    profile = "anthropic_messages"
    credential_header = "x-api-key"
    credential_prefix = ""
    static_headers = {"anthropic-version": "2023-06-01"}
    capabilities = frozenset(
        {
            "text_input",
            "text_output",
            "system_message",
            "multi_turn_conversation",
            "usage_reporting",
            "image_input",
            "multiple_images",
        }
    )

    def path_suffix(self, endpoint: ModelEndpoint) -> str:
        return "/v1/messages"

    def build_request(
        self, endpoint: ModelEndpoint, messages: list[object], options: dict[str, object]
    ) -> dict[str, Any]:
        allowed = self.safe_defaults(options)
        translated, system_parts = translate_anthropic_messages(messages)
        max_tokens = allowed.pop("max_tokens", allowed.pop("max_output_tokens", 32))
        request: dict[str, Any] = {
            **allowed,
            "model": endpoint.model_name,
            "messages": translated,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if system_parts:
            request["system"] = system_parts
        return request

    def build_connection_body(self, endpoint: ModelEndpoint) -> dict[str, object]:
        return {
            **self.safe_defaults(endpoint.default_request_body or {}),
            "model": endpoint.model_name,
            "messages": [{"role": "user", "content": [{"type": "text", "text": "Respond with the single word OK."}]}],
            "max_tokens": 8,
            "stream": False,
        }

    def extract_prediction(self, payload: dict[str, Any]) -> str:
        fragments = [
            part["text"]
            for part in payload.get("content", [])
            if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)
        ]
        if fragments:
            return "".join(fragments)
        raise ValueError("Anthropic response did not contain text content.")


def translate_anthropic_messages(messages: list[object]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    system_parts: list[dict[str, object]] = []
    translated: list[dict[str, object]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Each message must be an object.")
        role = message.get("role")
        content = _translate_content(message.get("content"))
        if role in {"system", "developer"}:
            system_parts.extend(content)
        elif role in {"user", "assistant"}:
            translated.append({"role": role, "content": content})
        else:
            raise ValueError("Anthropic Messages supports system, user, and assistant messages only.")
    return translated, system_parts


def _translate_content(content: object) -> list[dict[str, object]]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if not isinstance(content, list):
        raise ValueError("Message content must be text or a list of content parts.")
    try:
        parts = normalize_content_parts(content)
    except ContentValidationError as error:
        raise ValueError(str(error)) from error
    translated: list[dict[str, object]] = []
    for part in parts:
        if part["type"] == "text":
            translated.append({"type": "text", "text": part["text"]})
        elif part["type"] == "image":
            source = part["source"]
            if not isinstance(source, dict):
                raise ValueError("Anthropic image content requires a source object.")
            if isinstance(source.get("base64_data"), str):
                validate_base64(source["base64_data"])
                translated.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": part["mime_type"], "data": source["base64_data"]},
                    }
                )
            elif isinstance(source.get("url"), str):
                validate_remote_media_url(source["url"])
                translated.append({"type": "image", "source": {"type": "url", "url": source["url"]}})
            else:
                raise ValueError("Anthropic image content requires base64_data or a remote URL.")
        else:
            raise ValueError(f"Anthropic Messages does not support {part['type']} content through this adapter.")
    return translated
