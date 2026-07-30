from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.mongo import MongoDocumentStore
from app.main import create_app
from app.benchmarks import get_installed_plugin, unregister_manifest_plugin
from tests.test_mongo_document_store import FakeClient


def _payload() -> dict[str, object]:
    return {"benchmark_id": "vision-smoke", "version": "1", "display_name": "Vision smoke", "manifest": {"modalities": ["image"]}}


def test_benchmark_definition_can_be_read_updated_and_disabled(tmp_path) -> None:
    app = create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode()))
    with TestClient(app) as api:
        created = api.post("/api/v1/benchmarks", json=_payload())
        assert created.status_code == 201
        benchmark_id = created.json()["id"]
        assert api.get(f"/api/v1/benchmarks/{benchmark_id}").json()["display_name"] == "Vision smoke"
        updated = api.patch(f"/api/v1/benchmarks/{benchmark_id}", json={"status": "disabled", "display_name": "Vision smoke v2"})
        assert updated.status_code == 200
        assert updated.json()["status"] == "disabled"
        assert api.get(f"/api/v1/benchmarks/{benchmark_id}/prompt").json()["prompt"] is None
        assert api.get(f"/api/v1/benchmarks/{benchmark_id}/dataset-status").json() == []
        pack = api.post("/api/v1/benchmarks/packs", json={"pack_name": "smoke", "benchmarks": [{"benchmark_id": "pack-smoke", "version": "1", "display_name": "Pack smoke", "manifest": {"modalities": ["text"]}}]})
        assert pack.status_code == 201
        assert pack.json()[0]["source"] == "pack:smoke"
        assert updated.json()["display_name"] == "Vision smoke v2"


def test_mongodb_benchmark_definition_can_be_updated(tmp_path) -> None:
    client = FakeClient()
    settings = Settings.local_development(database_url="mongodb://mongo.test/platform", data_root=str(tmp_path), secret_encryption_key=Fernet.generate_key().decode())
    app = create_app(settings, document_store=MongoDocumentStore(settings, client=client))
    with TestClient(app) as api:
        created = api.post("/api/v1/benchmarks", json=_payload()).json()
        updated = api.patch(f"/api/v1/benchmarks/{created['id']}", json={"status": "enabled"})
        assert updated.status_code == 200
        assert updated.json()["status"] == "enabled"


def test_updating_a_custom_manifest_removes_its_previous_runtime_plugin(tmp_path) -> None:
    app = create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode()))
    benchmark_key = ("runtime-update-smoke", "1")
    try:
        with TestClient(app) as api:
            created = api.post("/api/v1/benchmarks", json={
                "benchmark_id": benchmark_key[0],
                "version": benchmark_key[1],
                "display_name": "Runtime update smoke",
                "manifest": {
                    "modalities": ["text"],
                    "samples": [{"sample_id": "one", "prompt": "Say hi", "reference_answer": "hi"}],
                },
            })
            assert created.status_code == 201
            assert get_installed_plugin(*benchmark_key) is not None

            updated = api.patch(f"/api/v1/benchmarks/{created.json()['id']}", json={"manifest": {"modalities": ["text"]}})
            assert updated.status_code == 200
            assert get_installed_plugin(*benchmark_key) is None
    finally:
        unregister_manifest_plugin(*benchmark_key)


def test_published_benchmark_content_requires_an_explicit_new_version(tmp_path) -> None:
    app = create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path / 'versions.db'}", secret_encryption_key=Fernet.generate_key().decode()))
    with TestClient(app) as api:
        created = api.post("/api/v1/benchmarks", json=_payload()).json()
        assert api.patch(f"/api/v1/benchmarks/{created['id']}", json={"status": "enabled"}).status_code == 200
        blocked = api.patch(f"/api/v1/benchmarks/{created['id']}", json={"manifest": {"modalities": ["text"]}})
        assert blocked.status_code == 409
        assert "new version" in blocked.json()["detail"]

        revision = api.post(
            f"/api/v1/benchmarks/{created['id']}/versions",
            json={"version": "2", "display_name": "Vision smoke v2", "manifest": {"modalities": ["text"]}},
        )
        assert revision.status_code == 201
        assert revision.json()["benchmark_id"] == created["benchmark_id"]
        assert revision.json()["version"] == "2"
        assert revision.json()["status"] == "registered"
        assert api.get(f"/api/v1/benchmarks/{created['id']}").json()["manifest"]["modalities"] == ["image"]


def test_mongodb_published_benchmark_content_requires_a_new_version(tmp_path) -> None:
    client = FakeClient()
    settings = Settings.local_development(database_url="mongodb://mongo.test/platform", data_root=str(tmp_path), secret_encryption_key=Fernet.generate_key().decode())
    app = create_app(settings, document_store=MongoDocumentStore(settings, client=client))
    with TestClient(app) as api:
        created = api.post("/api/v1/benchmarks", json=_payload()).json()
        assert api.patch(f"/api/v1/benchmarks/{created['id']}", json={"status": "enabled"}).status_code == 200
        assert api.patch(f"/api/v1/benchmarks/{created['id']}", json={"display_name": "mutated"}).status_code == 409
        revision = api.post(f"/api/v1/benchmarks/{created['id']}/versions", json={"version": "2", "manifest": {"modalities": ["text"]}})
        assert revision.status_code == 201
        assert revision.json()["version"] == "2"
