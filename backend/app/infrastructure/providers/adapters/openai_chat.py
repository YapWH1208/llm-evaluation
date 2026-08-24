from __future__ import annotations

import math
import json
from typing import Any

from app.db.models import ModelEndpoint
from app.infrastructure.providers.adapters.base import (
    SANDBOX_ECHO_TOOL_DESCRIPTION,
    SANDBOX_ECHO_TOOL_NAME,
    SANDBOX_ECHO_TOOL_PARAMETERS,
    ProviderAdapter,
)
from app.infrastructure.providers.adapters.chat_content import translate_chat_messages
from app.infrastructure.providers.contracts import SandboxToolCall


class OpenAIChatCompletionsAdapter(ProviderAdapter):
    profile = "openai_chat_completions"
    max_output_token_path = ("max_completion_tokens",)
    max_output_token_aliases = (("max_completion_tokens",), ("max_tokens",), ("max_output_tokens",))
    reasoning_effort_path = ("reasoning_effort",)
    reasoning_effort_aliases = (("reasoning_effort",), ("reasoning", "effort"))
    sandbox_tool_calling_supported = True
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
            **self.connection_defaults(endpoint),
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

    def build_sandbox_tool_request(
        self, endpoint: ModelEndpoint, messages: list[object], options: dict[str, object]
    ) -> dict[str, Any]:
        return {
            **self.build_request(endpoint, messages, options),
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": SANDBOX_ECHO_TOOL_NAME,
                        "description": SANDBOX_ECHO_TOOL_DESCRIPTION,
                        "parameters": SANDBOX_ECHO_TOOL_PARAMETERS,
                        "strict": True,
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": SANDBOX_ECHO_TOOL_NAME}},
            "parallel_tool_calls": False,
        }

    def extract_sandbox_tool_calls(self, payload: dict[str, Any]) -> tuple[SandboxToolCall, ...]:
        choices = payload.get("choices")
        first = choices[0] if isinstance(choices, list) and choices else None
        message = first.get("message") if isinstance(first, dict) else None
        raw_calls = message.get("tool_calls") if isinstance(message, dict) else None
        if raw_calls is None:
            return ()
        if not isinstance(raw_calls, list):
            raise ValueError("Chat Completions tool calls were not a list.")
        return _parse_tool_calls(raw_calls)

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


def _parse_tool_calls(raw_calls: list[object]) -> tuple[SandboxToolCall, ...]:
    calls: list[SandboxToolCall] = []
    for item in raw_calls:
        function = item.get("function") if isinstance(item, dict) else None
        name = function.get("name") if isinstance(function, dict) else None
        raw_arguments = function.get("arguments") if isinstance(function, dict) else None
        if not isinstance(name, str) or not isinstance(raw_arguments, str):
            raise ValueError("Chat Completions tool call was missing a function name or JSON arguments.")
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as error:
            raise ValueError("Chat Completions tool call arguments were not valid JSON.") from error
        if not isinstance(arguments, dict):
            raise ValueError("Chat Completions tool call arguments must be a JSON object.")
        calls.append(SandboxToolCall(name, arguments))
    return tuple(calls)
