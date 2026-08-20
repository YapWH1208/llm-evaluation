from __future__ import annotations

import pytest

from app.db.models import ModelEndpoint
from app.infrastructure.providers.registry import ProviderRegistry


PROFILES = (
    "openai_chat_completions",
    "openai_responses",
    "anthropic_messages",
    "gemini_generate_content",
    "azure_openai_chat_completions",
    "ollama_chat",
    "custom_http_json",
)


def _endpoint(profile: str) -> ModelEndpoint:
    return ModelEndpoint(
        display_name=profile,
        base_url="https://models.example.test/v1?api-version=2025-01-01" if profile == "azure_openai_chat_completions" else "https://models.example.test/v1",
        model_name="test-model",
        protocol_profile=profile,
        encrypted_api_key="unused",
        api_key_mask="****test",
    )


@pytest.mark.parametrize("profile", PROFILES)
def test_each_provider_profile_has_one_adapter_for_request_probe_and_response(profile: str) -> None:
    registry = ProviderRegistry()
    endpoint = _endpoint(profile)
    adapter = registry.for_endpoint(endpoint)
    request = adapter.build_request_with_options(endpoint, [{"role": "user", "content": "hello"}], {})
    probe = adapter.build_connection_body(endpoint)

    assert adapter.profile == profile
    assert request.method == "POST"
    assert request.url.startswith("https://models.example.test/")
    assert "api_key" not in request.body
    assert "api_key" not in probe
    assert adapter.extract_prediction(_response_for(profile)) == "OK"


def test_registry_profiles_are_explicit_and_complete() -> None:
    assert ProviderRegistry().profiles == frozenset(PROFILES)


@pytest.mark.parametrize(
    "profile",
    ("openai_chat_completions", "azure_openai_chat_completions", "custom_http_json"),
)
def test_chat_style_adapters_preserve_tool_result_messages(profile: str) -> None:
    endpoint = _endpoint(profile)
    request = (
        ProviderRegistry()
        .for_endpoint(endpoint)
        .build_request_with_options(
            endpoint,
            [
                {
                    "role": "tool",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_call_id": "call_1",
                            "content": "tool evidence",
                        }
                    ],
                }
            ],
            {},
        )
    )

    assert request.body["messages"] == [{"role": "tool", "tool_call_id": "call_1", "content": "tool evidence"}]


@pytest.mark.parametrize(
    "message",
    (
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_call_id": "call_1", "content": "tool evidence"}],
        },
        {
            "role": "tool",
            "content": [
                {"type": "text", "text": "mixed"},
                {"type": "tool_result", "tool_call_id": "call_1", "content": "tool evidence"},
            ],
        },
    ),
    ids=("non-tool-role", "mixed-content"),
)
def test_chat_style_adapter_rejects_non_standalone_tool_results(message: dict[str, object]) -> None:
    endpoint = _endpoint("openai_chat_completions")

    with pytest.raises(ValueError, match="standalone message with role tool"):
        ProviderRegistry().for_endpoint(endpoint).build_request_with_options(endpoint, [message], {})


def test_gemini_adapter_rejects_tool_result_messages_explicitly() -> None:
    endpoint = _endpoint("gemini_generate_content")

    with pytest.raises(ValueError, match="does not support tool_result"):
        ProviderRegistry().for_endpoint(endpoint).build_request_with_options(
            endpoint,
            [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_call_id": "call_1",
                            "content": "tool evidence",
                        }
                    ],
                }
            ],
            {},
        )


def _response_for(profile: str) -> dict[str, object]:
    if profile in {"openai_chat_completions", "azure_openai_chat_completions"}:
        return {"choices": [{"message": {"content": "OK"}}]}
    if profile == "openai_responses":
        return {"output_text": "OK"}
    if profile == "anthropic_messages":
        return {"content": [{"type": "text", "text": "OK"}]}
    if profile == "gemini_generate_content":
        return {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}
    if profile == "ollama_chat":
        return {"message": {"content": "OK"}}
    return {"prediction": "OK"}
