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
