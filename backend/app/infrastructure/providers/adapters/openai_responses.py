from __future__ import annotations

from typing import Any

from app.db.models import ModelEndpoint
from app.infrastructure.providers.adapters.base import ProviderAdapter
from app.infrastructure.providers.common import translate_responses_messages


class OpenAIResponsesAdapter(ProviderAdapter):
    profile = "openai_responses"
    output_token_option = "max_output_tokens"
    capabilities = frozenset(
        {
            "text_input",
            "text_output",
            "system_message",
            "multi_turn_conversation",
            "usage_reporting",
            "image_input",
            "audio_input",
            "video_input",
            "multiple_images",
            "multiple_audio_files",
            "multiple_videos",
            "mixed_media_input",
        }
    )

    def path_suffix(self, endpoint: ModelEndpoint) -> str:
        return "/responses"

    def build_request(
        self, endpoint: ModelEndpoint, messages: list[object], options: dict[str, object]
    ) -> dict[str, Any]:
        return {
            **self.safe_defaults(options),
            "model": endpoint.model_name,
            "input": translate_responses_messages(messages),
            "stream": False,
            "store": False,
        }

    def build_connection_body(self, endpoint: ModelEndpoint) -> dict[str, object]:
        return {
            **self.safe_defaults(endpoint.default_request_body or {}),
            "model": endpoint.model_name,
            "input": [
                {"role": "user", "content": [{"type": "input_text", "text": "Respond with the single word OK."}]}
            ],
            "max_output_tokens": 8,
            "stream": False,
            "store": False,
        }

    def extract_prediction(self, payload: dict[str, Any]) -> str:
        output_text = payload.get("output_text")
        if isinstance(output_text, str):
            return output_text
        fragments = [
            part["text"]
            for item in payload.get("output", [])
            if isinstance(item, dict) and item.get("type") == "message"
            for part in item.get("content", [])
            if isinstance(part, dict) and part.get("type") == "output_text" and isinstance(part.get("text"), str)
        ]
        if fragments:
            return "".join(fragments)
        raise ValueError("Responses API response did not contain output text.")

    def request_defaults(self) -> dict[str, object]:
        return {"max_output_tokens": 32, "store": False}
