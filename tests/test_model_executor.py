import json

import httpx

from app.db.models import ModelEndpoint
from app.services.model_executor import OpenAIChatCompletionsExecutor
from app.services.request_body import resolve_request_body


def test_request_body_resolution_records_layer_precedence_and_protected_fields() -> None:
    evidence = resolve_request_body(
        protocol_profile="openai_chat_completions",
        model_defaults={"temperature": 0.8, "generation": {"top_p": 0.6}, "model": "blocked"},
        suite_defaults={"temperature": 0.5, "generation": {"seed": 7}, "messages": "blocked"},
        benchmark_defaults={"generation": {"top_p": 0.9}},
        run_override={"temperature": 0.3, "generation": {"seed": 11}},
        benchmark_forced={"temperature": 0, "response_schema": {"strict": True}},
    )

    assert evidence["effective_request_body"] == {
        "temperature": 0,
        "max_tokens": 32,
        "generation": {"top_p": 0.9, "seed": 11},
        "response_schema": {"strict": True},
    }
    assert {item["field"] for item in evidence["ignored_fields"]} == {"model", "messages"}
    assert any(item["field"] == "temperature" and item["new_layer"] == "benchmark_forced" for item in evidence["overridden_fields"])


def test_executor_sends_effective_request_body_and_persists_merge_evidence() -> None:
    evidence = resolve_request_body(
        protocol_profile="openai_chat_completions",
        model_defaults={"temperature": 0.7},
        suite_defaults={"temperature": 0.2},
        run_override={"top_p": 0.9},
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["temperature"] == 0.2
        assert body["top_p"] == 0.9
        assert "_evaluation" not in body
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    endpoint = ModelEndpoint(display_name="hierarchy", base_url="https://models.example.test/v1", model_name="model", encrypted_api_key="unused", api_key_mask="****test", default_request_body={"temperature": 0.7})
    result = OpenAIChatCompletionsExecutor(httpx.MockTransport(handler)).execute(
        endpoint,
        "secret",
        {"messages": [{"role": "user", "content": "hello"}], "request_body_evidence": evidence},
    )

    assert result.success is True
    assert result.request_snapshot["_evaluation"]["request_body_evidence"] == evidence


def test_openai_executor_records_provider_usage_and_latency() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["model"] == "model"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "OK"}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 3},
            },
        )

    endpoint = ModelEndpoint(
        display_name="executor test",
        base_url="https://models.example.test/v1",
        model_name="model",
        encrypted_api_key="unused",
        api_key_mask="****test",
    )
    result = OpenAIChatCompletionsExecutor(httpx.MockTransport(handler)).execute(
        endpoint,
        "secret",
        {"messages": [{"role": "user", "content": "hello"}]},
    )
    assert result.success is True
    assert result.input_tokens == 11
    assert result.output_tokens == 3
    assert result.latency_ms is not None and result.latency_ms >= 0


def test_openai_executor_includes_safe_endpoint_headers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret"
        assert request.headers["X-Project"] == "demo"
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    endpoint = ModelEndpoint(display_name="headers", base_url="https://models.example.test/v1", model_name="model", encrypted_api_key="unused", api_key_mask="****test", custom_headers={"X-Project": "demo"})
    result = OpenAIChatCompletionsExecutor(httpx.MockTransport(handler)).execute(endpoint, "secret", {"messages": [{"role": "user", "content": "hello"}]})
    assert result.success is True


def test_openai_executor_translates_image_and_audio_content_ir() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        content = json.loads(request.content)["messages"][0]["content"]
        assert content == [
            {"type": "text", "text": "Describe this input"},
            {"type": "image_url", "image_url": {"url": "https://media.example.test/photo.png"}},
            {"type": "input_audio", "input_audio": {"data": "aGVsbG8=", "format": "mp3"}},
        ]
        return httpx.Response(200, json={"choices": [{"message": {"content": "description"}}]})

    endpoint = ModelEndpoint(
        display_name="multimodal executor test",
        base_url="https://models.example.test/v1",
        model_name="model",
        encrypted_api_key="unused",
        api_key_mask="****test",
    )
    result = OpenAIChatCompletionsExecutor(httpx.MockTransport(handler)).execute(
        endpoint,
        "secret",
        {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this input"},
                        {"type": "image", "source": {"url": "https://media.example.test/photo.png"}, "mime_type": "image/png"},
                        {"type": "audio", "source": {"base64_data": "aGVsbG8="}, "mime_type": "audio/mpeg"},
                    ],
                }
            ]
        },
    )
    assert result.success is True
    assert result.prediction == "description"


def test_openai_executor_rejects_local_remote_media_target() -> None:
    endpoint = ModelEndpoint(
        display_name="executor test",
        base_url="https://models.example.test/v1",
        model_name="model",
        encrypted_api_key="unused",
        api_key_mask="****test",
    )
    result = OpenAIChatCompletionsExecutor().execute(
        endpoint,
        "secret",
        {"messages": [{"role": "user", "content": [{"type": "image", "source": {"url": "http://127.0.0.1/private.png"}, "mime_type": "image/png"}]}]},
    )
    assert result.success is False
    assert result.error_type == "invalid_sample"
    assert "private or local" in (result.error_message or "")


def test_openai_executor_parses_retry_after_from_rate_limited_response() -> None:
    endpoint = ModelEndpoint(
        display_name="executor test",
        base_url="https://models.example.test/v1",
        model_name="model",
        encrypted_api_key="unused",
        api_key_mask="****test",
    )
    result = OpenAIChatCompletionsExecutor(
        httpx.MockTransport(lambda _request: httpx.Response(429, headers={"Retry-After": "12"}))
    ).execute(endpoint, "secret", {"messages": [{"role": "user", "content": "hello"}]})

    assert result.success is False
    assert result.error_type == "http_429"
    assert result.retry_after_seconds == 12


def test_openai_executor_translates_responses_api_multimodal_input_and_output() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://models.example.test/v1/responses"
        assert json.loads(request.content) == {
            "model": "responses-model",
            "input": [{"role": "user", "content": [
                {"type": "input_text", "text": "Review these inputs"},
                {"type": "input_image", "image_url": "https://media.example.test/photo.png"},
                {"type": "input_audio", "input_audio": {"data": "aGVsbG8=", "format": "mp3"}},
                {"type": "input_file", "file_data": "JVBERi0=", "filename": "input-file"},
                {"type": "input_file", "file_data": "AAAA", "filename": "input-video"},
            ]}],
            "stream": False,
            "store": False,
            "max_output_tokens": 32,
        }
        return httpx.Response(200, json={"output": [{"type": "message", "content": [{"type": "output_text", "text": "accepted"}]}], "usage": {"input_tokens": 15, "output_tokens": 4}})

    endpoint = ModelEndpoint(display_name="responses executor test", base_url="https://models.example.test/v1", model_name="responses-model", protocol_profile="openai_responses", encrypted_api_key="unused", api_key_mask="****test")
    result = OpenAIChatCompletionsExecutor(httpx.MockTransport(handler)).execute(
        endpoint,
        "secret",
        {"messages": [{"role": "user", "content": [
            {"type": "text", "text": "Review these inputs"},
            {"type": "image", "source": {"url": "https://media.example.test/photo.png"}, "mime_type": "image/png"},
            {"type": "audio", "source": {"base64_data": "aGVsbG8="}, "mime_type": "audio/mpeg"},
            {"type": "file", "source": {"base64_data": "JVBERi0="}, "mime_type": "application/pdf"},
            {"type": "video", "source": {"base64_data": "AAAA"}, "mime_type": "video/mp4"},
        ]}]},
    )
    assert result.success is True
    assert result.prediction == "accepted"
    assert (result.input_tokens, result.output_tokens) == (15, 4)


def test_responses_executor_translates_tool_results_as_function_outputs() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["input"] == [{"type": "function_call_output", "call_id": "call_1", "output": "tool evidence"}]
        return httpx.Response(200, json={"output_text": "OK"})

    endpoint = ModelEndpoint(display_name="responses", base_url="https://models.example.test/v1", model_name="responses", protocol_profile="openai_responses", encrypted_api_key="unused", api_key_mask="****test")
    result = OpenAIChatCompletionsExecutor(httpx.MockTransport(handler)).execute(endpoint, "secret", {"messages": [{"role": "user", "content": [{"type": "tool_result", "tool_call_id": "call_1", "content": "tool evidence"}]}]})
    assert result.success is True


def test_executor_adapts_anthropic_messages_and_authentication() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://models.example.test/v1/messages"
        assert request.headers["x-api-key"] == "secret"
        assert request.headers["anthropic-version"] == "2023-06-01"
        assert "Authorization" not in request.headers
        assert json.loads(request.content) == {
            "model": "claude-test",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
            "max_tokens": 32,
            "temperature": 0,
            "stream": False,
            "system": [{"type": "text", "text": "Be concise."}],
        }
        return httpx.Response(200, json={"content": [{"type": "text", "text": "OK"}], "usage": {"input_tokens": 5, "output_tokens": 2}})

    endpoint = ModelEndpoint(display_name="Anthropic", base_url="https://models.example.test", model_name="claude-test", protocol_profile="anthropic_messages", encrypted_api_key="unused", api_key_mask="****test")
    result = OpenAIChatCompletionsExecutor(httpx.MockTransport(handler)).execute(endpoint, "secret", {"messages": [{"role": "system", "content": "Be concise."}, {"role": "user", "content": "Hello"}]})
    assert result.success is True
    assert result.prediction == "OK"
    assert (result.input_tokens, result.output_tokens) == (5, 2)


def test_executor_adapts_gemini_generation_and_usage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://models.example.test/v1beta/models/gemini-test:generateContent"
        assert request.headers["x-goog-api-key"] == "secret"
        body = json.loads(request.content)
        assert body["contents"] == [{"role": "user", "parts": [{"text": "Hello"}]}]
        assert body["systemInstruction"] == {"parts": [{"text": "Be concise."}]}
        assert body["generationConfig"] == {"maxOutputTokens": 32, "temperature": 0}
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "OK"}]}}], "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 2}})

    endpoint = ModelEndpoint(display_name="Gemini", base_url="https://models.example.test/v1beta", model_name="gemini-test", protocol_profile="gemini_generate_content", encrypted_api_key="unused", api_key_mask="****test")
    result = OpenAIChatCompletionsExecutor(httpx.MockTransport(handler)).execute(endpoint, "secret", {"messages": [{"role": "system", "content": "Be concise."}, {"role": "user", "content": "Hello"}]})
    assert result.success is True
    assert result.prediction == "OK"
    assert (result.input_tokens, result.output_tokens) == (5, 2)


def test_executor_adapts_azure_openai_and_preserves_api_version_query() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://models.example.test/openai/deployments/demo/chat/completions?api-version=2025-01-01-preview"
        assert request.headers["api-key"] == "secret"
        assert "Authorization" not in request.headers
        assert json.loads(request.content)["messages"] == [{"role": "user", "content": "Hello"}]
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    endpoint = ModelEndpoint(display_name="Azure", base_url="https://models.example.test/openai/deployments/demo?api-version=2025-01-01-preview", model_name="ignored-by-azure", protocol_profile="azure_openai_chat_completions", encrypted_api_key="unused", api_key_mask="****test")
    result = OpenAIChatCompletionsExecutor(httpx.MockTransport(handler)).execute(endpoint, "secret", {"messages": [{"role": "user", "content": "Hello"}]})
    assert result.success is True
    assert result.prediction == "OK"


def test_executor_adapts_ollama_and_does_not_require_bearer_auth() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://models.example.test/api/chat"
        assert "Authorization" not in request.headers
        assert json.loads(request.content) == {"model": "llama", "messages": [{"role": "user", "content": "Hello"}], "stream": False, "options": {"num_predict": 32, "temperature": 0}}
        return httpx.Response(200, json={"message": {"content": "OK"}, "prompt_eval_count": 5, "eval_count": 2})

    endpoint = ModelEndpoint(display_name="Ollama", base_url="https://models.example.test", model_name="llama", protocol_profile="ollama_chat", encrypted_api_key="unused", api_key_mask="****test")
    result = OpenAIChatCompletionsExecutor(httpx.MockTransport(handler)).execute(endpoint, "", {"messages": [{"role": "user", "content": "Hello"}]})
    assert result.success is True
    assert result.prediction == "OK"
    assert (result.input_tokens, result.output_tokens) == (5, 2)


def test_executor_posts_generic_chat_json_to_custom_http_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://models.example.test/evaluate?revision=1"
        assert request.headers["Authorization"] == "Bearer secret"
        assert json.loads(request.content)["messages"] == [{"role": "user", "content": "Hello"}]
        return httpx.Response(200, json={"prediction": "OK"})

    endpoint = ModelEndpoint(display_name="Custom", base_url="https://models.example.test/evaluate?revision=1", model_name="custom", protocol_profile="custom_http_json", encrypted_api_key="unused", api_key_mask="****test")
    result = OpenAIChatCompletionsExecutor(httpx.MockTransport(handler)).execute(endpoint, "secret", {"messages": [{"role": "user", "content": "Hello"}]})
    assert result.success is True
    assert result.prediction == "OK"
