from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.connection_tester import ConnectionTestResult
from app.services.model_executor import SampleExecutionResult


class SuccessfulTester:
    def test(self, _endpoint, _api_key: str) -> ConnectionTestResult:
        return ConnectionTestResult(True, "Connection succeeded.", 200)


class ExactExecutor:
    def execute(self, endpoint, _api_key: str, _input_snapshot: dict[str, object]) -> SampleExecutionResult:
        return SampleExecutionResult(True, {"model": endpoint.model_name}, '{"choices":[{"message":{"content":"4"}}]}', "4")


def test_completed_run_emits_sse_snapshot(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode("utf-8")),
        connection_tester=SuccessfulTester(),
        model_executor=ExactExecutor(),
    )
    with TestClient(app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={"base_url": "https://models.example.test/v1", "api_key": "audit-secret-key", "model_name": "example-model"},
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}).json()
        assert client.post(f"/api/v1/evaluation-runs/{run['id']}/execute").json()["status"] == "completed"

        events = client.get(f"/api/v1/evaluation-runs/{run['id']}/events")
        assert events.status_code == 200
        assert "event: run" in events.text
        assert '"status":"completed"' in events.text
