from __future__ import annotations

import math
from typing import Any

from app.db.models import ModelEndpoint
from app.infrastructure.providers.adapters.base import ProviderAdapter
from app.infrastructure.providers.adapters.chat_content import translate_chat_messages


class OpenAIChatCompletionsAdapter(ProviderAdapter):
    profile = "openai_chat_completions"
    capabilities = frozenset(
        {
            "text_input",
            "text_output",
            "system_message",
            "multi_turn_conversation",
            "usage_reporting",
            "image_input",
            "audio_input",
            "multiple_images",
            "multiple_audio_files",
            "mixed_media_input",
            "tool_calling",
            "parallel_tool_calling",
            "structured_output",
            "json_mode",
            "json_schema",
            "streaming",
            "seed",
            "logprobs",
        }
    )

    def path_suffix(self, endpoint: ModelEndpoint) -> str:
        return "/chat/completions"

    def build_request(
        self, endpoint: ModelEndpoint, messages: list[object], options: dict[str, object]
    ) -> dict[str, Any]:
        return {
            **self.safe_defaults(options),
            "model": endpoint.model_name,
            "messages": translate_chat_messages(messages),
            "stream": False,
        }

    def build_connection_body(self, endpoint: ModelEndpoint) -> dict[str, object]:
        return {
            **self.safe_defaults(endpoint.default_request_body or {}),
            "model": endpoint.model_name,
            "messages": [{"role": "user", "content": "Respond with the single word OK."}],
            "temperature": 0,
            "max_tokens": 8,
            "stream": False,
        }

    def extract_prediction(self, payload: dict[str, Any]) -> str:
        prediction = payload["choices"][0]["message"]["content"]
        if not isinstance(prediction, str):
            raise ValueError("Chat Completions response did not contain text content.")
        return prediction

    def extract_token_logprobs(self, payload: dict[str, Any]) -> tuple[float, ...] | None:
        choices = payload.get("choices")
        first = choices[0] if isinstance(choices, list) and choices else None
        logprobs = first.get("logprobs") if isinstance(first, dict) else None
        candidates = logprobs.get("content") if isinstance(logprobs, dict) else None
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


class AzureOpenAIChatAdapter(OpenAIChatCompletionsAdapter):
    profile = "azure_openai_chat_completions"
    credential_header = "api-key"
    credential_prefix = ""
