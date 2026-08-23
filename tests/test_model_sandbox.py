import json
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
import httpx
import pytest

from app.core.config import Settings
from app.db.models import ModelEndpoint
from app.infrastructure.providers.contracts import SandboxExecutionResult, SandboxToolCall
from app.infrastructure.providers.sandbox import ProviderSandboxRunner
from app.main import create_app


@pytest.fixture(autouse=True)
def public_provider_dns(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.network.outbound.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 0))],
    )


def _endpoint(profile: str = "openai_chat_completions") -> ModelEndpoint:
    return ModelEndpoint(
        display_name="Sandbox model",
        base_url="https://models.example.test/v1",
        model_name="test-model",
        protocol_profile=profile,
        encrypted_api_key="unused",
        api_key_mask="****test",
    )


def test_sandbox_runner_returns_sanitized_text_evidence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["messages"] == [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Say hello."},
        ]
        assert request.headers["Authorization"] == "Bearer secret"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Hello."}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            },
        )

    result = ProviderSandboxRunner(httpx.MockTransport(handler)).execute(
        _endpoint(), "secret", mode="text", user_prompt="Say hello.", system_prompt="Be concise."
    )

    assert result.success is True
    assert result.final_text == "Hello."
    assert result.tool_calls == ()
    assert result.input_tokens == 4
    assert result.output_tokens == 2
    assert result.provider_status_code == 200
    assert "secret" not in str(result.request_snapshot)
    assert "Authorization" not in str(result.request_snapshot)


def test_sandbox_runner_validates_a_non_executing_tool_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["tool_choice"] == {"type": "function", "function": {"name": "sandbox_echo"}}
        assert body["tools"][0]["function"]["name"] == "sandbox_echo"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "sandbox_echo", "arguments": '{"message":"sandbox"}'},
                                }
                            ]
                        }
                    }
                ]
            },
        )

    result = ProviderSandboxRunner(httpx.MockTransport(handler)).execute(
        _endpoint(), "secret", mode="tool", user_prompt="This input is intentionally ignored.", system_prompt=None
    )

    assert result.success is True
    assert result.final_text is None
    assert result.tool_calls == (SandboxToolCall("sandbox_echo", {"message": "sandbox"}),)


def test_sandbox_runner_validates_a_responses_tool_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["tool_choice"] == {"type": "function", "name": "sandbox_echo"}
        assert body["tools"][0]["name"] == "sandbox_echo"
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "function_call",
                        "name": "sandbox_echo",
                        "arguments": '{"message":"sandbox"}',
                    }
                ]
            },
        )

    result = ProviderSandboxRunner(httpx.MockTransport(handler)).execute(
        _endpoint("openai_responses"), "secret", mode="tool", user_prompt="", system_prompt=None
    )

    assert result.success is True
    assert result.tool_calls == (SandboxToolCall("sandbox_echo", {"message": "sandbox"}),)


def test_sandbox_runner_rejects_unsupported_tool_profiles_before_network() -> None:
    result = ProviderSandboxRunner(
        httpx.MockTransport(lambda _request: pytest.fail("unsupported tool profile made a network request"))
    ).execute(_endpoint("anthropic_messages"), "secret", mode="tool", user_prompt="", system_prompt=None)

    assert result.success is False
    assert result.error_type == "unsupported_tool_calling"
    assert result.request_snapshot == {}


def test_sandbox_runner_returns_safe_transport_failures(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.network.outbound.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("127.0.0.1", 0))],
    )
    result = ProviderSandboxRunner(
        httpx.MockTransport(lambda _request: pytest.fail("unsafe destination made a network request"))
    ).execute(_endpoint(), "secret", mode="text", user_prompt="hello", system_prompt=None)

    assert result.success is False
    assert result.error_type == "unsafe_destination"
    assert result.final_text is None
    assert result.provider_status_code is None


def test_sandbox_route_is_ephemeral_and_does_not_change_endpoint_status(tmp_path: Path) -> None:
    class SandboxRunner:
        def execute(
            self,
            endpoint: ModelEndpoint,
            api_key: str,
            *,
            mode: str,
            user_prompt: str,
            system_prompt: str | None,
        ) -> SandboxExecutionResult:
            assert endpoint.model_name == "test-model"
            assert api_key == "secret"
            assert mode == "text"
            assert user_prompt == "hello"
            assert system_prompt is None
            return SandboxExecutionResult(
                success=True,
                protocol_profile="openai_chat_completions",
                request_snapshot={"model": "test-model", "messages": [{"role": "user", "content": "hello"}]},
                final_text="Hello.",
                tool_calls=(),
                latency_ms=12.5,
                input_tokens=3,
                output_tokens=2,
                provider_status_code=200,
            )

    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode()
        ),
        sandbox_runner=SandboxRunner(),
    )
    with TestClient(app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "test-model"},
        ).json()
        response = client.post(
            f"/api/v1/model-endpoints/{endpoint['id']}/sandbox",
            json={"mode": "text", "user_prompt": "hello"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "mode": "text",
            "protocol_profile": "openai_chat_completions",
            "request": {"model": "test-model", "messages": [{"role": "user", "content": "hello"}]},
            "final_text": "Hello.",
            "tool_calls": [],
            "latency_ms": 12.5,
            "usage": {"input_tokens": 3, "output_tokens": 2},
            "provider_status_code": 200,
            "error_type": None,
            "error_message": None,
        }
        persisted = client.get(f"/api/v1/model-endpoints/{endpoint['id']}").json()
        assert persisted["status"] == "unverified"
        assert client.get(f"/api/v1/model-endpoints/{endpoint['id']}/capabilities").json() == []
