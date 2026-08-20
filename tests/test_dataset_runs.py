import base64
import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.infrastructure.providers.contracts import ConnectionTestResult, SampleExecutionResult
from app.services.run_names import format_run_display_name
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


class _AutomaticJudgeExecutor(_DatasetAnswerExecutor):
    def __init__(self, *, judge_succeeds: bool) -> None:
        self.judge_succeeds = judge_succeeds
        self.judge_inputs: list[dict[str, object]] = []

    def execute(self, endpoint, api_key: str, input_snapshot: dict[str, object]) -> SampleExecutionResult:
        if endpoint.model_name != "judge-model":
            return super().execute(endpoint, api_key, input_snapshot)
        self.judge_inputs.append(input_snapshot)
        if not self.judge_succeeds:
            return SampleExecutionResult(
                success=False,
                request_snapshot={"model": endpoint.model_name},
                raw_response=None,
                prediction=None,
                error_type="http_400",
                error_message="Judge rejected the assessment request.",
            )
        return SampleExecutionResult(
            success=True,
            request_snapshot={"model": endpoint.model_name},
            raw_response='{"choices":[{"message":{"content":"{\\"score\\": 0.75, \\"label\\": \\"pass\\", \\"rationale\\": \\"Matches the reference.\\"}"}}]}',
            prediction='{"score": 0.75, "label": "pass", "rationale": "Matches the reference."}',
            input_tokens=12,
            output_tokens=8,
        )


class _FrozenJudgeExecutor(_DatasetAnswerExecutor):
    def __init__(self) -> None:
        self.judge_calls: list[tuple[str, str, int, str]] = []

    def execute(self, endpoint, api_key: str, input_snapshot: dict[str, object]) -> SampleExecutionResult:
        if endpoint.model_name != "judge-model":
            return super().execute(endpoint, api_key, input_snapshot)
        self.judge_calls.append((endpoint.base_url, endpoint.model_name, endpoint.timeout_seconds, api_key))
        return SampleExecutionResult(
            success=True,
            request_snapshot={"model": endpoint.model_name},
            raw_response='{"choices":[{"message":{"content":"{\\"score\\": 0.75, \\"label\\": \\"pass\\", \\"rationale\\": \\"Matches the reference.\\"}"}}]}',
            prediction='{"score": 0.75, "label": "pass", "rationale": "Matches the reference."}',
            input_tokens=12,
            output_tokens=8,
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


def _prompt_package(
    client: TestClient,
    scoring_rule: dict[str, object] | None = None,
) -> str:
    created = client.post(
        "/api/v1/prompt-packages",
        json={"name": "record-template", "version": "1.0.0", "prompt_type": "user_custom", "user_template": "Q: {{question}}\nA:", "system_message": "Answer only the number.", "few_shot_examples": [{"role": "assistant", "content": "4"}], "scoring_rule": scoring_rule or {"type": "exact_match"}},
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


def test_effective_dataset_scoring_rule_uses_requested_package_default_precedence() -> None:
    from types import SimpleNamespace

    from app.services import dataset_runs

    package_rule = {"type": "regex_match", "pattern": "BLUE"}
    requested_rule = {"type": "token_f1"}

    assert dataset_runs.effective_dataset_scoring_rule(None, None) == {"type": "exact_match"}
    assert dataset_runs.effective_dataset_scoring_rule(
        None,
        SimpleNamespace(scoring_rule=package_rule),
    ) == package_rule
    effective = dataset_runs.effective_dataset_scoring_rule(
        requested_rule,
        SimpleNamespace(scoring_rule=package_rule),
    )
    requested_rule["type"] = "bleu"
    assert effective == {"type": "token_f1"}

    with pytest.raises(dataset_runs.DatasetRunError, match="Scoring rule is invalid:"):
        dataset_runs.effective_dataset_scoring_rule({"type": "unsupported"}, None)


def test_dataset_run_scoring_rule_precedence_validation_and_snapshots(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
            data_root=str(tmp_path / "data"),
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        ),
        connection_tester=_SuccessfulTester(),
    )
    with TestClient(app) as client:
        dataset = _register_ready_dataset(client)
        endpoint_id = _create_available_endpoint(client)
        package_rule = {"type": "regex_match", "pattern": "BLUE"}
        package_id = _prompt_package(client, package_rule)
        base_payload = {
            "model_endpoint_id": endpoint_id,
            "dataset_version_id": dataset["id"],
            "reference_field": "answer",
            "sample_limit": 10,
        }

        default_preflight = client.post(
            "/api/v1/evaluation-runs/dataset/preflight",
            json=base_payload,
        )
        assert default_preflight.status_code == 200
        assert default_preflight.json()["can_queue"] is True
        default_run = client.post("/api/v1/evaluation-runs/dataset", json=base_payload)
        assert default_run.status_code == 201
        assert default_run.json()["configuration_snapshot"]["scoring_rule"] == {"type": "exact_match"}

        package_payload = {**base_payload, "prompt_package_id": package_id}
        package_preflight = client.post(
            "/api/v1/evaluation-runs/dataset/preflight",
            json=package_payload,
        )
        assert package_preflight.status_code == 200
        assert package_preflight.json()["can_queue"] is True
        package_run = client.post("/api/v1/evaluation-runs/dataset", json=package_payload)
        assert package_run.status_code == 201
        assert package_run.json()["configuration_snapshot"]["scoring_rule"] == package_rule

        requested_rule = {"type": "token_f1"}
        requested_payload = {**package_payload, "scoring_rule": requested_rule}
        requested_preflight = client.post(
            "/api/v1/evaluation-runs/dataset/preflight",
            json=requested_payload,
        )
        assert requested_preflight.status_code == 200
        assert requested_preflight.json()["can_queue"] is True
        requested_run = client.post("/api/v1/evaluation-runs/dataset", json=requested_payload)
        assert requested_run.status_code == 201
        assert requested_run.json()["configuration_snapshot"]["scoring_rule"] == requested_rule

        expected_rules = {
            default_run.json()["id"]: {"type": "exact_match"},
            package_run.json()["id"]: package_rule,
            requested_run.json()["id"]: requested_rule,
        }
        for run_id, expected_rule in expected_rules.items():
            attempts = client.get(f"/api/v1/evaluation-runs/{run_id}/attempts").json()
            assert attempts
            assert all(attempt["reference_snapshot"]["scoring"] == expected_rule for attempt in attempts)

        judge = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://judge.example.test/v1",
                "api_key": "judge-secret-key",
                "model_name": "judge-model",
                "custom_headers": {"X-Judge-Secret": "must-not-appear"},
            },
        )
        assert judge.status_code == 201
        judge_id = judge.json()["id"]
        assert client.post(f"/api/v1/model-endpoints/{judge_id}/connection-test").status_code == 200
        judge_rule = {
            "type": "LLM_JUDGE",
            "judge_endpoint_id": judge_id,
            "system_message": " Judge each candidate against the reference. ",
        }
        judge_payload = {**base_payload, "scoring_rule": judge_rule}
        judge_preflight = client.post("/api/v1/evaluation-runs/dataset/preflight", json=judge_payload)
        assert judge_preflight.status_code == 200
        assert judge_preflight.json()["can_queue"] is True
        assert judge_preflight.json()["judge_estimate"] == {
            "estimated_requests": 2,
            "estimated_input_tokens": judge_preflight.json()["estimated_input_tokens"] + 256,
            "estimated_output_tokens": 128,
            "estimated_cost": None,
            "currency": "USD",
        }
        judge_run = client.post("/api/v1/evaluation-runs/dataset", json=judge_payload)
        assert judge_run.status_code == 201
        judge_snapshot = judge_run.json()["configuration_snapshot"]
        expected_judge_rule = {
            "type": "llm_judge",
            "judge_endpoint_id": judge_id,
            "system_message": "Judge each candidate against the reference.",
        }
        assert judge_snapshot["scoring_rule"] == expected_judge_rule
        assert judge_snapshot["judge"] == {
            "endpoint": {
                "id": judge_id,
                "base_url": "https://judge.example.test/v1",
                "model_name": "judge-model",
                "protocol_profile": "openai_chat_completions",
                "timeout_seconds": 60,
                "input_cost_per_million": None,
                "output_cost_per_million": None,
                "currency": "USD",
            },
            "reference_field": "answer",
            "system_message": "Judge each candidate against the reference.",
        }
        assert "judge-secret-key" not in str(judge_snapshot)
        assert "must-not-appear" not in str(judge_snapshot)
        judge_attempts = client.get(f"/api/v1/evaluation-runs/{judge_run.json()['id']}/attempts").json()
        assert all(attempt["reference_snapshot"]["judge"] == judge_snapshot["judge"] for attempt in judge_attempts)

        unavailable_judge = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://offline-judge.example.test/v1",
                "api_key": "offline-judge-secret",
                "model_name": "offline-judge",
            },
        ).json()

        for invalid_rule, message in (
            ({**expected_judge_rule, "judge_endpoint_id": endpoint_id}, "cannot judge its own"),
            ({**expected_judge_rule, "judge_endpoint_id": "missing-judge"}, "Judge model endpoint not found"),
            ({**expected_judge_rule, "judge_endpoint_id": unavailable_judge["id"]}, "must pass a connection test"),
        ):
            invalid_payload = {**base_payload, "scoring_rule": invalid_rule}
            invalid_preflight = client.post("/api/v1/evaluation-runs/dataset/preflight", json=invalid_payload)
            assert invalid_preflight.status_code == 200
            assert invalid_preflight.json()["can_queue"] is False
            assert any(message in issue for issue in invalid_preflight.json()["issues"])
            assert client.post("/api/v1/evaluation-runs/dataset", json=invalid_payload).status_code == 409

        run_count = len(client.get("/api/v1/evaluation-runs").json())
        invalid_rule = {**base_payload, "scoring_rule": {"type": "regex_match"}}
        assert client.post(
            "/api/v1/evaluation-runs/dataset/preflight",
            json=invalid_rule,
        ).status_code == 422
        assert client.post(
            "/api/v1/evaluation-runs/dataset",
            json=invalid_rule,
        ).status_code == 422
        assert len(client.get("/api/v1/evaluation-runs").json()) == run_count


def test_dataset_run_end_to_end(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", data_root=str(tmp_path / "data"), secret_encryption_key=Fernet.generate_key().decode("utf-8")),
        connection_tester=_SuccessfulTester(),
        model_executor=_DatasetAnswerExecutor(),
    )
    with TestClient(app) as client:
        dataset = _register_ready_dataset(client)
        profiled = client.put(
            f"/api/v1/datasets/{dataset['id']}",
            json={
                "dataset_id": "demo",
                "version": "1",
                "input_field": "question",
                "reference_field": "answer",
                "capabilities": ["classification"],
                "languages": ["en"],
                "evaluation_type": "classification",
            },
        )
        assert profiled.status_code == 200
        dataset = profiled.json()
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
        assert run["display_name"] == format_run_display_name(
            "example-model",
            "demo",
            datetime.fromisoformat(run["created_at"]),
        )
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
        metrics = client.get(f"/api/v1/analytics/runs/{run['id']}/metrics")
        assert metrics.status_code == 200
        metrics_by_name = {metric["metric_name"]: metric for metric in metrics.json()}
        assert metrics_by_name["accuracy"]["metric_value"] == 1.0
        assert metrics_by_name["precision_macro"]["metric_value"] == 1.0
        assert metrics_by_name["recall_macro"]["metric_value"] == 1.0
        assert metrics_by_name["f1_macro"]["metric_value"] == 1.0


@pytest.mark.parametrize("judge_succeeds", [True, False], ids=["success", "failure"])
def test_dataset_run_automatically_records_llm_judge_evidence(
    tmp_path: Path,
    judge_succeeds: bool,
) -> None:
    executor = _AutomaticJudgeExecutor(judge_succeeds=judge_succeeds)
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
            data_root=str(tmp_path / "data"),
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        ),
        connection_tester=_SuccessfulTester(),
        model_executor=executor,
    )
    with TestClient(app) as client:
        dataset = _register_ready_dataset(client)
        assert client.put(
            f"/api/v1/datasets/{dataset['id']}",
            json={
                "dataset_id": "demo",
                "version": "1",
                "input_field": "question",
                "reference_field": "answer",
                "capabilities": ["classification"],
                "languages": ["en"],
                "evaluation_type": "classification",
            },
        ).status_code == 200
        target_id = _create_available_endpoint(client)
        judge = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://judge.example.test/v1",
                "api_key": "judge-secret",
                "model_name": "judge-model",
            },
        )
        assert judge.status_code == 201
        judge_id = judge.json()["id"]
        assert client.post(f"/api/v1/model-endpoints/{judge_id}/connection-test").status_code == 200
        system_message = "Score the candidate strictly against the dataset answer."
        run = client.post(
            "/api/v1/evaluation-runs/dataset",
            json={
                "model_endpoint_id": target_id,
                "dataset_version_id": dataset["id"],
                "prompt_package_id": _prompt_package(client),
                "reference_field": "answer",
                "sample_limit": 2,
                "scoring_rule": {
                    "type": "llm_judge",
                    "judge_endpoint_id": judge_id,
                    "system_message": system_message,
                },
            },
        )
        assert run.status_code == 201
        executed = client.post(f"/api/v1/evaluation-runs/{run.json()['id']}/execute")
        assert executed.status_code == 200
        assert executed.json()["status"] == "completed"
        assert executed.json()["successful_samples"] == 2

        attempts = client.get(f"/api/v1/evaluation-runs/{run.json()['id']}/attempts").json()
        assert {attempt["status"] for attempt in attempts} == {"succeeded"}
        assert {attempt["score"] for attempt in attempts} == {None}
        judge_evidence = [attempt["metric_evidence"]["llm_judge"] for attempt in attempts]
        expected_status = "succeeded" if judge_succeeds else "failed"
        assert {item["status"] for item in judge_evidence} == {expected_status}
        assert all("raw_response" not in item for item in judge_evidence)
        if judge_succeeds:
            assert {item["score"] for item in judge_evidence} == {0.75}
            assert {item["label"] for item in judge_evidence} == {"pass"}
        else:
            assert {item["error_message"] for item in judge_evidence} == {"Judge rejected the assessment request."}

        metrics = {
            item["metric_name"]: item
            for item in client.get(f"/api/v1/analytics/runs/{run.json()['id']}/metrics").json()
        }
        judge_metric = metrics["llm_judge"]
        assert judge_metric["metric_value"] == (0.75 if judge_succeeds else None)
        assert judge_metric["sample_count"] == (2 if judge_succeeds else 0)
        assert judge_metric["confidence_interval"] == (
            {"method": "normal_95", "lower": 0.75, "upper": 0.75}
            if judge_succeeds
            else None
        )
        if not judge_succeeds:
            assert "No successful" in judge_metric["availability_reason"]
        leaderboard = client.get("/api/v1/leaderboard", params={"available_metric": "llm_judge"})
        assert leaderboard.status_code == 200
        assert leaderboard.json()["total"] == (1 if judge_succeeds else 0)

        assessments = [
            client.get(f"/api/v1/judge-assessments/sample/{attempt['id']}").json()
            for attempt in attempts
        ]
        assert all(len(items) == 1 for items in assessments)
        assert {items[0]["status"] for items in assessments} == {expected_status}
        if judge_succeeds:
            assert all(items[0]["rubric"] == {"source": "llm_judge_metric", "reference_field": "answer"} for items in assessments)
            assert {items[0]["score"] for items in assessments} == {0.75}
            assert [item["messages"][0]["content"] for item in executor.judge_inputs] == [system_message, system_message]
            judge_payloads = [json.loads(item["messages"][1]["content"]) for item in executor.judge_inputs]
            assert {payload["reference"]["answer"] for payload in judge_payloads} == {"4", "6"}


def test_dataset_run_judges_with_the_frozen_endpoint_configuration_and_records_judge_usage(tmp_path: Path) -> None:
    executor = _FrozenJudgeExecutor()
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
            data_root=str(tmp_path / "data"),
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        ),
        connection_tester=_SuccessfulTester(),
        model_executor=executor,
    )
    with TestClient(app) as client:
        dataset = _register_ready_dataset(client)
        assert client.put(
            f"/api/v1/datasets/{dataset['id']}",
            json={
                "dataset_id": "demo",
                "version": "1",
                "input_field": "question",
                "reference_field": "answer",
                "capabilities": ["classification"],
                "languages": ["en"],
                "evaluation_type": "classification",
            },
        ).status_code == 200
        target_id = _create_available_endpoint(client)
        judge = client.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://judge.example.test/v1",
                "api_key": "judge-secret",
                "model_name": "judge-model",
                "input_cost_per_million": 2,
                "output_cost_per_million": 3,
            },
        )
        assert judge.status_code == 201
        judge_id = judge.json()["id"]
        assert client.post(f"/api/v1/model-endpoints/{judge_id}/connection-test").status_code == 200
        system_message = "Score the candidate strictly against the dataset answer."
        run = client.post(
            "/api/v1/evaluation-runs/dataset",
            json={
                "model_endpoint_id": target_id,
                "dataset_version_id": dataset["id"],
                "prompt_package_id": _prompt_package(client),
                "reference_field": "answer",
                "sample_limit": 2,
                "scoring_rule": {
                    "type": "llm_judge",
                    "judge_endpoint_id": judge_id,
                    "system_message": system_message,
                },
            },
        )
        assert run.status_code == 201
        edited = client.patch(
            f"/api/v1/model-endpoints/{judge_id}",
            json={
                "base_url": "https://judge-edited.example.test/v1",
                "model_name": "judge-edited-model",
                "timeout_seconds": 30,
                "input_cost_per_million": 99,
                "output_cost_per_million": 99,
            },
        )
        assert edited.status_code == 200
        assert client.post(f"/api/v1/model-endpoints/{judge_id}/connection-test").status_code == 200
        executed = client.post(f"/api/v1/evaluation-runs/{run.json()['id']}/execute")
        assert executed.status_code == 200
        assert executed.json()["status"] == "completed"
        assert executor.judge_calls == [("https://judge.example.test/v1", "judge-model", 60, "judge-secret")] * 2
        attempts = client.get(f"/api/v1/evaluation-runs/{run.json()['id']}/attempts").json()
        assessments = [
            client.get(f"/api/v1/judge-assessments/sample/{attempt['id']}").json()[0]
            for attempt in attempts
        ]
        assert len(assessments) == 2
        assert {item["status"] for item in assessments} == {"succeeded"}
        assert {item["input_tokens"] for item in assessments} == {12}
        assert {item["output_tokens"] for item in assessments} == {8}
        assert {item["estimated_cost"] for item in assessments} == {round((12 * 2 + 8 * 3) / 1_000_000, 12)}


def test_effective_dataset_scoring_rule_rejects_overlong_judge_system_messages() -> None:
    from app.services import dataset_runs

    with pytest.raises(dataset_runs.DatasetRunError, match="Scoring rule is invalid:"):
        dataset_runs.effective_dataset_scoring_rule(
            {"type": "llm_judge", "judge_endpoint_id": "endpoint-x", "system_message": "a" * 12_000},
            None,
        )


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


def test_dataset_run_with_prompt_package_ignores_input_field(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
            data_root=str(tmp_path / "data"),
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        ),
        connection_tester=_SuccessfulTester(),
        model_executor=_DatasetAnswerExecutor(),
    )
    with TestClient(app) as client:
        dataset = _register_ready_dataset(client)
        endpoint_id = _create_available_endpoint(client)
        package_id = _prompt_package(client)

        created = client.post("/api/v1/evaluation-runs/dataset", json={
            "model_endpoint_id": endpoint_id,
            "dataset_version_id": dataset["id"],
            "prompt_package_id": package_id,
            "input_field": "missing-field",
            "reference_field": "answer",
            "sample_limit": 10,
        })
        assert created.status_code == 201
        snapshot = created.json()["configuration_snapshot"]
        assert snapshot["input_field"] is None
        assert snapshot["prompt_package"]["id"] == package_id
        attempts = client.get(f"/api/v1/evaluation-runs/{created.json()['id']}/attempts").json()
        contents = {attempt["input_snapshot"]["messages"][-1]["content"] for attempt in attempts}
        assert contents == {"Q: what is 2+2?\nA:", "Q: what is 3+3?\nA:"}

        preflight = client.post("/api/v1/evaluation-runs/dataset/preflight", json={
            "model_endpoint_id": endpoint_id,
            "dataset_version_id": dataset["id"],
            "prompt_package_id": package_id,
            "input_field": "missing-field",
            "reference_field": "answer",
            "sample_limit": 10,
        })
        assert preflight.status_code == 200
        assert preflight.json()["can_queue"] is True
        assert not any("input field" in issue for issue in preflight.json()["issues"])


def test_dataset_run_rejects_identical_input_and_reference_fields(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
            data_root=str(tmp_path / "data"),
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        ),
        connection_tester=_SuccessfulTester(),
    )
    with TestClient(app) as client:
        dataset = _register_ready_dataset(client)
        endpoint_id = _create_available_endpoint(client)

        preflight = client.post("/api/v1/evaluation-runs/dataset/preflight", json={
            "model_endpoint_id": endpoint_id,
            "dataset_version_id": dataset["id"],
            "input_field": "question",
            "reference_field": "question",
            "sample_limit": 10,
        })
        assert preflight.status_code == 200
        assert preflight.json()["can_queue"] is False
        assert any("different" in issue for issue in preflight.json()["issues"])

        created = client.post("/api/v1/evaluation-runs/dataset", json={
            "model_endpoint_id": endpoint_id,
            "dataset_version_id": dataset["id"],
            "input_field": "question",
            "reference_field": "question",
            "sample_limit": 10,
        })
        assert created.status_code == 409
        assert "different" in created.json()["detail"]


def test_dataset_run_inherits_dataset_defaults_without_overwriting_record_metadata(
    tmp_path: Path,
) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
            data_root=str(tmp_path / "data"),
            secret_encryption_key=Fernet.generate_key().decode("utf-8"),
        ),
        connection_tester=_SuccessfulTester(),
    )
    content = (
        b'{"question":"first","answer":"1","metadata":{"capabilities":["record_reasoning"],"languages":["fr"],"evaluation_type":"generation"}}\n'
        b'{"question":"second","answer":"2"}\n'
        b'{"question":"third","answer":"3","metadata":{"capabilities":[]}}\n'
    )
    with TestClient(app) as client:
        created_dataset = client.post(
            "/api/v1/datasets",
            json={
                "dataset_id": "profiled",
                "version": "1",
                "input_field": "question",
                "reference_field": "answer",
                "capabilities": ["classification"],
                "languages": ["en-US"],
                "evaluation_type": "classification",
            },
        )
        uploaded = client.post(
            f"/api/v1/datasets/{created_dataset.json()['id']}/upload",
            json={
                "filename": "profiled.jsonl",
                "base64_data": base64.b64encode(content).decode("ascii"),
            },
        )
        assert uploaded.status_code == 200
        endpoint_id = _create_available_endpoint(client)

        created = client.post(
            "/api/v1/evaluation-runs/dataset",
            json={
                "model_endpoint_id": endpoint_id,
                "dataset_version_id": uploaded.json()["id"],
                "sample_limit": 10,
            },
        )
        assert created.status_code == 201
        snapshot = created.json()["configuration_snapshot"]
        assert snapshot["input_field"] == "question"
        assert snapshot["reference_field"] == "answer"
        assert snapshot["dataset_profile"] == {
            "capabilities": ["classification"],
            "languages": ["en-US"],
            "evaluation_type": "classification",
            "input_field": "question",
            "reference_field": "answer",
        }

        attempts = client.get(
            f"/api/v1/evaluation-runs/{created.json()['id']}/attempts"
        ).json()
        by_prompt = {
            attempt["input_snapshot"]["messages"][-1]["content"]: attempt
            for attempt in attempts
        }
        explicit = by_prompt["first"]
        inherited = by_prompt["second"]
        explicit_empty = by_prompt["third"]
        assert explicit["input_snapshot"]["metadata"]["dataset"] == "profiled"
        assert explicit["input_snapshot"]["metadata"]["record_number"] == "1"
        assert explicit["input_snapshot"]["metadata"]["capabilities"] == ["record_reasoning"]
        assert explicit["input_snapshot"]["metadata"]["languages"] == ["fr"]
        assert explicit["input_snapshot"]["metadata"]["evaluation_type"] == "generation"
        assert inherited["input_snapshot"]["metadata"]["capabilities"] == ["classification"]
        assert inherited["input_snapshot"]["metadata"]["languages"] == ["en-US"]
        assert inherited["input_snapshot"]["metadata"]["evaluation_type"] == "classification"
        assert explicit_empty["input_snapshot"]["metadata"]["capabilities"] == []
        assert explicit_empty["input_snapshot"]["metadata"]["languages"] == ["en-US"]
        assert explicit_empty["input_snapshot"]["metadata"]["evaluation_type"] == "classification"
        assert explicit["reference_snapshot"]["dataset_profile"]["evaluation_type"] == "generation"
        assert inherited["reference_snapshot"]["dataset_profile"]["evaluation_type"] == "classification"
        assert explicit_empty["reference_snapshot"]["dataset_profile"]["capabilities"] == []
        assert all(
            attempt["reference_snapshot"]["scoring"] == {"type": "exact_match"}
            for attempt in attempts
        )
