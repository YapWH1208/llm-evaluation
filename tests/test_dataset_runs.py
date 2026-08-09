import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.connection_tester import ConnectionTestResult
from app.services.model_executor import SampleExecutionResult
from cryptography.fernet import Fernet


class _SuccessfulTester:
    def test(self, _endpoint, _api_key: str) -> ConnectionTestResult:
        return ConnectionTestResult(True, "Connection succeeded.", 200)


class _DatasetAnswerExecutor:
    def execute(self, endpoint, _api_key: str, input_snapshot: dict[str, object]) -> SampleExecutionResult:
        prompt = str(input_snapshot["messages"][-1]["content"])
        prediction = "4" if "2+2" in prompt else "6"
        return SampleExecutionResult(
            success=True,
            request_snapshot={"model": endpoint.model_name, "messages": input_snapshot["messages"]},
            raw_response=f'{{"choices":[{{"message":{{"content":"{prediction}"}}}}]}}',
            prediction=prediction,
            latency_ms=125.5,
            input_tokens=10,
            output_tokens=5,
        )


def _create_available_endpoint(client: TestClient) -> str:
    created = client.post(
        "/api/v1/model-endpoints",
        json={"base_url": "https://models.example.test/v1", "api_key": "test-secret-key", "model_name": "example-model"},
    )
    assert created.status_code == 201
    endpoint_id = created.json()["id"]
    assert client.post(f"/api/v1/model-endpoints/{endpoint_id}/connection-test").status_code == 200
    return endpoint_id


def _register_ready_dataset(
    client: TestClient,
    dataset_id: str = "demo",
    content: bytes | None = None,
) -> dict[str, object]:
    created = client.post(
        "/api/v1/datasets",
        json={"dataset_id": dataset_id, "version": "1", "revision": "main"},
    )
    assert created.status_code == 201
    version_id = created.json()["id"]
    content = content or b'{"question":"what is 2+2?","answer":"4"}\n{"question":"what is 3+3?","answer":"6"}\n'
    uploaded = client.post(
        f"/api/v1/datasets/{version_id}/upload",
        json={"filename": "examples.jsonl", "base64_data": base64.b64encode(content).decode("ascii")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["status"] == "ready"
    return uploaded.json()


def _prompt_package(client: TestClient) -> str:
    created = client.post(
        "/api/v1/prompt-packages",
        json={"name": "record-template", "version": "1.0.0", "prompt_type": "user_custom", "user_template": "Q: {{question}}\nA:", "system_message": "Answer only the number.", "few_shot_examples": [{"role": "assistant", "content": "4"}], "scoring_rule": {"type": "exact_match"}},
    )
    assert created.status_code == 201
    return created.json()["id"]


def test_dataset_run_service_manifest_identity() -> None:
    from app.services.dataset_runs import (
        DATASET_RUN_BENCHMARK_ID,
        DATASET_RUN_BENCHMARK_VERSION,
        DATASET_RUN_DEFAULT_SAMPLE_LIMIT,
        _DATASET_RUN_MANIFEST,
    )

    assert DATASET_RUN_BENCHMARK_ID == "dataset-evaluation"
    assert DATASET_RUN_BENCHMARK_VERSION == "1.0.0"
    assert DATASET_RUN_DEFAULT_SAMPLE_LIMIT == 100
    assert _DATASET_RUN_MANIFEST["benchmark_id"] == DATASET_RUN_BENCHMARK_ID
    assert _DATASET_RUN_MANIFEST["shard_size"] == 50


def test_dataset_run_end_to_end(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", data_root=str(tmp_path / "data"), secret_encryption_key=Fernet.generate_key().decode("utf-8")),
        connection_tester=_SuccessfulTester(),
        model_executor=_DatasetAnswerExecutor(),
    )
    with TestClient(app) as client:
        dataset = _register_ready_dataset(client)
        endpoint_id = _create_available_endpoint(client)
        package_id = _prompt_package(client)
        created = client.post(
            "/api/v1/evaluation-runs/dataset",
            json={
                "model_endpoint_id": endpoint_id,
                "dataset_version_id": dataset["id"],
                "prompt_package_id": package_id,
                "reference_field": "answer",
                "sample_limit": 10,
            },
        )
        assert created.status_code == 201
        run = created.json()
        assert run["benchmark_id"] == "dataset-evaluation"
        assert run["total_samples"] == 2
        assert run["configuration_snapshot"]["reference_field"] == "answer"
        executed = client.post(f"/api/v1/evaluation-runs/{run['id']}/execute")
        assert executed.status_code == 200
        assert executed.json()["status"] == "completed"
        assert executed.json()["successful_samples"] == 2
        attempts = client.get(f"/api/v1/evaluation-runs/{run['id']}/attempts").json()
        assert len(attempts) == 2
        message_lists = [attempt["input_snapshot"]["messages"] for attempt in attempts]
        assert all(messages[0] == {"role": "system", "content": "Answer only the number."} for messages in message_lists)
        assert all(messages[1] == {"role": "assistant", "content": "4"} for messages in message_lists)
        contents = {messages[2]["content"] for messages in message_lists}
        assert contents == {"Q: what is 2+2?\nA:", "Q: what is 3+3?\nA:"}
        assert {attempt["reference_snapshot"]["answer"] for attempt in attempts} == {"4", "6"}
        assert {attempt["score"] for attempt in attempts} == {1.0}


def test_dataset_run_preflight_and_validation_errors(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", data_root=str(tmp_path / "data"), secret_encryption_key=Fernet.generate_key().decode("utf-8")),
        connection_tester=_SuccessfulTester(),
        model_executor=_DatasetAnswerExecutor(),
    )
    with TestClient(app) as client:
        dataset = _register_ready_dataset(client)
        endpoint_id = _create_available_endpoint(client)
        preflight = client.post(
            "/api/v1/evaluation-runs/dataset/preflight",
            json={"model_endpoint_id": endpoint_id, "dataset_version_id": dataset["id"], "reference_field": "answer", "sample_limit": 10},
        )
        assert preflight.status_code == 200
        assert preflight.json()["can_queue"] is True
        assert preflight.json()["sample_count"] == 2
        bad_field = client.post(
            "/api/v1/evaluation-runs/dataset",
            json={"model_endpoint_id": endpoint_id, "dataset_version_id": dataset["id"], "reference_field": "nope", "sample_limit": 10},
        )
        assert bad_field.status_code == 409
        assert "reference field" in bad_field.json()["detail"]
        not_ready = client.post(
            "/api/v1/evaluation-runs/dataset",
            json={"model_endpoint_id": endpoint_id, "dataset_version_id": "missing", "reference_field": "answer", "sample_limit": 10},
        )
        assert not_ready.status_code == 404
        missing_field = client.post(
            "/api/v1/evaluation-runs/dataset",
            json={"model_endpoint_id": endpoint_id, "dataset_version_id": dataset["id"], "reference_field": "", "sample_limit": 10},
        )
        assert missing_field.status_code == 422


def test_dataset_run_uses_selected_input_field_and_preserves_legacy_fallback(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
            data_root=str(tmp_path / "data"),
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        ),
        connection_tester=_SuccessfulTester(),
    )
    content = (
        b'{"distractor":"wrong-one","question":"chosen-one","answer":"1"}\n'
        b'{"distractor":"wrong-two","question":"chosen-two","answer":"2"}\n'
    )
    with TestClient(app) as client:
        dataset = _register_ready_dataset(client, content=content)
        endpoint_id = _create_available_endpoint(client)

        selected = client.post("/api/v1/evaluation-runs/dataset", json={
            "model_endpoint_id": endpoint_id,
            "dataset_version_id": dataset["id"],
            "input_field": "question",
            "reference_field": "answer",
            "sample_limit": 10,
        })
        assert selected.status_code == 201
        selected_run = selected.json()
        assert selected_run["configuration_snapshot"]["input_field"] == "question"
        assert selected_run["configuration_snapshot"]["reference_field"] == "answer"
        selected_attempts = client.get(
            f"/api/v1/evaluation-runs/{selected_run['id']}/attempts"
        ).json()
        assert {
            attempt["input_snapshot"]["messages"][-1]["content"]
            for attempt in selected_attempts
        } == {"chosen-one", "chosen-two"}

        legacy = client.post("/api/v1/evaluation-runs/dataset", json={
            "model_endpoint_id": endpoint_id,
            "dataset_version_id": dataset["id"],
            "reference_field": "answer",
            "sample_limit": 10,
        })
        assert legacy.status_code == 201
        assert legacy.json()["configuration_snapshot"]["input_field"] is None
        legacy_attempts = client.get(
            f"/api/v1/evaluation-runs/{legacy.json()['id']}/attempts"
        ).json()
        assert {
            attempt["input_snapshot"]["messages"][-1]["content"]
            for attempt in legacy_attempts
        } == {"wrong-one", "wrong-two"}

        bad_input = client.post("/api/v1/evaluation-runs/dataset/preflight", json={
            "model_endpoint_id": endpoint_id,
            "dataset_version_id": dataset["id"],
            "input_field": "missing",
            "reference_field": "answer",
            "sample_limit": 10,
        })
        assert bad_input.status_code == 200
        assert bad_input.json()["can_queue"] is False
        assert any("input field 'missing'" in issue for issue in bad_input.json()["issues"])

        blank_input = client.post("/api/v1/evaluation-runs/dataset", json={
            "model_endpoint_id": endpoint_id,
            "dataset_version_id": dataset["id"],
            "input_field": "",
            "reference_field": "answer",
            "sample_limit": 10,
        })
        assert blank_input.status_code == 422
