from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from urllib.parse import urlsplit

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
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            data_root=str(tmp_path / "data"),
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
            public_web_url="https://evaluation.example.test",
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
        assert body["insights"]["strongest_capability"]["score"] == 1.0
        assert body["insights"]["weakest_capability"]["score"] == 1.0
        assert {item["capability"] for item in body["insights"]["capabilities"]} == {"reasoning", "instruction_following"}
        assert body["insights"]["significant_anomalies"] == []

        evidence = client.get(f"/api/v1/evaluation-runs/{run_a}/attempts", params={"capability": "reasoning", "language": "en", "difficulty": "basic", "modality": "text", "correct": True})
        assert evidence.status_code == 200
        assert len(evidence.json()) == 1
        assert evidence.json()[0]["sample_metadata"] == {"capability": "reasoning", "language": "en", "difficulty": "basic"}
        assert evidence.json()[0]["human_review_status"] == "unreviewed"
        assert evidence.json()[0]["judge_disagreement"] is False

        metrics = client.get(f"/api/v1/analytics/runs/{run_a}/metrics")
        assert metrics.status_code == 200
        metrics_by_name = {metric["metric_name"]: metric for metric in metrics.json()}
        assert metrics_by_name["accuracy"]["metric_value"] == 1.0
        assert metrics_by_name["accuracy"]["sample_count"] == 2
        assert metrics_by_name["accuracy"]["confidence_interval"]["method"] == "normal_95"
        assert metrics_by_name["p95_latency_ms"]["metric_value"] == 75.0
        recomputed = client.post(f"/api/v1/analytics/runs/{run_a}/metrics/recompute")
        assert recomputed.status_code == 200
        assert len(recomputed.json()) == len(metrics_by_name)

        dashboard = client.get("/api/v1/dashboard")
        assert dashboard.status_code == 200
        assert dashboard.json()["api"]["estimated_cost_by_currency"] == {"USD": 0.00016}
        assert dashboard.json()["quality"]["samples"]["total"] == 4

        matrix = client.get("/api/v1/analytics/matrix")
        assert matrix.status_code == 200
        assert len(matrix.json()["heatmap"]) == 2
        assert matrix.json()["capability_matrix"][0]["capability"] == "text_input"
        detailed_matrix = client.get("/api/v1/analytics/matrix", params={"baseline_run_id": run_a})
        assert detailed_matrix.status_code == 200
        heatmaps = detailed_matrix.json()["heatmaps"]
        assert set(heatmaps) == {"model_benchmark", "model_capability", "model_language", "model_difficulty", "prompt_benchmark", "model_modality"}
        reasoning_cell = next(cell for cell in heatmaps["model_capability"] if cell["x_label"] == "model-a" and cell["y_key"] == "reasoning")
        assert reasoning_cell["sample_count"] == 1
        assert reasoning_cell["confidence_interval"]["method"] == "normal_95"
        assert reasoning_cell["baseline_score"] == 1.0
        assert reasoning_cell["delta"] == 0.0
        assert heatmaps["model_language"][0]["y_key"] == "en"
        assert heatmaps["model_difficulty"][0]["y_key"] == "basic"
        assert heatmaps["model_modality"][0]["y_key"] == "text"

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

        multi_report = client.post(
            "/api/v1/reports",
            json={"run_id": run_a, "format": "json", "report_type": "multi_model_comparison", "related_run_ids": [run_b]},
        )
        assert multi_report.status_code == 200
        assert multi_report.json()["report_type"] == "multi_model_comparison"
        multi_payload = client.get(f"/api/v1/reports/{multi_report.json()['id']}/download").json()
        assert multi_payload["related_runs"][0]["run_id"] == run_b
        assert multi_payload["related_runs"][0]["summary"]["samples"]["accuracy"] == 0.0
        assert client.post("/api/v1/reports", json={"run_id": run_a, "format": "json", "report_type": "regression"}).status_code == 409

        cost_report = client.post("/api/v1/reports", json={"run_id": run_a, "format": "json", "report_type": "cost"})
        assert cost_report.status_code == 200
        assert cost_report.json()["report_type"] == "cost"

        report = client.post("/api/v1/reports", json={"run_id": run_a, "format": "markdown"})
        assert report.status_code == 200
        assert report.json()["format"] == "markdown"
        downloaded = client.get(f"/api/v1/reports/{report.json()['id']}/download")
        assert downloaded.status_code == 200
        assert "# Evaluation report: text-quick-check" in downloaded.text
        assert "Estimated cost" in downloaded.text

        pdf = client.post("/api/v1/reports", json={"run_id": run_a, "format": "pdf"})
        assert pdf.status_code == 200
        pdf_download = client.get(f"/api/v1/reports/{pdf.json()['id']}/download")
        assert pdf_download.headers["content-type"].startswith("application/pdf")
        assert pdf_download.content.startswith(b"%PDF-1.4")

        parquet = client.post("/api/v1/reports", json={"run_id": run_a, "format": "parquet"})
        assert parquet.status_code == 200
        parquet_download = client.get(f"/api/v1/reports/{parquet.json()['id']}/download")
        assert parquet_download.headers["content-type"].startswith("application/vnd.apache.parquet")
        assert parquet_download.content[:4] == b"PAR1"
        assert parquet_download.content[-4:] == b"PAR1"
        assert client.post(f"/api/v1/reports/{parquet.json()['id']}/shares", json={}).status_code == 409

        share = client.post(
            f"/api/v1/reports/{report.json()['id']}/shares",
            json={"password": "view-only-password"},
        )
        assert share.status_code == 201
        assert share.json()["share_url"].startswith("https://evaluation.example.test/shared-reports/")
        share_path = urlsplit(share.json()["share_url"]).path
        assert client.get(share_path).status_code == 401
        public_report = client.get(share_path, headers={"X-Report-Password": "view-only-password"})
        assert public_report.status_code == 200
        assert "# Evaluation report" in public_report.text
        assert public_report.headers["cache-control"] == "private, no-store"
        assert public_report.headers["vary"] == "X-Report-Password"
        # A password-authorized response must not make a later headerless read
        # usable, even when a caller reuses the same client/cache context.
        assert client.get(share_path).status_code == 401
        for _ in range(3):
            assert client.get(share_path).status_code == 401
        # The SQL-backed shared limiter blocks the sixth read before hashing
        # the password, including a correct value from that client partition.
        assert client.get(share_path, headers={"X-Report-Password": "view-only-password"}).status_code == 401
        revoked = client.post(f"/api/v1/reports/{report.json()['id']}/shares/{share.json()['id']}/revoke")
        assert revoked.status_code == 200
        assert client.get(share_path, headers={"X-Report-Password": "view-only-password"}).status_code == 404
