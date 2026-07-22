from pathlib import Path
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app

def test_user_creation_records_an_audit_event(tmp_path:Path)->None:
    app=create_app(Settings(database_url=f"sqlite:///{tmp_path/'db.sqlite'}"))
    with TestClient(app) as client:
        user=client.post("/api/v1/users",json={"email":"reviewer@example.test","display_name":"Reviewer","role":"reviewer"})
        assert user.status_code==201
        events=client.get("/api/v1/audit-events")
        assert events.status_code==200
        assert events.json()[0]["action"]=="user.created"

def test_configured_bearer_token_protects_api(tmp_path:Path)->None:
    app=create_app(Settings(database_url=f"sqlite:///{tmp_path/'db.sqlite'}",admin_token="protect-me"))
    with TestClient(app) as client:
        assert client.get("/api/v1/users").status_code==401
        assert client.get("/api/v1/users",headers={"Authorization":"Bearer protect-me"}).status_code==200
