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
