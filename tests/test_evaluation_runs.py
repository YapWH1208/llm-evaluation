from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
import httpx
from sqlalchemy import select

from app.core.config import Settings
from app.db import EvaluationRun, SampleAttempt, TaskUnit
from app.db import ModelEndpoint
from app.db.models import BenchmarkDefinition, EndpointRateWindow, EndpointSecondRateWindow
from app.main import create_app
from app.benchmarks.text_quick_check import TextSample
from app.infrastructure.providers.contracts import ConnectionTestResult, SampleExecutionResult
from app.modules.evaluations.names import format_run_display_name
from app.modules.evaluations.executor import _retry_delay_seconds
from app.modules.evaluations.queue import claim_task, reclaim_expired_leases


def _configure_dataset_download(monkeypatch, content: bytes) -> None:
    class Response:
        headers: dict[str, str] = {"content-length": str(len(content))}

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def raise_for_status(self) -> None:
            return None

        def iter_bytes(self):
            yield content

    monkeypatch.setattr(
        "app.infrastructure.network.outbound.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 0))],
    )
    monkeypatch.setattr(
        "app.modules.datasets.preparation.pinned_outbound_transport",
        lambda *_args, **_kwargs: httpx.MockTransport(lambda _request: httpx.Response(200, content=content)),
    )


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
            return SampleExecutionResult(
                False, {"model": endpoint.model_name}, None, None, "http_429", "Provider returned HTTP 429."
            )
        return SampleExecutionResult(
            True, {"model": endpoint.model_name}, '{"choices":[{"message":{"content":"4"}}]}', "4"
        )


class FatalThenSuccessfulExecutor:
    def __init__(self) -> None:
        self.fail = True

    def execute(self, endpoint, _api_key: str, _input_snapshot: dict[str, object]) -> SampleExecutionResult:
        if self.fail:
            return SampleExecutionResult(
                False, {"model": endpoint.model_name}, None, None, "http_400", "Invalid request."
            )
        return SampleExecutionResult(
            True, {"model": endpoint.model_name}, '{"choices":[{"message":{"content":"4"}}]}', "4"
        )


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
        Settings.local_development(
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
        assert client.post(f"/api/v1/model-endpoints/{endpoint_id}/connection-test").status_code == 200

        created = client.post(
            "/api/v1/evaluation-runs",
            json={"model_endpoint_id": endpoint_id, "sample_limit": 2},
        )
        assert created.status_code == 201
        body = created.json()
        assert body["status"] == "queued"
        assert body["total_samples"] == 2
        assert body["benchmark_id"] == "text-quick-check"
        assert body["display_name"] == format_run_display_name(
            "example-model",
            "text-quick-check",
            datetime.fromisoformat(body["created_at"]),
        )
        assert body["configuration_snapshot"]["endpoint"]["model_name"] == "example-model"
        assert "encrypted_api_key" not in str(body["configuration_snapshot"])

        with app.state.database.get_session() as session:
            run = session.scalar(select(EvaluationRun).where(EvaluationRun.id == body["id"]))
            assert run is not None
            assert run.display_name == body["display_name"]
            tasks = list(session.scalars(select(TaskUnit).where(TaskUnit.run_id == run.id)))
            attempts = list(
                session.scalars(
                    select(SampleAttempt).where(SampleAttempt.run_id == run.id).order_by(SampleAttempt.sample_id)
                )
            )

        assert [task.task_type for task in tasks] == ["dataset_preparation", "benchmark", "evaluation_shard"]
        dataset_task, benchmark_task, evaluation_task = tasks
        assert dataset_task.status == "succeeded"
        assert benchmark_task.status == "succeeded"
        assert benchmark_task.parent_task_id == dataset_task.id
        assert evaluation_task.status == "pending"
        assert evaluation_task.parent_task_id == benchmark_task.id
        assert len(attempts) == 2
        assert {attempt.status for attempt in attempts} == {"pending"}
        assert {attempt.attempt_number for attempt in attempts} == {1}
        assert all(attempt.task_id == evaluation_task.id for attempt in attempts)

        with app.state.database.get_session() as session:
            legacy_run = session.get(EvaluationRun, body["id"])
            assert legacy_run is not None
            legacy_run.display_name = None
            session.commit()
        assert client.get(f"/api/v1/evaluation-runs/{body['id']}").json()["display_name"] == body["display_name"]


def test_builtin_benchmark_packs_are_registered_and_preserve_multimodal_samples(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        ),
        connection_tester=SuccessfulTester(),
    )
    expected_packs = {
        "text-quick-check",
        "text-full-evaluation",
        "vision-quick-check",
        "vision-full-evaluation",
        "audio-evaluation",
        "video-evaluation",
        "multimodal-complete",
        "coding-evaluation",
        "instruction-following",
        "safety-evaluation",
    }
    with TestClient(app) as client:
        registered = {item["benchmark_id"]: item for item in client.get("/api/v1/benchmarks").json()}
        assert expected_packs <= set(registered)
        assert registered["multimodal-complete"]["manifest"]["input_modalities"] == ["text", "image", "audio", "video"]
        assert registered["vision-quick-check"]["manifest"]["shard_size"] == 20

        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models.example.test/v1",
                "api_key": "test-secret-key",
                "model_name": "example-model",
            },
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        preflight = client.post(
            "/api/v1/evaluation-runs/validate",
            json={
                "model_endpoint_id": endpoint["id"],
                "benchmark_id": "vision-quick-check",
                "benchmark_version": "1.0.0",
            },
        )
        assert preflight.status_code == 200
        assert preflight.json()["can_queue"] is True
        assert preflight.json()["estimated_input_tokens"] > 500
        run = client.post(
            "/api/v1/evaluation-runs",
            json={
                "model_endpoint_id": endpoint["id"],
                "benchmark_id": "vision-quick-check",
                "benchmark_version": "1.0.0",
            },
        )
        assert run.status_code == 201
        attempt = client.get(f"/api/v1/evaluation-runs/{run.json()['id']}/attempts").json()[0]
        assert attempt["input_snapshot"]["modality"] == "image"
        assert attempt["input_snapshot"]["messages"][0]["content"][1]["type"] == "image"
        assert attempt["input_snapshot"]["messages"][0]["content"][1]["source"]["embedded_media"]["redacted"] is True


def test_benchmark_samples_are_split_into_independent_shards_before_scoring(tmp_path: Path, monkeypatch) -> None:
    plugin = SimpleNamespace(
        manifest={
            "benchmark_id": "text-quick-check",
            "version": "1.0.0",
            "required_capabilities": ["text_input"],
            "scoring": {"type": "exact_match"},
            "datasets": [],
            "shard_size": 2,
        },
        samples=lambda _limit: tuple(
            TextSample(f"shard-{index}", "Reply with only the number: what is 2 + 2?", "4") for index in range(5)
        ),
    )
    monkeypatch.setattr("app.modules.evaluations.service.get_installed_plugin", lambda *_args: plugin)
    app = create_app(
        Settings.local_development(
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
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post(
            "/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 5}
        ).json()
        with app.state.database.get_session() as session:
            shards = list(
                session.scalars(
                    select(TaskUnit)
                    .where(TaskUnit.run_id == run["id"], TaskUnit.task_type == "evaluation_shard")
                    .order_by(TaskUnit.created_at)
                )
            )
            assert [task.payload["sample_ids"] for task in shards] == [
                ["shard-0", "shard-1"],
                ["shard-2", "shard-3"],
                ["shard-4"],
            ]
            assert [task.payload["shard_index"] for task in shards] == [1, 2, 3]
            assert {task.payload["shard_count"] for task in shards} == {3}
        completed = client.post(f"/api/v1/evaluation-runs/{run['id']}/execute")
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
        assert completed.json()["completed_samples"] == 5


def test_run_requires_a_verified_endpoint(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
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
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            data_root=str(tmp_path / "data"),
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
        ).json()
        assert (
            client.put(
                f"/api/v1/model-endpoints/{endpoint['id']}/capabilities",
                json={"capability_key": "text_input", "user_declared_status": "unsupported"},
            ).status_code
            == 200
        )
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        response = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1})
        assert response.status_code == 409
        assert "text_input" in response.json()["detail"]


def test_execute_queued_run_captures_sample_evidence_and_scores(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
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
        assert client.post(f"/api/v1/model-endpoints/{endpoint_id}/connection-test").status_code == 200
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

        logs = client.get(f"/api/v1/evaluation-runs/{run_id}/logs")
        assert logs.status_code == 200
        assert {entry["event"] for entry in logs.json()} == {"task.lifecycle", "sample.lifecycle"}
        assert any(entry["details"].get("status") == "succeeded" for entry in logs.json())
        assert "choices" not in str(logs.json())

        progress = client.get(f"/api/v1/evaluation-runs/{run_id}/progress")
        assert progress.status_code == 200
        assert progress.json()["completion_rate"] == 1
        assert progress.json()["successful_samples"] == 2

        assert client.post(f"/api/v1/evaluation-runs/{run_id}/execute").status_code == 409


def test_worker_leases_and_retries_only_retryable_samples(tmp_path: Path) -> None:
    executor = RetryOnceExecutor()
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            data_root=str(tmp_path / "data"),
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        ),
        connection_tester=SuccessfulTester(),
        model_executor=executor,
    )
    with TestClient(app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models.example.test/v1",
                "api_key": "test-secret-key",
                "model_name": "example-model",
            },
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post(
            "/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}
        ).json()
        with app.state.database.get_session() as session:
            task = session.scalar(
                select(TaskUnit).where(TaskUnit.run_id == run["id"], TaskUnit.task_type == "evaluation_shard")
            )
            assert task is not None
            task.payload = {
                **task.payload,
                "retry_policy": {"max_attempts": 2, "base_delay_seconds": 0, "max_delay_seconds": 0},
            }
            session.commit()

        first_claim = client.post("/api/v1/workers/claim", json={"worker_id": "worker-a"}).json()
        first_execution = client.post(
            f"/api/v1/workers/tasks/{first_claim['id']}/execute", json={"lease_token": first_claim["lease_token"]}
        )
        assert first_execution.status_code == 200
        assert first_execution.json()["status"] == "retry_scheduled"
        second_claim = client.post("/api/v1/workers/claim", json={"worker_id": "worker-b"}).json()
        second_execution = client.post(
            f"/api/v1/workers/tasks/{second_claim['id']}/execute", json={"lease_token": second_claim["lease_token"]}
        )
        assert second_execution.status_code == 200
        assert second_execution.json()["status"] == "succeeded"
        scoring_claim = client.post("/api/v1/workers/claim", json={"worker_id": "worker-c"}).json()
        assert scoring_claim["task_type"] == "scoring"
        assert (
            client.post(
                f"/api/v1/workers/tasks/{scoring_claim['id']}/execute",
                json={"lease_token": scoring_claim["lease_token"]},
            ).json()["status"]
            == "succeeded"
        )
        aggregation_claim = client.post("/api/v1/workers/claim", json={"worker_id": "worker-d"}).json()
        assert aggregation_claim["task_type"] == "aggregation"
        assert (
            client.post(
                f"/api/v1/workers/tasks/{aggregation_claim['id']}/execute",
                json={"lease_token": aggregation_claim["lease_token"]},
            ).json()["status"]
            == "succeeded"
        )
        report_claim = client.post("/api/v1/workers/claim", json={"worker_id": "worker-e"}).json()
        assert report_claim["task_type"] == "report_generation"
        assert (
            client.post(
                f"/api/v1/workers/tasks/{report_claim['id']}/execute", json={"lease_token": report_claim["lease_token"]}
            ).json()["status"]
            == "succeeded"
        )
        final_run = client.get(f"/api/v1/evaluation-runs/{run['id']}").json()
        assert final_run["status"] == "completed"
        assert len(client.get(f"/api/v1/reports/run/{run['id']}").json()) == 1
        attempts = client.get(f"/api/v1/evaluation-runs/{run['id']}/attempts").json()
        assert [(attempt["attempt_number"], attempt["status"]) for attempt in attempts] == [
            (1, "retry_scheduled"),
            (2, "succeeded"),
        ]


def test_report_generation_failure_preserves_completed_evaluation_results(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            data_root=str(tmp_path / "data"),
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
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post(
            "/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}
        ).json()
        for worker_id, task_type in (
            ("worker-evaluation", "evaluation_shard"),
            ("worker-scoring", "scoring"),
            ("worker-aggregation", "aggregation"),
        ):
            claim = client.post("/api/v1/workers/claim", json={"worker_id": worker_id}).json()
            assert claim["task_type"] == task_type
            assert (
                client.post(
                    f"/api/v1/workers/tasks/{claim['id']}/execute", json={"lease_token": claim["lease_token"]}
                ).status_code
                == 200
            )
        with app.state.database.get_session() as session:
            report_task = session.scalar(
                select(TaskUnit).where(TaskUnit.run_id == run["id"], TaskUnit.task_type == "report_generation")
            )
            assert report_task is not None
            report_task.payload = {**report_task.payload, "format": "unsupported"}
            session.commit()
        claim = client.post("/api/v1/workers/claim", json={"worker_id": "worker-report"}).json()
        assert claim["task_type"] == "report_generation"
        assert (
            client.post(
                f"/api/v1/workers/tasks/{claim['id']}/execute", json={"lease_token": claim["lease_token"]}
            ).status_code
            == 409
        )
        assert client.get(f"/api/v1/evaluation-runs/{run['id']}").json()["status"] == "completed"
        with app.state.database.get_session() as session:
            report_task = session.get(TaskUnit, claim["id"])
            assert report_task is not None
            assert report_task.status == "failed"


def test_run_preflight_estimates_work_without_creating_a_run(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
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
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        preflight = client.post(
            "/api/v1/evaluation-runs/validate", json={"model_endpoint_id": endpoint["id"], "sample_limit": 2}
        )
        assert preflight.status_code == 200
        assert preflight.json()["can_queue"] is True
        assert preflight.json()["sample_count"] == 2
        assert preflight.json()["estimated_requests"] == 2
        assert preflight.json()["estimated_cost"] is not None
        assert client.get("/api/v1/evaluation-runs").json() == []


def test_run_scheduling_controls_and_benchmark_rerun_preserve_source_evidence(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
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
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        source = client.post(
            "/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}
        ).json()
        assert (
            client.patch(f"/api/v1/evaluation-runs/{source['id']}/scheduling", json={"max_concurrency": 2}).json()[
                "max_concurrency"
            ]
            == 2
        )
        assert (
            client.patch(f"/api/v1/evaluation-runs/{source['id']}/scheduling", json={"max_concurrency": None}).json()[
                "max_concurrency"
            ]
            is None
        )
        assert client.post(f"/api/v1/evaluation-runs/{source['id']}/execute").json()["status"] == "completed"
        assert (
            client.patch(f"/api/v1/evaluation-runs/{source['id']}/scheduling", json={"max_concurrency": 1}).status_code
            == 409
        )
        rerun = client.post(f"/api/v1/evaluation-runs/{source['id']}/rerun-benchmark")
        assert rerun.status_code == 201
        assert rerun.json()["id"] != source["id"]
        assert rerun.json()["display_name"] == format_run_display_name(
            "example-model",
            "text-quick-check",
            datetime.fromisoformat(rerun.json()["created_at"]),
        )
        assert rerun.json()["configuration_snapshot"]["rerun_of"] == {"run_id": source["id"], "kind": "benchmark"}


def test_sample_attempt_list_uses_database_pagination_for_unfiltered_evidence(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
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
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post(
            "/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}
        ).json()
        with app.state.database.get_session() as session:
            task = session.scalar(
                select(TaskUnit).where(TaskUnit.run_id == run["id"], TaskUnit.task_type == "evaluation_shard")
            )
            assert task is not None
            session.add_all(
                SampleAttempt(
                    run_id=run["id"],
                    task_id=task.id,
                    sample_id=f"bulk-{index:03d}",
                    input_snapshot={"messages": [{"role": "user", "content": "small evidence"}]},
                    reference_snapshot={"type": "exact_match", "answer": "ok"},
                )
                for index in range(205)
            )
            session.commit()
        first = client.get(f"/api/v1/evaluation-runs/{run['id']}/attempts?offset=0&limit=200")
        second = client.get(f"/api/v1/evaluation-runs/{run['id']}/attempts?offset=200&limit=200")
        assert len(first.json()) == 200
        assert len(second.json()) == 6
        assert {item["sample_id"] for item in first.json()}.isdisjoint({item["sample_id"] for item in second.json()})


def test_declared_dataset_is_prepared_before_benchmark_execution(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "declared-samples.jsonl"
    source.write_text('{"question":"2 + 2"}\n', encoding="utf-8")
    _configure_dataset_download(monkeypatch, source.read_bytes())
    plugin = SimpleNamespace(
        manifest={
            "benchmark_id": "text-quick-check",
            "version": "1.0.0",
            "required_capabilities": ["text_input"],
            "scoring": {"type": "exact_match"},
            "datasets": [{"dataset_id": "declared-samples", "version": "2026.07"}],
        },
        samples=lambda _limit: (TextSample("declared-001", "Reply with only the number: what is 2 + 2?", "4"),),
    )
    monkeypatch.setattr("app.modules.evaluations.service.get_installed_plugin", lambda *_args: plugin)
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            data_root=str(tmp_path / "data"),
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        ),
        connection_tester=SuccessfulTester(),
        model_executor=ExactAnswerExecutor(),
    )
    with TestClient(app) as client:
        dataset = client.post(
            "/api/v1/datasets",
            json={
                "dataset_id": "declared-samples",
                "version": "2026.07",
                "source_url": "https://datasets.example.test/declared-samples.jsonl",
            },
        )
        assert dataset.status_code == 201
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models.example.test/v1",
                "api_key": "test-secret-key",
                "model_name": "example-model",
            },
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1})
        assert run.status_code == 201
        assert run.json()["status"] == "waiting_for_dataset"
        assert run.json()["configuration_snapshot"]["datasets"][0]["dataset_version_id"] == dataset.json()["id"]
        assert client.delete(f"/api/v1/datasets/{dataset.json()['id']}/cache").status_code == 409

        preparation = client.post("/api/v1/workers/claim", json={"worker_id": "dataset-worker"}).json()
        assert preparation["task_type"] == "dataset_preparation"
        assert preparation["payload"]["datasets"][0]["dataset_version_id"] == dataset.json()["id"]
        prepared = client.post(
            f"/api/v1/workers/tasks/{preparation['id']}/execute", json={"lease_token": preparation["lease_token"]}
        )
        assert prepared.status_code == 200
        assert prepared.json()["status"] == "succeeded"
        datasets = {item["id"]: item for item in client.get("/api/v1/datasets").json()}
        assert datasets[dataset.json()["id"]]["status"] == "ready"
        assert client.get(f"/api/v1/evaluation-runs/{run.json()['id']}").json()["status"] == "queued"

        benchmark = client.post("/api/v1/workers/claim", json={"worker_id": "benchmark-worker"}).json()
        assert benchmark["task_type"] == "benchmark"
        assert (
            client.post(
                f"/api/v1/workers/tasks/{benchmark['id']}/execute", json={"lease_token": benchmark["lease_token"]}
            ).json()["status"]
            == "succeeded"
        )
        execution = client.post("/api/v1/workers/claim", json={"worker_id": "evaluation-worker"}).json()
        assert execution["task_type"] == "evaluation_shard"
        assert (
            client.post(
                f"/api/v1/workers/tasks/{execution['id']}/execute", json={"lease_token": execution["lease_token"]}
            ).json()["status"]
            == "succeeded"
        )


def test_manifest_dataset_source_is_registered_and_prepared_automatically(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "manifest-samples.jsonl"
    source.write_text('{"question":"2 + 2"}\n', encoding="utf-8")
    _configure_dataset_download(monkeypatch, source.read_bytes())
    plugin = SimpleNamespace(
        manifest={
            "benchmark_id": "text-quick-check",
            "version": "1.0.0",
            "required_capabilities": ["text_input"],
            "scoring": {"type": "exact_match"},
            "datasets": [
                {
                    "dataset_id": "manifest-samples",
                    "version": "2026.07",
                    "revision": "r1",
                    "source_url": "https://datasets.example.test/manifest-samples.jsonl",
                }
            ],
        },
        samples=lambda _limit: (TextSample("manifest-001", "Reply with only the number: what is 2 + 2?", "4"),),
    )
    monkeypatch.setattr("app.modules.evaluations.service.get_installed_plugin", lambda *_args: plugin)
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            data_root=str(tmp_path / "data"),
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
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        preflight = client.post(
            "/api/v1/evaluation-runs/validate", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}
        )
        assert preflight.status_code == 200
        assert preflight.json()["can_queue"] is True
        assert preflight.json()["datasets"] == [
            {
                "dataset_id": "manifest-samples",
                "version": "2026.07",
                "revision": "r1",
                "status": "will_register",
                "will_prepare": True,
            }
        ]

        run = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1})
        assert run.status_code == 201
        assert run.json()["status"] == "waiting_for_dataset"
        dataset_id = run.json()["configuration_snapshot"]["datasets"][0]["dataset_version_id"]
        datasets = {item["id"]: item for item in client.get("/api/v1/datasets").json()}
        assert datasets[dataset_id]["source_url"] == "https://datasets.example.test/manifest-samples.jsonl"
        assert datasets[dataset_id]["status"] == "not_downloaded"

        preparation = client.post("/api/v1/workers/claim", json={"worker_id": "dataset-worker"}).json()
        assert preparation["task_type"] == "dataset_preparation"
        assert (
            client.post(
                f"/api/v1/workers/tasks/{preparation['id']}/execute", json={"lease_token": preparation["lease_token"]}
            ).json()["status"]
            == "succeeded"
        )
        assert {item["id"]: item for item in client.get("/api/v1/datasets").json()}[dataset_id]["status"] == "ready"


def test_non_inference_worker_interfaces_are_independently_leased_and_audited(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
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
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post(
            "/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}
        ).json()
        with app.state.database.get_session() as session:
            for priority, task_type in enumerate(("dataset_preparation", "benchmark", "judge", "cleanup"), start=10):
                session.add(
                    TaskUnit(run_id=run["id"], task_type=task_type, payload={"stage": task_type}, priority=priority)
                )
            session.commit()
        completed = []
        for _ in range(4):
            claim = client.post("/api/v1/workers/claim", json={"worker_id": "stage-worker"}).json()
            assert claim is not None
            completed.append(claim["task_type"])
            result = client.post(
                f"/api/v1/workers/tasks/{claim['id']}/execute", json={"lease_token": claim["lease_token"]}
            )
            assert result.status_code == 200
            assert result.json()["status"] == "succeeded"
            assert result.json()["payload"]["worker_interface"] == claim["task_type"]
        assert set(completed) == {"dataset_preparation", "benchmark", "judge", "cleanup"}


def test_retry_after_and_total_wait_bound_are_recorded_without_requeuing(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        ),
        connection_tester=SuccessfulTester(),
        model_executor=RetryAfterExecutor(),
    )
    with TestClient(app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models.example.test/v1",
                "api_key": "test-secret-key",
                "model_name": "example-model",
            },
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post(
            "/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}
        ).json()
        with app.state.database.get_session() as session:
            task = session.scalar(
                select(TaskUnit).where(TaskUnit.run_id == run["id"], TaskUnit.task_type == "evaluation_shard")
            )
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
            task = session.scalar(
                select(TaskUnit).where(TaskUnit.run_id == run["id"], TaskUnit.task_type == "evaluation_shard")
            )
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
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        ),
        connection_tester=SuccessfulTester(),
        model_executor=executor,
    )
    with TestClient(app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models.example.test/v1",
                "api_key": "test-secret-key",
                "model_name": "example-model",
            },
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post(
            "/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}
        ).json()
        cloned = client.post(f"/api/v1/evaluation-runs/{run['id']}/clone")
        assert cloned.status_code == 201
        assert cloned.json()["id"] != run["id"]
        assert cloned.json()["display_name"] == format_run_display_name(
            "example-model",
            "text-quick-check",
            datetime.fromisoformat(cloned.json()["created_at"]),
        )
        assert cloned.json()["configuration_snapshot"]["sample_ids"] == run["configuration_snapshot"]["sample_ids"]

        first_execution = client.post(f"/api/v1/evaluation-runs/{run['id']}/execute")
        assert first_execution.json()["status"] == "completed_with_errors"
        retried = client.post(f"/api/v1/evaluation-runs/{run['id']}/retry-failed")
        assert retried.status_code == 200
        assert retried.json()["status"] == "queued"
        assert retried.json()["display_name"] == run["display_name"]

        executor.fail = False
        second_execution = client.post(f"/api/v1/evaluation-runs/{run['id']}/execute")
        assert second_execution.json()["status"] == "completed"
        attempts = client.get(f"/api/v1/evaluation-runs/{run['id']}/attempts").json()
        assert [(attempt["attempt_number"], attempt["status"]) for attempt in attempts] == [
            (1, "failed"),
            (2, "succeeded"),
        ]


def test_expired_worker_lease_requeues_only_inflight_sample_attempts(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
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
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post(
            "/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}
        ).json()
        claim = client.post("/api/v1/workers/claim", json={"worker_id": "crashed-worker"}).json()
        with app.state.database.get_session() as session:
            task = session.get(TaskUnit, claim["id"])
            attempt = session.scalar(select(SampleAttempt).where(SampleAttempt.task_id == claim["id"]))
            assert task is not None and attempt is not None
            task.status = "running"
            task.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            attempt.status = "running"
            session.commit()
        assert client.post("/api/v1/workers/reclaim-expired").json() == {"reclaimed": 1}
        recovered = client.post("/api/v1/workers/claim", json={"worker_id": "recovery-worker"}).json()
        assert recovered["id"] == claim["id"]
        attempts = client.get(f"/api/v1/evaluation-runs/{run['id']}/attempts").json()
        assert attempts[0]["status"] == "pending"


def test_worker_claim_honors_endpoint_concurrency_and_rpm_budgets(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setattr("app.modules.evaluations.queue.datetime", _FixedNow)
    app = create_app(
        Settings.local_development(
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
                "max_concurrency": 1,
            },
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        first_run = client.post(
            "/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}
        ).json()
        client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1})
        assert client.post("/api/v1/workers/claim", json={"worker_id": "worker-a"}).json()["run_id"] == first_run["id"]
        assert client.post("/api/v1/workers/claim", json={"worker_id": "worker-b"}).json() is None

    rpm_app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'rpm.db'}", secret_encryption_key=Fernet.generate_key().decode("utf-8")
        ),
        connection_tester=SuccessfulTester(),
    )
    with TestClient(rpm_app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models.example.test/v1",
                "api_key": "test-secret-key",
                "model_name": "example-model",
                "max_concurrency": 3,
                "requests_per_minute": 1,
            },
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1})
        client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1})
        assert client.post("/api/v1/workers/claim", json={"worker_id": "worker-a"}).json() is not None
        assert client.post("/api/v1/workers/claim", json={"worker_id": "worker-b"}).json() is None
        with rpm_app.state.database.get_session() as session:
            window = session.scalar(select(EndpointRateWindow))
            assert window is not None
            assert window.request_count == 1


def test_worker_claim_honors_system_and_worker_concurrency_limits(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
            system_max_concurrency=1,
            worker_max_concurrency=1,
        ),
        connection_tester=SuccessfulTester(),
    )
    with TestClient(app) as client:
        endpoint_a = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models-a.example.test/v1",
                "api_key": "secret-a",
                "model_name": "a",
                "max_concurrency": 3,
            },
        ).json()
        endpoint_b = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models-b.example.test/v1",
                "api_key": "secret-b",
                "model_name": "b",
                "max_concurrency": 3,
            },
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint_a['id']}/connection-test").status_code == 200
        assert client.post(f"/api/v1/model-endpoints/{endpoint_b['id']}/connection-test").status_code == 200
        assert (
            client.post(
                "/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint_a["id"], "sample_limit": 1}
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint_b["id"], "sample_limit": 1}
            ).status_code
            == 201
        )
        first = client.post("/api/v1/workers/claim", json={"worker_id": "worker-a"})
        assert first.status_code == 200 and first.json() is not None
        assert client.post("/api/v1/workers/claim", json={"worker_id": "worker-a"}).json() is None
        assert client.post("/api/v1/workers/claim", json={"worker_id": "worker-b"}).json() is None


class _FixedNow:
    """Deterministic clock for rate-window tests: every claim shares one second.

    Pinned to now + 1 hour so real-clock lease checks in the executor (which
    use their own unpatched ``datetime``) still see the lease as valid while
    the patched claim path sees one fixed second.
    """

    fixed: datetime = datetime.now(timezone.utc) + timedelta(hours=1)

    @classmethod
    def now(cls, tz: object = None) -> datetime:
        del tz
        return cls.fixed


def test_worker_claim_honors_rps_and_directional_token_budgets(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setattr("app.modules.evaluations.queue.datetime", _FixedNow)
    rps_app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'rps.db'}", secret_encryption_key=Fernet.generate_key().decode("utf-8")
        ),
        connection_tester=SuccessfulTester(),
    )
    with TestClient(rps_app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models.example.test/v1",
                "api_key": "secret",
                "model_name": "model",
                "max_concurrency": 3,
                "requests_per_second": 1,
            },
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        assert (
            client.post(
                "/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}
            ).status_code
            == 201
        )
        assert client.post("/api/v1/workers/claim", json={"worker_id": "worker-a"}).json() is not None
        assert client.post("/api/v1/workers/claim", json={"worker_id": "worker-b"}).json() is None
        with rps_app.state.database.get_session() as session:
            assert session.scalar(select(EndpointSecondRateWindow)).request_count == 1

    tokens_app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'tokens.db'}",
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        ),
        connection_tester=SuccessfulTester(),
    )
    with TestClient(tokens_app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models.example.test/v1",
                "api_key": "secret",
                "model_name": "model",
                "max_concurrency": 3,
                "output_tokens_per_minute": 16,
            },
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        response = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1})
        assert response.status_code == 409
        assert "token budget" in response.json()["detail"]


def test_token_limited_runs_split_shards_before_admission(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'token-shards.db'}",
            secret_encryption_key=Fernet.generate_key().decode(),
        ),
        connection_tester=SuccessfulTester(),
    )
    with TestClient(app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models.example.test/v1",
                "api_key": "secret",
                "model_name": "model",
                "tokens_per_minute": 100,
            },
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        created = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"]})
        assert created.status_code == 201
        with app.state.database.get_session() as session:
            shards = list(
                session.scalars(
                    select(TaskUnit).where(
                        TaskUnit.run_id == created.json()["id"], TaskUnit.task_type == "evaluation_shard"
                    )
                )
            )
            assert len(shards) > 1
            assert all(task.payload["estimated_token_count"] <= 100 for task in shards)


def test_low_rps_runs_split_requests_and_continue_when_the_next_window_opens(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setattr("app.modules.evaluations.queue.datetime", _FixedNow)
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'rps-continuation.db'}",
            secret_encryption_key=Fernet.generate_key().decode(),
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
                "requests_per_second": 1,
            },
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"]}).json()
        with app.state.database.get_session() as session:
            shards = list(
                session.scalars(
                    select(TaskUnit).where(TaskUnit.run_id == run["id"], TaskUnit.task_type == "evaluation_shard")
                )
            )
            assert len(shards) == run["total_samples"]
            assert all(task.payload["estimated_request_count"] == 1 for task in shards)

        first_window = client.post(f"/api/v1/evaluation-runs/{run['id']}/execute")
        assert first_window.status_code == 200
        assert first_window.json()["status"] == "running"
        for _ in range(run["total_samples"] - 1):
            with app.state.database.get_session() as session:
                rate_window = session.scalar(select(EndpointSecondRateWindow))
                assert rate_window is not None
                # Simulate the next fixed one-second provider window.
                rate_window.request_count = 0
                session.commit()
            resumed = client.post(f"/api/v1/evaluation-runs/{run['id']}/execute")
            assert resumed.status_code == 200

        assert resumed.json()["status"] == "completed"


def test_reclaimed_worker_cannot_persist_a_late_model_result(tmp_path: Path) -> None:
    class LeaseLosingExecutor:
        def execute(self, _endpoint, _api_key: str, _input_snapshot: dict[str, object]) -> SampleExecutionResult:
            with app.state.database.get_session() as session:
                task = session.scalar(
                    select(TaskUnit).where(TaskUnit.task_type == "evaluation_shard", TaskUnit.status == "running")
                )
                assert task is not None
                task.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                session.commit()
                assert reclaim_expired_leases(session) == 1
            return SampleExecutionResult(True, {"model": "late"}, '{"choices":[{"message":{"content":"4"}}]}', "4")

    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'late-result.db'}",
            secret_encryption_key=Fernet.generate_key().decode(),
        ),
        connection_tester=SuccessfulTester(),
        model_executor=LeaseLosingExecutor(),
    )
    with TestClient(app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "model"},
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post(
            "/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}
        ).json()
        claim = client.post("/api/v1/workers/claim", json={"worker_id": "worker-a", "run_id": run["id"]}).json()
        assert claim is not None
        late = client.post(f"/api/v1/workers/tasks/{claim['id']}/execute", json={"lease_token": claim["lease_token"]})
        assert late.status_code == 409
        attempt = client.get(f"/api/v1/evaluation-runs/{run['id']}/attempts").json()[0]
        assert attempt["status"] == "pending"
        assert attempt["raw_response"] is None


def test_pause_invalidates_a_running_lease_before_a_late_result_can_commit(tmp_path: Path) -> None:
    class PausingExecutor:
        def execute(self, _endpoint, _api_key: str, _input_snapshot: dict[str, object]) -> SampleExecutionResult:
            with app.state.database.get_session() as session:
                run = session.scalar(select(EvaluationRun).where(EvaluationRun.status == "running"))
                assert run is not None
                app.state.evaluation_service.pause(run.id)
            return SampleExecutionResult(True, {"model": "late"}, '{"choices":[{"message":{"content":"4"}}]}', "4")

    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'pause-result.db'}",
            secret_encryption_key=Fernet.generate_key().decode(),
        ),
        connection_tester=SuccessfulTester(),
        model_executor=PausingExecutor(),
    )
    with TestClient(app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "model"},
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post(
            "/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}
        ).json()
        claim = client.post("/api/v1/workers/claim", json={"worker_id": "worker-a", "run_id": run["id"]}).json()
        late = client.post(f"/api/v1/workers/tasks/{claim['id']}/execute", json={"lease_token": claim["lease_token"]})
        assert late.status_code == 409
        assert client.get(f"/api/v1/evaluation-runs/{run['id']}").json()["status"] == "paused"
        attempt = client.get(f"/api/v1/evaluation-runs/{run['id']}/attempts").json()[0]
        assert attempt["status"] == "pending"
        assert attempt["raw_response"] is None


def test_queued_run_uses_frozen_endpoint_configuration_and_rotated_secret(tmp_path: Path) -> None:
    captured: list[tuple[str, str, int, dict[str, object], str]] = []

    class SnapshotExecutor:
        def execute(self, endpoint, api_key: str, input_snapshot: dict[str, object]) -> SampleExecutionResult:
            captured.append(
                (endpoint.base_url, endpoint.model_name, endpoint.timeout_seconds, endpoint.custom_headers, api_key)
            )
            return SampleExecutionResult(
                True, {"model": endpoint.model_name}, '{"choices":[{"message":{"content":"4"}}]}', "4"
            )

    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'snapshot.db'}", secret_encryption_key=Fernet.generate_key().decode()
        ),
        connection_tester=SuccessfulTester(),
        model_executor=SnapshotExecutor(),
    )
    with TestClient(app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models.example.test/v1",
                "api_key": "initial-secret",
                "model_name": "frozen-model",
                "timeout_seconds": 42,
                "custom_headers": {"X-Run-Mode": "frozen"},
                "default_request_body": {"temperature": 0.1},
            },
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post(
            "/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}
        ).json()
        changed = client.patch(
            f"/api/v1/model-endpoints/{endpoint['id']}",
            json={
                "base_url": "https://changed.models.example.test/v1",
                "api_key": "rotated-secret",
                "model_name": "changed-model",
                "timeout_seconds": 5,
                "custom_headers": {"X-Run-Mode": "changed"},
                "default_request_body": {"temperature": 0.9},
            },
        )
        assert changed.status_code == 200
        assert client.post(f"/api/v1/evaluation-runs/{run['id']}/execute").json()["status"] == "completed"

    assert captured == [
        ("https://models.example.test/v1", "frozen-model", 42, {"X-Run-Mode": "frozen"}, "rotated-secret")
    ]


def test_worker_claim_honors_run_and_shared_api_key_concurrency_limits(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'limits.db'}", secret_encryption_key=Fernet.generate_key().decode()
        ),
        connection_tester=SuccessfulTester(),
    )
    with TestClient(app) as client:
        first_endpoint = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models-a.example.test/v1",
                "api_key": "shared-provider-key",
                "model_name": "a",
                "max_concurrency": 3,
                "api_key_max_concurrency": 1,
            },
        ).json()
        second_endpoint = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models-b.example.test/v1",
                "api_key": "shared-provider-key",
                "model_name": "b",
                "max_concurrency": 3,
                "api_key_max_concurrency": 1,
            },
        ).json()
        for endpoint in (first_endpoint, second_endpoint):
            assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        first_run = client.post(
            "/api/v1/evaluation-runs",
            json={"model_endpoint_id": first_endpoint["id"], "sample_limit": 1, "max_concurrency": 1},
        ).json()
        second_run = client.post(
            "/api/v1/evaluation-runs", json={"model_endpoint_id": second_endpoint["id"], "sample_limit": 1}
        ).json()
        with app.state.database.get_session() as session:
            session.add(
                TaskUnit(
                    run_id=first_run["id"],
                    task_type="evaluation_shard",
                    payload={"sample_ids": ["extra"], "estimated_request_count": 1, "estimated_token_count": 1},
                )
            )
            session.commit()
            assert claim_task(session, "worker-a", run_id=first_run["id"]) is not None
            assert claim_task(session, "worker-b", run_id=first_run["id"]) is None
            assert claim_task(session, "worker-c", run_id=second_run["id"]) is None


def test_worker_claim_honors_benchmark_concurrency_limits(tmp_path: Path) -> None:
    benchmark_app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'benchmark-limits.db'}",
            secret_encryption_key=Fernet.generate_key().decode(),
        ),
        connection_tester=SuccessfulTester(),
    )
    with TestClient(benchmark_app) as client:
        endpoints = [
            client.post(
                "/api/v1/model-endpoints",
                json={
                    "base_url": f"https://benchmark-{name}.example.test/v1",
                    "api_key": f"benchmark-key-{name}",
                    "model_name": name,
                    "max_concurrency": 3,
                },
            ).json()
            for name in ("a", "b")
        ]
        for endpoint in endpoints:
            assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        with benchmark_app.state.database.get_session() as session:
            definition = session.scalar(
                select(BenchmarkDefinition).where(
                    BenchmarkDefinition.benchmark_id == "text-quick-check", BenchmarkDefinition.version == "1.0.0"
                )
            )
            assert definition is not None
            definition.manifest = {**definition.manifest, "max_concurrency": 1}
            session.commit()
        runs = [
            client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}).json()
            for endpoint in endpoints
        ]
        with benchmark_app.state.database.get_session() as session:
            assert claim_task(session, "worker-a", run_id=runs[0]["id"]) is not None
            assert claim_task(session, "worker-b", run_id=runs[1]["id"]) is None


def test_run_snapshots_a_versioned_prompt_package(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
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
        ).json()
        with app.state.database.get_session() as session:
            item = session.get(ModelEndpoint, endpoint["id"])
            assert item is not None
            item.status = "available"
            session.commit()
        prompt = client.post(
            "/api/v1/prompt-packages",
            json={
                "name": "strict",
                "version": "1",
                "user_template": "Answer only: {{ question }}",
                "system_message": "Be concise.",
            },
        ).json()
        run = client.post(
            "/api/v1/evaluation-runs",
            json={"model_endpoint_id": endpoint["id"], "sample_limit": 1, "prompt_package_id": prompt["id"]},
        )
        assert run.status_code == 201
        attempts = client.get(f"/api/v1/evaluation-runs/{run.json()['id']}/attempts").json()
        assert attempts[0]["input_snapshot"]["messages"][0]["role"] == "system"
        assert "Answer only:" in attempts[0]["input_snapshot"]["messages"][-1]["content"]


def test_prompt_scoring_rule_is_snapshotted_and_applied_to_execution(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'scoring.db'}", secret_encryption_key=Fernet.generate_key().decode()
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
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        prompt = client.post(
            "/api/v1/prompt-packages",
            json={
                "name": "regex-score",
                "version": "1",
                "user_template": "{{ question }}",
                "scoring_rule": {"type": "regex_match", "pattern": "BLUE"},
            },
        ).json()
        run = client.post(
            "/api/v1/evaluation-runs",
            json={"model_endpoint_id": endpoint["id"], "sample_limit": 1, "prompt_package_id": prompt["id"]},
        ).json()
        assert client.post(f"/api/v1/evaluation-runs/{run['id']}/execute").status_code == 200
        attempt = client.get(f"/api/v1/evaluation-runs/{run['id']}/attempts").json()[0]
        assert attempt["reference_snapshot"]["scoring"] == {"type": "regex_match", "pattern": "BLUE"}
        assert attempt["status"] == "succeeded"
        assert attempt["score"] == 0.0


def test_terminal_run_must_be_archived_before_deletion(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'archive.db'}", secret_encryption_key=Fernet.generate_key().decode()
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
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post(
            "/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}
        ).json()
        assert client.post(f"/api/v1/evaluation-runs/{run['id']}/execute").json()["status"] == "completed"
        assert client.delete(f"/api/v1/evaluation-runs/{run['id']}").status_code == 409
        archived = client.post(f"/api/v1/evaluation-runs/{run['id']}/archive")
        assert archived.status_code == 200
        assert archived.json()["archived_at"] is not None
        assert client.get("/api/v1/evaluation-runs").json() == []
        assert client.get(f"/api/v1/evaluation-runs/{run['id']}").status_code == 200
        assert client.delete(f"/api/v1/evaluation-runs/{run['id']}").status_code == 204
        assert client.get(f"/api/v1/evaluation-runs/{run['id']}").status_code == 404
