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


class EvidenceExecutor:
    def execute(self, endpoint, _api_key: str, input_snapshot: dict[str, object]) -> SampleExecutionResult:
        content = str(input_snapshot["messages"][0]["content"])
        correct_answer = "4" if "2 + 2" in content else "BLUE"
        prediction = correct_answer if endpoint.model_name == "model-a" else "incorrect"
        return SampleExecutionResult(
            success=True,
            request_snapshot={"model": endpoint.model_name},
            raw_response='{"choices":[{"message":{"content":"value"}}]}',
            prediction=prediction,
            latency_ms=75 if endpoint.model_name == "model-a" else 125,
            input_tokens=10,
            output_tokens=5,
        )


def _create_completed_run(client: TestClient, model_name: str) -> str:
    endpoint = client.post(
        "/api/v1/model-endpoints",
        json={
            "base_url": "https://models.example.test/v1",
            "api_key": "test-secret-key",
            "model_name": model_name,
            "input_cost_per_million": 2,
            "output_cost_per_million": 4,
        },
    ).json()
    assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
    run = client.post(
        "/api/v1/evaluation-runs",
        json={"model_endpoint_id": endpoint["id"], "sample_limit": 2},
    ).json()
    assert client.post(f"/api/v1/evaluation-runs/{run['id']}/execute").status_code == 200
    return run["id"]


def test_run_summary_comparison_and_report_exports(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            data_root=str(tmp_path / "data"),
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        ),
        connection_tester=SuccessfulTester(),
        model_executor=EvidenceExecutor(),
    )

    with TestClient(app) as client:
        run_a = _create_completed_run(client, "model-a")
        run_b = _create_completed_run(client, "model-b")

        summary = client.get(f"/api/v1/evaluation-runs/{run_a}/summary")
        assert summary.status_code == 200
        body = summary.json()
        assert body["samples"] == {
            "total": 2,
            "completed": 2,
            "successful": 2,
            "failed": 0,
            "completion_rate": 1.0,
            "success_rate": 1.0,
            "accuracy": 1.0,
        }
        assert body["latency_ms"]["average"] == 75.0
        assert body["latency_ms"]["p95"] == 75.0
        assert body["tokens"] == {"measured_samples": 2, "input": 20, "output": 10, "total": 30}
        assert body["cost"]["estimated"] == 0.00008
        assert body["cost"]["currency"] == "USD"

        dashboard = client.get("/api/v1/dashboard")
        assert dashboard.status_code == 200
        assert dashboard.json()["api"]["estimated_cost_by_currency"] == {"USD": 0.00016}
        assert dashboard.json()["quality"]["samples"]["total"] == 4

        matrix = client.get("/api/v1/analytics/matrix")
        assert matrix.status_code == 200
        assert len(matrix.json()["heatmap"]) == 2
        assert matrix.json()["capability_matrix"][0]["capability"] == "text_input"

        comparison = client.get("/api/v1/comparisons", params={"run_a": run_a, "run_b": run_b})
        assert comparison.status_code == 200
        compared = comparison.json()
        assert compared["outcomes"] == {
            "both_correct": 0,
            "run_a_only_correct": 2,
            "run_b_only_correct": 0,
            "both_incorrect": 0,
        }
        assert compared["differences"]["average_latency_ms"] == -50.0
        assert len(compared["sample_outcomes"]) == 2

        report = client.post("/api/v1/reports", json={"run_id": run_a, "format": "markdown"})
        assert report.status_code == 200
        assert report.json()["format"] == "markdown"
        downloaded = client.get(f"/api/v1/reports/{report.json()['id']}/download")
        assert downloaded.status_code == 200
        assert "# Evaluation report: text-quick-check" in downloaded.text
        assert "Estimated cost" in downloaded.text
