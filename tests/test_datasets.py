import hashlib
from pathlib import Path
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app

def test_dataset_license_gate_and_acknowledgement(tmp_path: Path) -> None:
    app=create_app(Settings(database_url=f"sqlite:///{tmp_path/'db.sqlite'}",data_root=str(tmp_path/'data')))
    with TestClient(app) as client:
        created=client.post("/api/v1/datasets",json={"dataset_id":"demo","version":"1","license_text":"terms"})
        assert created.status_code==201
        body=created.json();assert body["status"]=="license_required"
        accepted=client.post(f"/api/v1/datasets/{body['id']}/accept-license")
        assert accepted.status_code==200;assert accepted.json()["status"]=="not_downloaded";assert accepted.json()["license_accepted_at"]
        cleared=client.delete(f"/api/v1/datasets/{body['id']}/cache")
        assert cleared.status_code==200;assert cleared.json()["status"]=="not_downloaded";assert cleared.json()["local_path"] is None


def test_dataset_supports_local_sources_and_explicit_credential_gates(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    source.write_text('{"question":"2 + 2"}\n', encoding="utf-8")
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path/'db.sqlite'}", data_root=str(tmp_path / "data")))
    with TestClient(app) as client:
        local = client.post("/api/v1/datasets", json={"dataset_id":"local","version":"1","source_url":source.as_uri(),"checksum":checksum})
        assert local.status_code == 201
        downloaded = client.post(f"/api/v1/datasets/{local.json()['id']}/download")
        assert downloaded.status_code == 200
        assert downloaded.json()["status"] == "ready"
        assert Path(downloaded.json()["local_path"]).read_text(encoding="utf-8") == source.read_text(encoding="utf-8")

        protected = client.post("/api/v1/datasets", json={"dataset_id":"private","version":"1","source_url":"https://datasets.example.test/private.jsonl","credential_env_var":"LLE_TEST_PRIVATE_DATASET_TOKEN"})
        assert protected.status_code == 201
        response = client.post(f"/api/v1/datasets/{protected.json()['id']}/download")
        assert response.status_code == 409
        assert "credential environment variable" in response.json()["detail"]
        items = {item["id"]: item for item in client.get("/api/v1/datasets").json()}
        assert items[protected.json()["id"]]["status"] == "credential_required"
