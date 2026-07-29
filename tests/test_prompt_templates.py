from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.connection_tester import ConnectionTestResult


class SuccessfulTester:
    def test(self, _endpoint, _api_key: str) -> ConnectionTestResult:
        return ConnectionTestResult(True, "ok", 200)


def test_prompt_packages_validate_variables_and_snapshot_nonstandard_flags(tmp_path) -> None:
    app = create_app(
        Settings.local_development(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode()),
        connection_tester=SuccessfulTester(),
    )
    with TestClient(app) as api:
        invalid = api.post("/api/v1/prompt-packages", json={"name": "bad", "version": "1", "user_template": "{{ unsupported }}"})
        assert invalid.status_code == 422

        prompt = api.post(
            "/api/v1/prompt-packages",
            json={
                "name": "contextual",
                "version": "1",
                "prompt_type": "benchmark_variant",
                "system_message": "Return concise text.",
                "few_shot_examples": [{"role": "user", "content": "Example"}],
                "user_template": "{{ context }}\n{{ question }}\n{{ language }}",
            },
        )
        assert prompt.status_code == 201
        endpoint = api.post("/api/v1/model-endpoints", json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "model"}).json()
        assert api.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = api.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "prompt_package_id": prompt.json()["id"], "sample_limit": 1})
        assert run.status_code == 201
        flags = run.json()["configuration_snapshot"]["prompt_standardization"]
        assert flags == {"is_standard": False, "flags": ["non_standard_prompt", "modified_system_message", "custom_few_shot"]}
        attempt = api.get(f"/api/v1/evaluation-runs/{run.json()['id']}/attempts").json()[0]
        assert "2 + 2" in attempt["input_snapshot"]["messages"][-1]["content"]
