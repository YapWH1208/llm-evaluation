import base64
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.connection_tester import ConnectionTestResult
from app.services.model_executor import SampleExecutionResult
from app.services.run_names import format_run_display_name


class SuccessfulTester:
    def test(self, _endpoint, _api_key: str) -> ConnectionTestResult:
        return ConnectionTestResult(True, "Connection succeeded.", 200)


class MultimodalExecutor:
    def execute(self, endpoint, _api_key: str, input_snapshot: dict[str, object]) -> SampleExecutionResult:
        content = input_snapshot["messages"][0]["content"]
        assert isinstance(content, list)
        assert content[1]["source"]["base64_data"]
        return SampleExecutionResult(True, {"model": endpoint.model_name}, '{"choices":[{"message":{"content":"yes"}}]}', "yes")


def test_custom_multimodal_run_resolves_uploaded_assets_and_uses_normal_execution(tmp_path: Path) -> None:
    png = b"\x89PNG\r\n\x1a\nminimal-png-content"
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            data_root=str(tmp_path / "data"),
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        ),
        connection_tester=SuccessfulTester(),
        model_executor=MultimodalExecutor(),
    )
    with TestClient(app) as client:
        asset = client.post(
            "/api/v1/assets",
            json={"filename": "sample.png", "mime_type": "image/png", "base64_data": base64.b64encode(png).decode()},
        ).json()
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={"base_url": "https://models.example.test/v1", "api_key": "test-secret-key", "model_name": "example-model"},
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        created = client.post(
            "/api/v1/evaluation-runs/custom-multimodal",
            json={
                "model_endpoint_id": endpoint["id"],
                "sample_id": "image-1",
                "reference_answer": "yes",
                "messages": [{"role": "user", "content": [{"type": "text", "text": "Does the image exist?"}, {"type": "image", "source": {"asset_id": asset["id"]}, "mime_type": "image/png"}]}],
            },
        )
        assert created.status_code == 201
        assert created.json()["benchmark_id"] == "custom-multimodal"
        assert created.json()["display_name"] == format_run_display_name(
            "example-model",
            "custom-multimodal",
            datetime.fromisoformat(created.json()["created_at"]),
        )
        assert client.post(f"/api/v1/evaluation-runs/{created.json()['id']}/execute").json()["status"] == "completed"
        attempt = client.get(f"/api/v1/evaluation-runs/{created.json()['id']}/attempts").json()[0]
        assert attempt["status"] == "succeeded"
        assert attempt["input_snapshot"]["modality"] == "image+text"
        source = attempt["input_snapshot"]["messages"][0]["content"][1]["source"]
        assert source["asset_id"] == asset["id"]
        assert "base64_data" not in source
        assert source["embedded_media"]["redacted"] is True
