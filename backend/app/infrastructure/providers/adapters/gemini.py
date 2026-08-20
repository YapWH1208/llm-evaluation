from __future__ import annotations

from typing import Any

from app.db.models import ModelEndpoint
from app.infrastructure.providers.adapters.base import ProviderAdapter
from app.infrastructure.providers.common import translate_gemini_messages


class GeminiGenerateContentAdapter(ProviderAdapter):
    profile = "gemini_generate_content"
    capabilities = frozenset({"text_input", "text_output", "system_message", "multi_turn_conversation", "usage_reporting", "image_input", "multiple_images"})

    def path_suffix(self, endpoint: ModelEndpoint) -> str:
        return f"/models/{endpoint.model_name}:generateContent"

    def build_request(self, endpoint: ModelEndpoint, messages: list[object], options: dict[str, object]) -> dict[str, Any]:
        allowed = self.safe_defaults(options)
        contents, system_parts = translate_gemini_messages(messages)
        generation_config = dict(allowed.pop("generationConfig", {})) if isinstance(allowed.get("generationConfig"), dict) else {}
        option_map = {"max_tokens": "maxOutputTokens", "max_output_tokens": "maxOutputTokens", "top_p": "topP", "top_k": "topK"}
        for source, target in option_map.items():
            if source in allowed:
                generation_config[target] = allowed.pop(source)
        if "temperature" in allowed:
            generation_config["temperature"] = allowed.pop("temperature")
        request: dict[str, Any] = {**allowed, "contents": contents}
        if system_parts:
            request["systemInstruction"] = {"parts": system_parts}
        if generation_config:
            request["generationConfig"] = generation_config
        return request

    def build_connection_body(self, endpoint: ModelEndpoint) -> dict[str, object]:
        return {**self.safe_defaults(endpoint.default_request_body or {}), "contents": [{"role": "user", "parts": [{"text": "Respond with the single word OK."}]}], "generationConfig": {"temperature": 0, "maxOutputTokens": 8}}

    def extract_prediction(self, payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates")
        first = candidates[0] if isinstance(candidates, list) and candidates else {}
        fragments = [part["text"] for part in first.get("content", {}).get("parts", []) if isinstance(part, dict) and isinstance(part.get("text"), str)] if isinstance(first, dict) else []
        if fragments:
            return "".join(fragments)
        raise ValueError("Gemini response did not contain text content.")
