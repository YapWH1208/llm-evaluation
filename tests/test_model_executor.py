import json

import httpx

from app.db.models import ModelEndpoint
from app.services.model_executor import OpenAIChatCompletionsExecutor


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
        ]}]},
    )
    assert result.success is True
    assert result.prediction == "accepted"
    assert (result.input_tokens, result.output_tokens) == (15, 4)
