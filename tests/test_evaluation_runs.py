from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db import EvaluationRun, SampleAttempt, TaskUnit
from app.db import ModelEndpoint
from app.db.models import EndpointRateWindow
from app.main import create_app
from app.services.connection_tester import ConnectionTestResult
from app.services.model_executor import SampleExecutionResult
from app.services.run_executor import _retry_delay_seconds


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
            latency_ms=125.5,
            input_tokens=10,
            output_tokens=5,
        )


class RetryOnceExecutor:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, endpoint, api_key: str, input_snapshot: dict[str, object]) -> SampleExecutionResult:
        self.calls += 1
        if self.calls == 1:
            return SampleExecutionResult(False, {"model": endpoint.model_name}, None, None, "http_429", "Provider returned HTTP 429.")
        return SampleExecutionResult(True, {"model": endpoint.model_name}, '{"choices":[{"message":{"content":"4"}}]}', "4")


class FatalThenSuccessfulExecutor:
    def __init__(self) -> None:
        self.fail = True

    def execute(self, endpoint, _api_key: str, _input_snapshot: dict[str, object]) -> SampleExecutionResult:
        if self.fail:
            return SampleExecutionResult(False, {"model": endpoint.model_name}, None, None, "http_400", "Invalid request.")
        return SampleExecutionResult(True, {"model": endpoint.model_name}, '{"choices":[{"message":{"content":"4"}}]}', "4")


class RetryAfterExecutor:
    def execute(self, endpoint, _api_key: str, _input_snapshot: dict[str, object]) -> SampleExecutionResult:
        return SampleExecutionResult(
            False,
            {"model": endpoint.model_name},
            None,
            None,
            "http_429",
            "Provider returned HTTP 429.",
            retry_after_seconds=120,
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
                "input_cost_per_million": 2,
                "output_cost_per_million": 4,
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


def test_run_rejects_effectively_unsupported_benchmark_capability(tmp_path: Path) -> None:
    app = create_app(
        Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode("utf-8")),
        connection_tester=SuccessfulTester(),
    )
    with TestClient(app) as client:
        endpoint = client.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"test-secret-key","model_name":"example-model"}).json()
        assert client.put(f"/api/v1/model-endpoints/{endpoint['id']}/capabilities", json={"capability_key":"text_input","user_declared_status":"unsupported"}).status_code == 200
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        response = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1})
        assert response.status_code == 409
        assert "text_input" in response.json()["detail"]


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
                "input_cost_per_million": 2,
                "output_cost_per_million": 4,
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
        assert {attempt["latency_ms"] for attempt in attempts.json()} == {125.5}
        assert {attempt["input_tokens"] for attempt in attempts.json()} == {10}
        assert {attempt["output_tokens"] for attempt in attempts.json()} == {5}
        assert {attempt["estimated_cost"] for attempt in attempts.json()} == {0.00004}

        assert client.post(f"/api/v1/evaluation-runs/{run_id}/execute").status_code == 409


def test_worker_leases_and_retries_only_retryable_samples(tmp_path: Path) -> None:
    executor = RetryOnceExecutor()
    app = create_app(
        Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode("utf-8")),
        connection_tester=SuccessfulTester(),
        model_executor=executor,
    )
    with TestClient(app) as client:
        endpoint = client.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"test-secret-key","model_name":"example-model"}).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id":endpoint["id"],"sample_limit":1}).json()
        with app.state.database.get_session() as session:
            task = session.scalar(select(TaskUnit).where(TaskUnit.run_id == run["id"]))
            assert task is not None
            task.payload = {**task.payload, "retry_policy":{"max_attempts":2,"base_delay_seconds":0,"max_delay_seconds":0}}
            session.commit()

        first_claim = client.post("/api/v1/workers/claim", json={"worker_id":"worker-a"}).json()
        first_execution = client.post(f"/api/v1/workers/tasks/{first_claim['id']}/execute", json={"lease_token":first_claim["lease_token"]})
        assert first_execution.status_code == 200
        assert first_execution.json()["status"] == "retry_scheduled"
        second_claim = client.post("/api/v1/workers/claim", json={"worker_id":"worker-b"}).json()
        second_execution = client.post(f"/api/v1/workers/tasks/{second_claim['id']}/execute", json={"lease_token":second_claim["lease_token"]})
        assert second_execution.status_code == 200
        assert second_execution.json()["status"] == "succeeded"
        final_run = client.get(f"/api/v1/evaluation-runs/{run['id']}").json()
        assert final_run["status"] == "completed"
        attempts = client.get(f"/api/v1/evaluation-runs/{run['id']}/attempts").json()
        assert [(attempt["attempt_number"], attempt["status"]) for attempt in attempts] == [(1, "failed"), (2, "succeeded")]


def test_retry_after_and_total_wait_bound_are_recorded_without_requeuing(tmp_path: Path) -> None:
    app = create_app(
        Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode("utf-8")),
        connection_tester=SuccessfulTester(),
        model_executor=RetryAfterExecutor(),
    )
    with TestClient(app) as client:
        endpoint = client.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"test-secret-key","model_name":"example-model"}).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}).json()
        with app.state.database.get_session() as session:
            task = session.scalar(select(TaskUnit).where(TaskUnit.run_id == run["id"]))
            assert task is not None
            task.payload = {
                **task.payload,
                "retry_policy": {
                    "max_attempts": 3,
                    "base_delay_seconds": 1,
                    "max_delay_seconds": 2,
                    "jitter_ratio": 0,
                    "max_total_wait_seconds": 30,
                },
            }
            session.commit()

        execution = client.post(f"/api/v1/evaluation-runs/{run['id']}/execute")
        assert execution.status_code == 200
        assert execution.json()["status"] == "completed_with_errors"
        with app.state.database.get_session() as session:
            task = session.scalar(select(TaskUnit).where(TaskUnit.run_id == run["id"]))
            assert task is not None
            assert task.payload["retry_exhausted_reason"] == "max_total_wait_seconds"
            assert task.payload["retry_total_wait_seconds"] == 0


def test_retry_delay_supports_fixed_exponential_jitter_and_provider_hint() -> None:
    policy = {
        "base_delay_seconds": 2,
        "max_delay_seconds": 10,
        "strategy": "exponential_jitter",
        "jitter_ratio": 0,
        "respect_retry_after": True,
    }
    assert _retry_delay_seconds(3, policy, provider_retry_after_seconds=None) == 8
    assert _retry_delay_seconds(3, policy, provider_retry_after_seconds=12) == 12
    assert _retry_delay_seconds(3, {**policy, "strategy": "fixed"}, provider_retry_after_seconds=None) == 2


def test_clone_run_and_retry_failed_samples_preserve_attempt_history(tmp_path: Path) -> None:
    executor = FatalThenSuccessfulExecutor()
    app = create_app(
        Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode("utf-8")),
        connection_tester=SuccessfulTester(),
        model_executor=executor,
    )
    with TestClient(app) as client:
        endpoint = client.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"test-secret-key","model_name":"example-model"}).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id":endpoint["id"],"sample_limit":1}).json()
        cloned = client.post(f"/api/v1/evaluation-runs/{run['id']}/clone")
        assert cloned.status_code == 201
        assert cloned.json()["id"] != run["id"]
        assert cloned.json()["configuration_snapshot"]["sample_ids"] == run["configuration_snapshot"]["sample_ids"]

        first_execution = client.post(f"/api/v1/evaluation-runs/{run['id']}/execute")
        assert first_execution.json()["status"] == "completed_with_errors"
        retried = client.post(f"/api/v1/evaluation-runs/{run['id']}/retry-failed")
        assert retried.status_code == 200
        assert retried.json()["status"] == "queued"

        executor.fail = False
        second_execution = client.post(f"/api/v1/evaluation-runs/{run['id']}/execute")
        assert second_execution.json()["status"] == "completed"
        attempts = client.get(f"/api/v1/evaluation-runs/{run['id']}/attempts").json()
        assert [(attempt["attempt_number"], attempt["status"]) for attempt in attempts] == [(1, "failed"), (2, "succeeded")]


def test_expired_worker_lease_requeues_only_inflight_sample_attempts(tmp_path: Path) -> None:
    app = create_app(
        Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode("utf-8")),
        connection_tester=SuccessfulTester(),
    )
    with TestClient(app) as client:
        endpoint = client.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"test-secret-key","model_name":"example-model"}).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id":endpoint["id"],"sample_limit":1}).json()
        claim = client.post("/api/v1/workers/claim", json={"worker_id":"crashed-worker"}).json()
        with app.state.database.get_session() as session:
            task = session.get(TaskUnit, claim["id"])
            attempt = session.scalar(select(SampleAttempt).where(SampleAttempt.task_id == claim["id"]))
            assert task is not None and attempt is not None
            task.status = "running"
            task.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            attempt.status = "running"
            session.commit()
        assert client.post("/api/v1/workers/reclaim-expired").json() == {"reclaimed": 1}
        recovered = client.post("/api/v1/workers/claim", json={"worker_id":"recovery-worker"}).json()
        assert recovered["id"] == claim["id"]
        attempts = client.get(f"/api/v1/evaluation-runs/{run['id']}/attempts").json()
        assert attempts[0]["status"] == "pending"


def test_worker_claim_honors_endpoint_concurrency_and_rpm_budgets(tmp_path: Path) -> None:
    app = create_app(
        Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode("utf-8")),
        connection_tester=SuccessfulTester(),
    )
    with TestClient(app) as client:
        endpoint = client.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"test-secret-key","model_name":"example-model","max_concurrency":1}).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        first_run = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id":endpoint["id"],"sample_limit":1}).json()
        client.post("/api/v1/evaluation-runs", json={"model_endpoint_id":endpoint["id"],"sample_limit":1})
        assert client.post("/api/v1/workers/claim", json={"worker_id":"worker-a"}).json()["run_id"] == first_run["id"]
        assert client.post("/api/v1/workers/claim", json={"worker_id":"worker-b"}).json() is None

    rpm_app = create_app(
        Settings(database_url=f"sqlite:///{tmp_path / 'rpm.db'}", secret_encryption_key=Fernet.generate_key().decode("utf-8")),
        connection_tester=SuccessfulTester(),
    )
    with TestClient(rpm_app) as client:
        endpoint = client.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"test-secret-key","model_name":"example-model","max_concurrency":3,"requests_per_minute":1}).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        client.post("/api/v1/evaluation-runs", json={"model_endpoint_id":endpoint["id"],"sample_limit":1})
        client.post("/api/v1/evaluation-runs", json={"model_endpoint_id":endpoint["id"],"sample_limit":1})
        assert client.post("/api/v1/workers/claim", json={"worker_id":"worker-a"}).json() is not None
        assert client.post("/api/v1/workers/claim", json={"worker_id":"worker-b"}).json() is None
        with rpm_app.state.database.get_session() as session:
            window = session.scalar(select(EndpointRateWindow))
            assert window is not None
            assert window.request_count == 1


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
