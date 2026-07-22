from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db import EvaluationRun, SampleAttempt, TaskUnit
from app.main import create_app
from app.services.connection_tester import ConnectionTestResult


class SuccessfulTester:
    def test(self, _endpoint, _api_key: str) -> ConnectionTestResult:
        return ConnectionTestResult(True, "Connection succeeded.", 200)


def test_text_quick_check_run_creates_durable_tasks_and_attempts(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        ),
        connection_tester=SuccessfulTester(),
    )

    with TestClient(app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models.example.test/v1",
                "api_key": "test-secret-key",
                "model_name": "example-model",
            },
        )
        endpoint_id = endpoint.json()["id"]
        assert client.post(
            f"/api/v1/model-endpoints/{endpoint_id}/connection-test"
        ).status_code == 200

        created = client.post(
            "/api/v1/evaluation-runs",
            json={"model_endpoint_id": endpoint_id, "sample_limit": 2},
        )
        assert created.status_code == 201
        body = created.json()
        assert body["status"] == "queued"
        assert body["total_samples"] == 2
        assert body["benchmark_id"] == "text-quick-check"
        assert body["configuration_snapshot"]["endpoint"]["model_name"] == "example-model"
        assert "encrypted_api_key" not in str(body["configuration_snapshot"])

        with app.state.database.get_session() as session:
            run = session.scalar(select(EvaluationRun).where(EvaluationRun.id == body["id"]))
            assert run is not None
            tasks = list(session.scalars(select(TaskUnit).where(TaskUnit.run_id == run.id)))
            attempts = list(
                session.scalars(
                    select(SampleAttempt)
                    .where(SampleAttempt.run_id == run.id)
                    .order_by(SampleAttempt.sample_id)
                )
            )

        assert len(tasks) == 1
        assert tasks[0].status == "pending"
        assert len(attempts) == 2
        assert {attempt.status for attempt in attempts} == {"pending"}
        assert {attempt.attempt_number for attempt in attempts} == {1}
        assert all(attempt.task_id == tasks[0].id for attempt in attempts)


def test_run_requires_a_verified_endpoint(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        )
    )

    with TestClient(app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models.example.test/v1",
                "api_key": "test-secret-key",
                "model_name": "example-model",
            },
        )
        response = client.post(
            "/api/v1/evaluation-runs",
            json={"model_endpoint_id": endpoint.json()["id"]},
        )

    assert response.status_code == 409
    assert "connection test" in response.json()["detail"]
