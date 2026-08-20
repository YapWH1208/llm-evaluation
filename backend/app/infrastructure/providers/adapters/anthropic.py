from __future__ import annotations

from typing import Any

from app.db.models import ModelEndpoint
from app.infrastructure.providers.adapters.base import ProviderAdapter
from app.infrastructure.providers.common import translate_anthropic_messages


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
