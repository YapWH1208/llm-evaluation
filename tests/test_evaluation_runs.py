from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db import EvaluationRun, SampleAttempt, TaskUnit
from app.db import ModelEndpoint
from app.main import create_app
from app.services.connection_tester import ConnectionTestResult
from app.services.model_executor import SampleExecutionResult


class SuccessfulTester:
    def test(self, _endpoint, _api_key: str) -> ConnectionTestResult:
        return ConnectionTestResult(True, "Connection succeeded.", 200)


class ExactAnswerExecutor:
    def execute(self, endpoint, api_key: str, input_snapshot: dict[str, object]) -> SampleExecutionResult:
        assert endpoint.model_name == "example-model"
        assert api_key == "test-secret-key"
        prompt = input_snapshot["messages"][0]["content"]
        prediction = "4" if "2 + 2" in prompt else "BLUE"
        return SampleExecutionResult(
            success=True,
            request_snapshot={"model": endpoint.model_name, "messages": input_snapshot["messages"]},
            raw_response=f'{{"choices":[{{"message":{{"content":"{prediction}"}}}}]}}',
            prediction=prediction,
        )


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


def test_execute_queued_run_captures_sample_evidence_and_scores(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        ),
        connection_tester=SuccessfulTester(),
        model_executor=ExactAnswerExecutor(),
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
        run = client.post(
            "/api/v1/evaluation-runs",
            json={"model_endpoint_id": endpoint_id, "sample_limit": 2},
        )
        run_id = run.json()["id"]

        executed = client.post(f"/api/v1/evaluation-runs/{run_id}/execute")
        assert executed.status_code == 200
        assert executed.json()["status"] == "completed"
        assert executed.json()["completed_samples"] == 2
        assert executed.json()["successful_samples"] == 2
        assert executed.json()["failed_samples"] == 0

        attempts = client.get(f"/api/v1/evaluation-runs/{run_id}/attempts")
        assert attempts.status_code == 200
        assert len(attempts.json()) == 2
        assert {attempt["status"] for attempt in attempts.json()} == {"succeeded"}
        assert {attempt["score"] for attempt in attempts.json()} == {1.0}
        assert all(attempt["request_snapshot"] for attempt in attempts.json())
        assert all(attempt["raw_response"] for attempt in attempts.json())

        assert client.post(f"/api/v1/evaluation-runs/{run_id}/execute").status_code == 409


def test_run_snapshots_a_versioned_prompt_package(tmp_path: Path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode("utf-8")))
    with TestClient(app) as client:
        endpoint = client.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"test-secret-key","model_name":"example-model"}).json()
        with app.state.database.get_session() as session:
            item = session.get(ModelEndpoint, endpoint["id"])
            assert item is not None
            item.status = "available"
            session.commit()
        prompt = client.post("/api/v1/prompt-packages", json={"name":"strict","version":"1","user_template":"Answer only: {{ question }}","system_message":"Be concise."}).json()
        run = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id":endpoint["id"],"sample_limit":1,"prompt_package_id":prompt["id"]})
        assert run.status_code == 201
        attempts = client.get(f"/api/v1/evaluation-runs/{run.json()['id']}/attempts").json()
        assert attempts[0]["input_snapshot"]["messages"][0]["role"] == "system"
        assert "Answer only:" in attempts[0]["input_snapshot"]["messages"][-1]["content"]
