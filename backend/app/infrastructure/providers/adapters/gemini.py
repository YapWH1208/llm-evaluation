from __future__ import annotations

from typing import Any

from app.core.content import ContentValidationError, normalize_content_parts
from app.db.models import ModelEndpoint
from app.infrastructure.providers.adapters.base import ProviderAdapter
from app.infrastructure.providers.common import nonnegative_int, validate_base64


class GeminiGenerateContentAdapter(ProviderAdapter):
    profile = "gemini_generate_content"
    credential_header = "x-goog-api-key"
    credential_prefix = ""
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
        return f"/models/{endpoint.model_name}:generateContent"

    def build_request(
        self, endpoint: ModelEndpoint, messages: list[object], options: dict[str, object]
    ) -> dict[str, Any]:
        allowed = self.safe_defaults(options)
        contents, system_parts = translate_gemini_messages(messages)
        generation_config = (
            dict(allowed.pop("generationConfig", {})) if isinstance(allowed.get("generationConfig"), dict) else {}
        )
        option_map = {
            "max_tokens": "maxOutputTokens",
            "max_output_tokens": "maxOutputTokens",
            "top_p": "topP",
            "top_k": "topK",
        }
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
        return {
            **self.safe_defaults(endpoint.default_request_body or {}),
            "contents": [{"role": "user", "parts": [{"text": "Respond with the single word OK."}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 8},
        }

    def extract_prediction(self, payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates")
        first = candidates[0] if isinstance(candidates, list) and candidates else {}
        fragments = (
            [
                part["text"]
                for part in first.get("content", {}).get("parts", [])
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            ]
            if isinstance(first, dict)
            else []
        )
        if fragments:
            return "".join(fragments)
        raise ValueError("Gemini response did not contain text content.")

    def request_defaults(self) -> dict[str, object]:
        return {"max_output_tokens": 32, "temperature": 0}

    def extract_usage(self, payload: dict[str, Any]) -> tuple[int | None, int | None]:
        usage = payload.get("usageMetadata")
        if not isinstance(usage, dict):
            return None, None
        return nonnegative_int(usage.get("promptTokenCount")), nonnegative_int(usage.get("candidatesTokenCount"))


def translate_gemini_messages(messages: list[object]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    contents: list[dict[str, object]] = []
    system_parts: list[dict[str, object]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Each message must be an object.")
        role = message.get("role")
        parts = _translate_content(message.get("content"))
        if role in {"system", "developer"}:
            system_parts.extend(parts)
        elif role == "assistant":
            contents.append({"role": "model", "parts": parts})
        elif role == "user":
            contents.append({"role": "user", "parts": parts})
        else:
            raise ValueError("Gemini GenerateContent supports system, user, and assistant messages only.")
    return contents, system_parts


def _translate_content(content: object) -> list[dict[str, object]]:
    if isinstance(content, str):
        return [{"text": content}]
    if not isinstance(content, list):
        raise ValueError("Message content must be text or a list of content parts.")
    try:
        parts = normalize_content_parts(content)
    except ContentValidationError as error:
        raise ValueError(str(error)) from error
    translated: list[dict[str, object]] = []
    for part in parts:
        if part["type"] == "text":
            translated.append({"text": part["text"]})
            continue
        if part["type"] == "tool_result":
            raise ValueError("Gemini GenerateContent does not support tool_result content through this adapter.")
        source = part["source"]
        encoded = source.get("base64_data") if isinstance(source, dict) else None
        if not isinstance(encoded, str):
            raise ValueError(f"Gemini {part['type']} content requires base64_data through this adapter.")
        validate_base64(encoded)
        translated.append({"inlineData": {"mimeType": part["mime_type"], "data": encoded}})
    return translated
