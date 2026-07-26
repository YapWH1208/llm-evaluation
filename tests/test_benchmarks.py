from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_builtin_benchmark_manifest_is_registered_and_selectable(tmp_path: Path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode()))
    with TestClient(app) as client:
        benchmarks = client.get("/api/v1/benchmarks")
        assert benchmarks.status_code == 200
        quick_check = next(item for item in benchmarks.json() if item["benchmark_id"] == "text-quick-check")
        assert quick_check["status"] == "available"
        assert quick_check["manifest"]["required_capabilities"] == ["text_input"]

        endpoint = client.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"secret","model_name":"m"}).json()
        with app.state.database.get_session() as session:
            from app.db.models import ModelEndpoint
            item = session.get(ModelEndpoint, endpoint["id"])
            assert item is not None
            item.status = "available"
            session.commit()
        run = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id":endpoint["id"],"benchmark_id":"text-quick-check","benchmark_version":"1.0.0","sample_limit":1})
        assert run.status_code == 201
        assert run.json()["configuration_snapshot"]["benchmark"]["manifest"]["scoring"]["type"] == "exact_match"

        disabled = client.patch(f"/api/v1/benchmarks/{quick_check['id']}", json={"status": "disabled"})
        assert disabled.status_code == 200
        blocked = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id":endpoint["id"],"benchmark_id":"text-quick-check","benchmark_version":"1.0.0","sample_limit":1})
        assert blocked.status_code == 409
        assert "disabled" in blocked.json()["detail"]
