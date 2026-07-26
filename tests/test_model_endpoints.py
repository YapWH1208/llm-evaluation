from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.core.secrets import SecretCipher
from app.db import ModelEndpoint
from app.main import create_app


def test_model_endpoint_crud_encrypts_the_api_key(tmp_path: Path) -> None:
    database_path = tmp_path / "platform.db"
    encryption_key = Fernet.generate_key().decode("utf-8")
    app = create_app(
        Settings(
            database_url=f"sqlite:///{database_path}",
            secret_encryption_key=encryption_key,
        )
    )

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/model-endpoints",
            json={
                "display_name": "Local model",
                "base_url": "https://models.example.test/v1/",
                "api_key": "test-secret-key",
                "model_name": "example-model",
                "default_request_body": {"temperature": 0},
                "max_concurrency": 3,
                "api_key_max_concurrency": 2,
                "requests_per_second": 5,
                "requests_per_minute": 120,
                "input_tokens_per_minute": 7000,
                "output_tokens_per_minute": 3000,
            },
        )
        assert created.status_code == 201
        created_body = created.json()
        endpoint_id = created_body["id"]
        assert created_body["base_url"] == "https://models.example.test/v1"
        assert created_body["api_key_mask"] == "••••-key"
        assert "api_key" not in created_body
        assert "encrypted_api_key" not in created_body
        assert created_body["requests_per_second"] == 5
        assert created_body["input_tokens_per_minute"] == 7000
        assert created_body["api_key_max_concurrency"] == 2

        listed = client.get("/api/v1/model-endpoints")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [endpoint_id]

        updated = client.patch(
            f"/api/v1/model-endpoints/{endpoint_id}",
            json={"api_key": "replacement-secret", "tokens_per_minute": 9000, "output_tokens_per_minute": 4000},
        )
        assert updated.status_code == 200
        assert updated.json()["api_key_mask"] == "••••cret"
        assert updated.json()["tokens_per_minute"] == 9000
        assert updated.json()["output_tokens_per_minute"] == 4000

        with app.state.database.get_session() as session:
            stored = session.scalar(select(ModelEndpoint).where(ModelEndpoint.id == endpoint_id))
            assert stored is not None
            assert "replacement-secret" not in stored.encrypted_api_key
            assert SecretCipher(encryption_key).decrypt(stored.encrypted_api_key) == "replacement-secret"
            assert stored.api_key_fingerprint is not None
            assert "replacement-secret" not in stored.api_key_fingerprint

        deleted = client.delete(f"/api/v1/model-endpoints/{endpoint_id}")
        assert deleted.status_code == 204
        assert client.get(f"/api/v1/model-endpoints/{endpoint_id}").status_code == 404


def test_model_endpoint_creation_requires_an_encryption_key(tmp_path: Path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}"))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models.example.test/v1",
                "api_key": "test-secret-key",
                "model_name": "example-model",
            },
        )

    assert response.status_code == 503
    assert "LLE_SECRET_ENCRYPTION_KEY" in response.json()["detail"]


def test_model_endpoint_persists_supported_protocol_profile(tmp_path: Path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode()))
    with TestClient(app) as client:
        response = client.post("/api/v1/model-endpoints", json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "responses", "protocol_profile": "openai_responses"})
        assert response.status_code == 201
        endpoint = response.json()
        assert endpoint["protocol_profile"] == "openai_responses"
        updated = client.patch(f"/api/v1/model-endpoints/{endpoint['id']}", json={"protocol_profile": "openai_chat_completions"})
        assert updated.status_code == 200
        assert updated.json()["protocol_profile"] == "openai_chat_completions"


def test_model_endpoint_accepts_all_built_in_provider_protocol_profiles(tmp_path: Path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode()))
    profiles = ["anthropic_messages", "gemini_generate_content", "azure_openai_chat_completions", "ollama_chat", "custom_http_json"]
    with TestClient(app) as client:
        for profile in profiles:
            response = client.post("/api/v1/model-endpoints", json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "model", "protocol_profile": profile})
            assert response.status_code == 201
            assert response.json()["protocol_profile"] == profile
        local = client.post("/api/v1/model-endpoints", json={"base_url": "http://127.0.0.1:11434", "api_key": "", "model_name": "llama", "protocol_profile": "ollama_chat"})
        assert local.status_code == 201
        assert local.json()["api_key_mask"] == "\u2022\u2022\u2022\u2022"


def test_model_endpoint_persists_safe_custom_headers_and_metadata(tmp_path: Path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode()))
    with TestClient(app) as client:
        response = client.post("/api/v1/model-endpoints", json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "model", "custom_headers": {"X-Project": "demo"}, "tags": ["vision", "test"], "notes": "safe routing metadata"})
        assert response.status_code == 201
        body = response.json()
        assert body["custom_headers"] == {"X-Project": "demo"}
        assert body["tags"] == ["vision", "test"]
        assert body["notes"] == "safe routing metadata"
        rejected = client.patch(f"/api/v1/model-endpoints/{body['id']}", json={"custom_headers": {"Authorization": "not-allowed"}})
        assert rejected.status_code == 422


def test_model_endpoint_request_preview_excludes_secrets(tmp_path: Path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode()))
    with TestClient(app) as client:
        endpoint = client.post("/api/v1/model-endpoints", json={"base_url": "https://models.example.test/v1", "api_key": "never-return", "model_name": "preview", "protocol_profile": "openai_responses"}).json()
        preview = client.post(f"/api/v1/model-endpoints/{endpoint['id']}/request-preview", json={"messages": [{"role": "user", "content": "hello"}]})
        assert preview.status_code == 200
        assert preview.json()["request_body"]["input"][0]["content"] == [{"type": "input_text", "text": "hello"}]
        assert "never-return" not in preview.text


def test_model_endpoint_rejects_protected_request_body_fields(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models.example.test/v1",
                "api_key": "test-secret-key",
                "model_name": "example-model",
                "default_request_body": {"model": "cannot-override"},
            },
        )

    assert response.status_code == 422
    assert "protected fields" in response.json()["detail"][0]["msg"]
