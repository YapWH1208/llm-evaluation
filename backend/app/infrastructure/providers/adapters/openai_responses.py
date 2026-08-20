from __future__ import annotations

from typing import Any

from app.core.content import ContentValidationError, normalize_content_parts
from app.db.models import ModelEndpoint
from app.infrastructure.providers.adapters.base import ProviderAdapter
from app.infrastructure.providers.common import (
    source_as_data_or_remote_url,
    validate_base64,
    validate_remote_media_url,
)


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


def translate_responses_messages(messages: list[object]) -> list[dict[str, object]]:
    translated: list[dict[str, object]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Each message must be an object.")
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant", "system", "developer"}:
            raise ValueError("Responses API messages require a user, assistant, system, or developer role.")
        if isinstance(content, str):
            parts = [{"type": "input_text", "text": content}]
            tool_results: list[dict[str, object]] = []
        else:
            try:
                normalized = normalize_content_parts(content) if isinstance(content, list) else None
            except ContentValidationError as error:
                raise ValueError(str(error)) from error
            if normalized is None:
                raise ValueError("Message content must be text or a list of content parts.")
            parts = [_translate_part(part) for part in normalized if part["type"] != "tool_result"]
            tool_results = [
                {"type": "function_call_output", "call_id": part["tool_call_id"], "output": part["content"]}
                for part in normalized
                if part["type"] == "tool_result"
            ]
        if parts:
            translated.append({"role": role, "content": parts})
        translated.extend(tool_results)
    return translated


def _translate_part(part: dict[str, Any]) -> dict[str, object]:
    part_type = part["type"]
    if part_type == "text":
        return {"type": "input_text", "text": part["text"]}
    if part_type == "image":
        return {"type": "input_image", "image_url": source_as_data_or_remote_url(part)}
    if part_type == "audio":
        source = part["source"]
        encoded = source.get("base64_data") if isinstance(source, dict) else None
        if not isinstance(encoded, str):
            raise ValueError("Responses API audio content requires base64_data.")
        validate_base64(encoded)
        audio_format = part["mime_type"].split("/", 1)[1]
        if audio_format == "mpeg":
            audio_format = "mp3"
        if audio_format not in {"wav", "mp3"}:
            raise ValueError("Responses API audio supports WAV or MP3 content only.")
        return {"type": "input_audio", "input_audio": {"data": encoded, "format": audio_format}}
    if part_type in {"file", "video"}:
        source = part["source"]
        if not isinstance(source, dict):
            raise ValueError("File and video content parts require a source object.")
        filename = "input-video" if part_type == "video" else "input-file"
        if isinstance(source.get("url"), str):
            validate_remote_media_url(source["url"])
            return {"type": "input_file", "file_url": source["url"], "filename": filename}
        if isinstance(source.get("base64_data"), str):
            validate_base64(source["base64_data"])
            return {"type": "input_file", "file_data": source["base64_data"], "filename": filename}
        raise ValueError("Responses API file and video content requires base64_data or a remote URL.")
    raise ValueError(f"Responses API does not support {part_type} content through this adapter.")
