from pathlib import Path
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
import pytest
from app.core.config import Settings
from app.main import create_app

def test_user_creation_records_an_audit_event(tmp_path:Path)->None:
    app=create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path/'db.sqlite'}"))
    with TestClient(app) as client:
        user=client.post("/api/v1/users",json={"email":"reviewer@example.test","display_name":"Reviewer","role":"reviewer"})
        assert user.status_code==201
        events=client.get("/api/v1/audit-events")
        assert events.status_code==200
        assert events.json()[0]["action"]=="user.created"

def test_configured_bearer_token_protects_api(tmp_path:Path)->None:
    app=create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path/'db.sqlite'}",admin_token="protect-me",secret_encryption_key=Fernet.generate_key().decode()))
    with TestClient(app) as client:
        assert client.get("/api/v1/users").status_code==401
        assert client.get("/api/v1/users",headers={"Authorization":"Bearer protect-me"}).status_code==200

def test_missing_token_requires_explicit_local_opt_in(tmp_path: Path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}"))
    with pytest.raises(ValueError, match="LLE_ADMIN_TOKEN"):
        with TestClient(app):
            pass

def test_authenticated_browser_preflight_bypasses_bearer_check(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
            admin_token="protect-me",
            secret_encryption_key=Fernet.generate_key().decode(),
        )
    )
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/model-endpoints",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"

def test_user_tokens_enforce_their_assigned_roles(tmp_path:Path)->None:
    app=create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path/'db.sqlite'}",admin_token="protect-me",secret_encryption_key=Fernet.generate_key().decode()))
    admin_headers={"Authorization":"Bearer protect-me"}
    with TestClient(app) as client:
        viewer=client.post("/api/v1/users",headers=admin_headers,json={"email":"viewer@example.test","display_name":"Viewer","role":"viewer"})
        assert viewer.status_code==201
        viewer_headers={"Authorization":f"Bearer {viewer.json()['api_token']}"}
        assert client.get("/api/v1/dashboard",headers=viewer_headers).status_code==200
        assert client.post("/api/v1/model-endpoints",headers=viewer_headers,json={"base_url":"https://models.example.test/v1","api_key":"secret","model_name":"m"}).status_code==403
        evaluator=client.post("/api/v1/users",headers=admin_headers,json={"email":"evaluator@example.test","display_name":"Evaluator","role":"evaluator"})
        evaluator_headers={"Authorization":f"Bearer {evaluator.json()['api_token']}"}
        assert client.post("/api/v1/model-endpoints",headers=evaluator_headers,json={"base_url":"https://models.example.test/v1","api_key":"secret","model_name":"m"}).status_code==201
        assert client.get("/api/v1/users",headers=evaluator_headers).status_code==403
