from __future__ import annotations

from typing import Any

from app.db.models import ModelEndpoint
from app.infrastructure.providers.adapters.base import ProviderAdapter
from app.infrastructure.providers.common import translate_chat_messages


class CustomHttpJsonAdapter(ProviderAdapter):
    profile = "custom_http_json"
    capabilities = frozenset({"text_input", "text_output"})

    def path_suffix(self, endpoint: ModelEndpoint) -> None:
        return None

    def build_request(self, endpoint: ModelEndpoint, messages: list[object], options: dict[str, object]) -> dict[str, Any]:
        return {**self.safe_defaults(options), "model": endpoint.model_name, "messages": translate_chat_messages(messages), "stream": False}

    def build_connection_body(self, endpoint: ModelEndpoint) -> dict[str, object]:
        return {**self.safe_defaults(endpoint.default_request_body or {}), "model": endpoint.model_name, "messages": [{"role": "user", "content": "Respond with the single word OK."}], "temperature": 0, "max_tokens": 8, "stream": False}

    def extract_prediction(self, payload: dict[str, Any]) -> str:
        for key in ("output_text", "text", "response", "prediction"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
        choices = payload.get("choices")
        first = choices[0] if isinstance(choices, list) and choices else {}
        message = first.get("message") if isinstance(first, dict) else None
        prediction = message.get("content") if isinstance(message, dict) else None
        if isinstance(prediction, str):
            return prediction
        raise ValueError("Custom JSON response did not contain text content.")
