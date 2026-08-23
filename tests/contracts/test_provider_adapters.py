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


def _endpoint(profile: str, **overrides: object) -> ModelEndpoint:
    values: dict[str, object] = {
        "display_name": profile,
        "base_url": (
            "https://models.example.test/v1?api-version=2025-01-01"
            if profile == "azure_openai_chat_completions"
            else "https://models.example.test/v1"
        ),
        "model_name": "test-model",
        "protocol_profile": profile,
        "encrypted_api_key": "unused",
        "api_key_mask": "****test",
    }
    values.update(overrides)
    return ModelEndpoint(**values)


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
    ("profile", "header", "value"),
    (
        ("openai_chat_completions", "Authorization", "Bearer secret"),
        ("openai_responses", "Authorization", "Bearer secret"),
        ("anthropic_messages", "x-api-key", "secret"),
        ("gemini_generate_content", "x-goog-api-key", "secret"),
        ("azure_openai_chat_completions", "api-key", "secret"),
        ("ollama_chat", "Authorization", "Bearer secret"),
        ("custom_http_json", "Authorization", "Bearer secret"),
    ),
)
def test_each_adapter_owns_its_authentication_headers(profile: str, header: str, value: str) -> None:
    endpoint = _endpoint(profile)
    headers = ProviderRegistry().for_endpoint(endpoint).headers(endpoint, "secret")

    assert headers[header] == value
    if profile == "anthropic_messages":
        assert headers["anthropic-version"] == "2023-06-01"


def test_ollama_adapter_explicitly_allows_anonymous_loopback() -> None:
    adapter = ProviderRegistry().for_profile("ollama_chat")

    assert adapter.allow_loopback is True
    assert adapter.headers(_endpoint("ollama_chat"), "") == {}


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


@pytest.mark.parametrize(
    ("profile", "legacy_defaults", "output_path", "reasoning_path"),
    (
        (
            "openai_chat_completions",
            {"max_tokens": 22, "reasoning_effort": "low"},
            ("max_completion_tokens",),
            ("reasoning_effort",),
        ),
        (
            "azure_openai_chat_completions",
            {"max_tokens": 22, "reasoning_effort": "low"},
            ("max_completion_tokens",),
            ("reasoning_effort",),
        ),
        (
            "openai_responses",
            {"max_tokens": 22, "reasoning_effort": "low"},
            ("max_output_tokens",),
            ("reasoning", "effort"),
        ),
        (
            "anthropic_messages",
            {"max_output_tokens": 22, "reasoning_effort": "low"},
            ("max_tokens",),
            ("output_config", "effort"),
        ),
        (
            "gemini_generate_content",
            {"max_tokens": 22, "reasoning_effort": "low"},
            ("generationConfig", "maxOutputTokens"),
            ("generationConfig", "thinkingConfig", "thinkingLevel"),
        ),
        (
            "ollama_chat",
            {"max_tokens": 22, "think": "low"},
            ("options", "num_predict"),
            ("think",),
        ),
    ),
)
def test_adapters_translate_typed_reasoning_defaults_and_replace_legacy_model_defaults(
    profile: str,
    legacy_defaults: dict[str, object],
    output_path: tuple[str, ...],
    reasoning_path: tuple[str, ...],
) -> None:
    endpoint = _endpoint(
        profile,
        default_request_body=legacy_defaults,
        reasoning_effort="high",
        max_output_tokens=77,
    )
    adapter = ProviderRegistry().for_endpoint(endpoint)
    from app.infrastructure.providers.common import resolve_request_body

    evidence = resolve_request_body(
        protocol_profile=profile,
        model_defaults=adapter.endpoint_request_defaults(endpoint),
        equivalent_field_groups=adapter.equivalent_request_field_groups(),
    )
    request = adapter.build_request_with_options(
        endpoint, [{"role": "user", "content": "hello"}], evidence["effective_request_body"]
    )

    assert _path(request.body, output_path) == 77
    assert _path(request.body, reasoning_path) == "high"
    for alias in adapter.max_output_token_aliases:
        if alias != output_path:
            assert _path(request.body, alias) is _MISSING
    for alias in adapter.reasoning_effort_aliases:
        if alias != reasoning_path:
            assert _path(request.body, alias) is _MISSING


def test_custom_http_keeps_typed_defaults_as_metadata_and_preserves_raw_defaults() -> None:
    endpoint = _endpoint(
        "custom_http_json",
        default_request_body={"max_tokens": 22, "reasoning_effort": "low"},
        reasoning_effort="high",
        max_output_tokens=77,
    )
    adapter = ProviderRegistry().for_endpoint(endpoint)

    assert adapter.endpoint_request_defaults(endpoint) == {"max_tokens": 22, "reasoning_effort": "low"}


def test_later_request_layers_override_typed_endpoint_defaults() -> None:
    from app.infrastructure.providers.common import resolve_request_body

    endpoint = _endpoint(
        "openai_chat_completions",
        default_request_body={"max_tokens": 22},
        max_output_tokens=77,
    )
    adapter = ProviderRegistry().for_endpoint(endpoint)
    evidence = resolve_request_body(
        protocol_profile=adapter.profile,
        model_defaults=adapter.endpoint_request_defaults(endpoint),
        run_override={"max_tokens": 5},
        equivalent_field_groups=adapter.equivalent_request_field_groups(),
    )

    assert evidence["effective_request_body"]["max_tokens"] == 5
    assert "max_completion_tokens" not in evidence["effective_request_body"]


_MISSING = object()


def _path(value: object, path: tuple[str, ...]) -> object:
    current = value
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return _MISSING
        current = current[key]
    return current


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
