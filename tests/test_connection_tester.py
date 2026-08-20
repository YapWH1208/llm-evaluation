import json
from pathlib import Path

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db import ModelEndpoint
from app.main import create_app
from app.infrastructure.providers.connection import ProviderConnectionTester
from app.infrastructure.providers.contracts import ConnectionTestResult


@pytest.fixture(autouse=True)
def public_provider_dns(monkeypatch):
    monkeypatch.setattr(
        "app.infrastructure.network.outbound.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 0))],
    )


def test_openai_connection_probe_uses_a_small_protected_request() -> None:
    observed_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_request
        observed_request = request
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    endpoint = ModelEndpoint(
        display_name="Test",
        base_url="https://models.example.test/v1",
        model_name="test-model",
        encrypted_api_key="not-used-by-the-tester",
        api_key_mask="鈥⑩€⑩€⑩€ey",
        default_request_body={"temperature": 0.8, "model": "must-not-be-used"},
    )

    result = ProviderConnectionTester(transport=httpx.MockTransport(handler)).test(
        endpoint,
        "test-secret-key",
    )

    assert result == ConnectionTestResult(True, "Connection succeeded.", 200)
    assert observed_request is not None
    assert observed_request.url == "https://models.example.test/v1/chat/completions"
    assert observed_request.headers["Authorization"] == "Bearer test-secret-key"
    assert json.loads(observed_request.content) == {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Respond with the single word OK."}],
        "temperature": 0,
        "max_tokens": 8,
        "stream": False,
    }


def test_responses_connection_probe_uses_responses_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://models.example.test/v1/responses"
        assert json.loads(request.content) == {
            "model": "responses-model",
            "input": [
                {"role": "user", "content": [{"type": "input_text", "text": "Respond with the single word OK."}]}
            ],
            "max_output_tokens": 8,
            "stream": False,
            "store": False,
        }
        return httpx.Response(200, json={"output_text": "OK"})

    endpoint = ModelEndpoint(
        display_name="Responses",
        base_url="https://models.example.test/v1",
        model_name="responses-model",
        protocol_profile="openai_responses",
        encrypted_api_key="not-used",
        api_key_mask="****test",
    )
    result = ProviderConnectionTester(transport=httpx.MockTransport(handler)).test(endpoint, "secret")
    assert result == ConnectionTestResult(True, "Connection succeeded.", 200)


def test_connection_probe_accepts_a_successful_provider_response_without_evaluation_payload() -> None:
    endpoint = ModelEndpoint(
        display_name="Provider-specific response",
        base_url="https://models.example.test/v1",
        model_name="test-model",
        encrypted_api_key="not-used",
        api_key_mask="****test",
    )

    result = ProviderConnectionTester(
        httpx.MockTransport(lambda _request: httpx.Response(200, json={"status": "ok", "request_id": "provider-123"}))
    ).test(endpoint, "secret")

    assert result == ConnectionTestResult(True, "Connection succeeded.", 200)


def test_connection_probe_adapts_anthropic_messages_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://models.example.test/v1/messages"
        assert request.headers["x-api-key"] == "secret"
        assert json.loads(request.content) == {
            "model": "claude-test",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "Respond with the single word OK."}]}],
            "max_tokens": 8,
            "stream": False,
        }
        return httpx.Response(200, json={"content": [{"type": "text", "text": "OK"}]})

    endpoint = ModelEndpoint(
        display_name="Anthropic",
        base_url="https://models.example.test",
        model_name="claude-test",
        protocol_profile="anthropic_messages",
        encrypted_api_key="not-used",
        api_key_mask="****test",
    )
    result = ProviderConnectionTester(transport=httpx.MockTransport(handler)).test(endpoint, "secret")
    assert result == ConnectionTestResult(True, "Connection succeeded.", 200)


def test_connection_probe_rejects_restricted_dns_and_oversized_responses(monkeypatch) -> None:
    called = False

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    endpoint = ModelEndpoint(
        display_name="Restricted",
        base_url="https://models.example.test/v1",
        model_name="model",
        encrypted_api_key="unused",
        api_key_mask="****",
    )
    monkeypatch.setattr(
        "app.infrastructure.network.outbound.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("127.0.0.1", 0))],
    )
    restricted = ProviderConnectionTester(transport=httpx.MockTransport(handler)).test(endpoint, "secret")
    assert restricted.success is False
    assert "restricted network" in restricted.message
    assert called is False

    monkeypatch.setattr(
        "app.infrastructure.network.outbound.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 0))],
    )
    oversized = ProviderConnectionTester(
        httpx.MockTransport(lambda _request: httpx.Response(200, content=b"x" * 32)),
        max_response_bytes=16,
    ).test(endpoint, "secret")
    assert oversized.success is False
    assert "byte limit" in oversized.message


def test_connection_probe_route_persists_a_safe_status(tmp_path: Path) -> None:
    class SuccessfulTester:
        def test(self, endpoint: ModelEndpoint, api_key: str) -> ConnectionTestResult:
            assert endpoint.model_name == "example-model"
            assert api_key == "test-secret-key"
            return ConnectionTestResult(True, "Connection succeeded.", 200)

    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        ),
        connection_tester=SuccessfulTester(),
    )

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models.example.test/v1",
                "api_key": "test-secret-key",
                "model_name": "example-model",
            },
        )
        endpoint_id = created.json()["id"]

        probe = client.post(f"/api/v1/model-endpoints/{endpoint_id}/connection-test")
        assert probe.status_code == 200
        assert probe.json() == {
            "success": True,
            "status": "available",
            "message": "Connection succeeded.",
            "provider_status_code": 200,
            "tested_at": probe.json()["tested_at"],
            "request": {
                "method": "POST",
                "url": "https://models.example.test/v1/chat/completions",
                "body": {
                    "model": "example-model",
                    "messages": [{"role": "user", "content": "Respond with the single word OK."}],
                    "temperature": 0,
                    "max_tokens": 8,
                    "stream": False,
                },
            },
        }

        with app.state.database.get_session() as session:
            stored = session.scalar(select(ModelEndpoint).where(ModelEndpoint.id == endpoint_id))
            assert stored is not None
            assert stored.status == "available"
            assert stored.last_connection_error is None
            assert stored.last_tested_at is not None


def test_connection_probe_rejects_non_json_successful_response() -> None:
    endpoint = ModelEndpoint(
        display_name="HTML page",
        base_url="https://models.example.test/v1",
        model_name="test-model",
        encrypted_api_key="not-used",
        api_key_mask="****test",
    )
    result = ProviderConnectionTester(
        httpx.MockTransport(lambda _request: httpx.Response(200, content=b"<html><body>ok</body></html>"))
    ).test(endpoint, "secret")
    assert result.success is False
    assert "non-JSON" in result.message


def test_connection_probe_accepts_an_empty_successful_response() -> None:
    endpoint = ModelEndpoint(
        display_name="Empty body",
        base_url="https://models.example.test/v1",
        model_name="test-model",
        encrypted_api_key="not-used",
        api_key_mask="****test",
    )
    result = ProviderConnectionTester(httpx.MockTransport(lambda _request: httpx.Response(200, content=b""))).test(
        endpoint, "secret"
    )
    assert result == ConnectionTestResult(True, "Connection succeeded.", 200)


def test_connection_probe_omits_sensitive_default_body_keys() -> None:
    observed_body: dict[str, object] | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_body
        observed_body = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    endpoint = ModelEndpoint(
        display_name="Stashed keys",
        base_url="https://models.example.test/v1",
        model_name="test-model",
        encrypted_api_key="not-used",
        api_key_mask="****test",
        default_request_body={"api_key": "stashed-secret", "secret_token": "stashed-token", "temperature": 0.5},
    )
    result = ProviderConnectionTester(transport=httpx.MockTransport(handler)).test(endpoint, "secret")
    assert result.success is True
    assert observed_body is not None
    assert "api_key" not in observed_body
    assert "secret_token" not in observed_body
    assert observed_body["temperature"] == 0
