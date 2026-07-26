from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.mongo import MongoDocumentStore
from app.main import create_app
from tests.test_mongo_document_store import FakeClient


def _suite() -> dict[str, object]:
    return {
        "name": "release-gate",
        "version": "1",
        "description": "Pre-release suite",
        "benchmark_list": [{"benchmark_id": "text-quick-check", "version": "1.0.0"}],
        "default_request_body": {"temperature": 0},
        "weight_configuration": {"text": 1.0},
    }


def test_evaluation_suite_crud_is_versioned(tmp_path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode()))
    with TestClient(app) as api:
        created = api.post("/api/v1/evaluation-suites", json=_suite())
        assert created.status_code == 201
        suite = created.json()
        assert api.get("/api/v1/evaluation-suites").json()[0]["id"] == suite["id"]
        updated = api.patch(f"/api/v1/evaluation-suites/{suite['id']}", json={"description": "Updated"})
        assert updated.status_code == 200
        assert updated.json()["description"] == "Updated"
        assert api.post("/api/v1/evaluation-suites", json=_suite()).status_code == 409


def test_mongodb_evaluation_suite_crud(tmp_path) -> None:
    client = FakeClient()
    settings = Settings(database_url="mongodb://mongo.test/platform", data_root=str(tmp_path), secret_encryption_key=Fernet.generate_key().decode())
    app = create_app(settings, document_store=MongoDocumentStore(settings, client=client))
    with TestClient(app) as api:
        suite = api.post("/api/v1/evaluation-suites", json=_suite()).json()
        assert api.get(f"/api/v1/evaluation-suites/{suite['id']}").status_code == 200
