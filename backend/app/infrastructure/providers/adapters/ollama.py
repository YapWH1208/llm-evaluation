from __future__ import annotations

from typing import Any

from app.db.models import ModelEndpoint
from app.infrastructure.providers.adapters.base import ProviderAdapter
from app.infrastructure.providers.common import translate_ollama_messages


class OllamaChatAdapter(ProviderAdapter):
    profile = "ollama_chat"
    capabilities = frozenset({"text_input", "text_output", "system_message", "multi_turn_conversation", "usage_reporting", "image_input", "multiple_images"})

    def path_suffix(self, endpoint: ModelEndpoint) -> str:
        return "/api/chat"

    def build_request(self, endpoint: ModelEndpoint, messages: list[object], options: dict[str, object]) -> dict[str, Any]:
        allowed = self.safe_defaults(options)
        request_options = dict(allowed.pop("options", {})) if isinstance(allowed.get("options"), dict) else {}
        option_map = {"max_tokens": "num_predict", "max_output_tokens": "num_predict", "top_p": "top_p", "top_k": "top_k", "temperature": "temperature", "seed": "seed"}
        for source, target in option_map.items():
            if source in allowed:
                request_options[target] = allowed.pop(source)
        request: dict[str, Any] = {**allowed, "model": endpoint.model_name, "messages": translate_ollama_messages(messages), "stream": False}
        if request_options:
            request["options"] = request_options
        return request

    def build_connection_body(self, endpoint: ModelEndpoint) -> dict[str, object]:
        return {**self.safe_defaults(endpoint.default_request_body or {}), "model": endpoint.model_name, "messages": [{"role": "user", "content": "Respond with the single word OK."}], "options": {"temperature": 0, "num_predict": 8}, "stream": False}

    def extract_prediction(self, payload: dict[str, Any]) -> str:
        message = payload.get("message")
        prediction = message.get("content") if isinstance(message, dict) else None
        if isinstance(prediction, str):
            return prediction
        raise ValueError("Ollama response did not contain text content.")
