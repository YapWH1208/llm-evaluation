from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.benchmarks import unregister_manifest_plugin


def test_builtin_benchmark_manifest_is_registered_and_selectable(tmp_path: Path) -> None:
    app = create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode()))
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


def test_inline_custom_pack_is_runnable_and_reloaded_from_storage(tmp_path: Path) -> None:
    settings = Settings.local_development(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode())
    pack = {
        "pack_name": "custom-smoke",
        "benchmarks": [{
            "benchmark_id": "custom-inline",
            "version": "1.0.0",
            "display_name": "Custom Inline Pack",
            "manifest": {
                "required_capabilities": ["text_input"],
                "scoring": {"type": "exact_match"},
                "shard_size": 1,
                "samples": [{"sample_id": "custom-001", "prompt": "Reply with only CUSTOM.", "reference_answer": "CUSTOM", "metadata": {"capability": "custom", "language": "en", "difficulty": "basic"}}],
            },
        }],
    }
    app = create_app(settings)
    with TestClient(app) as client:
        installed = client.post("/api/v1/benchmarks/packs", json=pack)
        assert installed.status_code == 201
        assert installed.json()[0]["manifest"]["benchmark_id"] == "custom-inline"
        endpoint = client.post("/api/v1/model-endpoints", json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "m"}).json()
        with app.state.database.get_session() as session:
            from app.db.models import ModelEndpoint
            item = session.get(ModelEndpoint, endpoint["id"])
            assert item is not None
            item.status = "available"
            session.commit()
        run = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "benchmark_id": "custom-inline", "benchmark_version": "1.0.0"})
        assert run.status_code == 201
        assert run.json()["total_samples"] == 1
        revision = client.post(
            "/api/v1/benchmarks/" + installed.json()[0]["id"] + "/versions",
            json={
                "version": "2.0.0",
                "manifest": {
                    "required_capabilities": ["text_input"],
                    "scoring": {"type": "exact_match"},
                    "samples": [{"sample_id": "custom-002", "prompt": "Reply with only NEW.", "reference_answer": "NEW"}],
                },
            },
        )
        assert revision.status_code == 201
        rerun = client.post(f"/api/v1/evaluation-runs/{run.json()['id']}/rerun-benchmark")
        assert rerun.status_code == 201
        assert rerun.json()["benchmark_version"] == "1.0.0"

    unregister_manifest_plugin("custom-inline", "1.0.0")
    reloaded = create_app(settings)
    with TestClient(reloaded) as client:
        endpoint = client.get("/api/v1/model-endpoints").json()[0]
        run = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "benchmark_id": "custom-inline", "benchmark_version": "1.0.0"})
        assert run.status_code == 201
        assert run.json()["configuration_snapshot"]["benchmark"]["manifest"]["samples"][0]["sample_id"] == "custom-001"
