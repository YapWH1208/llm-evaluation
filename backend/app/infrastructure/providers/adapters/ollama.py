from __future__ import annotations

import math
from typing import Any

from app.db.models import ModelEndpoint
from app.infrastructure.providers.adapters.base import ProviderAdapter
from app.infrastructure.providers.common import nonnegative_int, translate_ollama_messages


class OllamaChatAdapter(ProviderAdapter):
    profile = "ollama_chat"
    allow_loopback = True
    omit_empty_credential = True
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
        return "/api/chat"

    def build_request(
        self, endpoint: ModelEndpoint, messages: list[object], options: dict[str, object]
    ) -> dict[str, Any]:
        allowed = self.safe_defaults(options)
        request_options = dict(allowed.pop("options", {})) if isinstance(allowed.get("options"), dict) else {}
        option_map = {
            "max_tokens": "num_predict",
            "max_output_tokens": "num_predict",
            "top_p": "top_p",
            "top_k": "top_k",
            "temperature": "temperature",
            "seed": "seed",
        }
        for source, target in option_map.items():
            if source in allowed:
                request_options[target] = allowed.pop(source)
        request: dict[str, Any] = {
            **allowed,
            "model": endpoint.model_name,
            "messages": translate_ollama_messages(messages),
            "stream": False,
        }
        if request_options:
            request["options"] = request_options
        return request

    def build_connection_body(self, endpoint: ModelEndpoint) -> dict[str, object]:
        return {
            **self.safe_defaults(endpoint.default_request_body or {}),
            "model": endpoint.model_name,
            "messages": [{"role": "user", "content": "Respond with the single word OK."}],
            "options": {"temperature": 0, "num_predict": 8},
            "stream": False,
        }

    def extract_prediction(self, payload: dict[str, Any]) -> str:
        message = payload.get("message")
        prediction = message.get("content") if isinstance(message, dict) else None
        if isinstance(prediction, str):
            return prediction
        raise ValueError("Ollama response did not contain text content.")

    def extract_usage(self, payload: dict[str, Any]) -> tuple[int | None, int | None]:
        return nonnegative_int(payload.get("prompt_eval_count")), nonnegative_int(payload.get("eval_count"))

    def extract_token_logprobs(self, payload: dict[str, Any]) -> tuple[float, ...] | None:
        return self.parse_logprobs(payload.get("logprobs"))

    @staticmethod
    def parse_logprobs(candidates: object) -> tuple[float, ...] | None:
        if not isinstance(candidates, list) or not candidates:
            return None
        values: list[float] = []
        for candidate in candidates:
            value = candidate.get("logprob") if isinstance(candidate, dict) else None
            if (
                not isinstance(value, int | float)
                or isinstance(value, bool)
                or not math.isfinite(float(value))
                or float(value) > 0
            ):
                return None
            values.append(float(value))
        return tuple(values)
