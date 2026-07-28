from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db.models import ModelEndpoint
from app.main import create_app
from app.services.model_executor import SampleExecutionResult


class JsonJudgeExecutor:
    snapshots: list[dict[str, object]]

    def __init__(self) -> None:
        self.snapshots = []

    def execute(self, endpoint, api_key: str, input_snapshot: dict[str, object]) -> SampleExecutionResult:
        assert endpoint.model_name == "judge-model"
        assert api_key == "judge-key"
        assert input_snapshot["messages"][0]["role"] == "system"
        self.snapshots.append(input_snapshot)
        user_content = input_snapshot["messages"][1]["content"]
        if '"answers"' in user_content:
            return SampleExecutionResult(
                True,
                {"model": endpoint.model_name},
                '{"choices":[{"message":{"content":"{\\"score\\": 0.75, \\"label\\": \\"pairwise\\", \\"rationale\\": \\"A is stronger\\", \\"winner\\": \\"A\\"}"}}]}',
                '{"score": 0.75, "label": "pairwise", "rationale": "A is stronger", "winner": "A"}',
            )
        return SampleExecutionResult(
            True,
            {"model": endpoint.model_name},
            '{"choices":[{"message":{"content":"{\\"score\\": 0.75, \\"label\\": \\"mostly-correct\\", \\"rationale\\": \\"minor omission\\"}"}}]}',
            '{"score": 0.75, "label": "mostly-correct", "rationale": "minor omission"}',
        )


def test_llm_judge_saves_independent_assessment_evidence(tmp_path: Path) -> None:
    app = create_app(
        Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode()),
        model_executor=JsonJudgeExecutor(),
    )
    with TestClient(app) as client:
        target = client.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"target-key","model_name":"target-model"}).json()
        judge = client.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"judge-key","model_name":"judge-model"}).json()
        with app.state.database.get_session() as session:
            for endpoint_id in (target["id"], judge["id"]):
                endpoint = session.get(ModelEndpoint, endpoint_id)
                assert endpoint is not None
                endpoint.status = "available"
            session.commit()
        run = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id":target["id"],"sample_limit":1}).json()
        attempt = client.get(f"/api/v1/evaluation-runs/{run['id']}/attempts").json()[0]
        assessment = client.post("/api/v1/judge-assessments", json={"sample_attempt_id":attempt["id"],"judge_endpoint_id":judge["id"],"rubric":{"criterion":"answer quality"}})
        assert assessment.status_code == 201
        assert assessment.json()["score"] == 0.75
        assert assessment.json()["label"] == "mostly-correct"
        assert assessment.json()["status"] == "succeeded"
        listed = client.get(f"/api/v1/judge-assessments/sample/{attempt['id']}")
        assert [item["id"] for item in listed.json()] == [assessment.json()["id"]]


def test_target_model_cannot_judge_its_own_attempt(tmp_path: Path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode()))
    with TestClient(app) as client:
        target = client.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"target-key","model_name":"target-model"}).json()
        with app.state.database.get_session() as session:
            endpoint = session.get(ModelEndpoint, target["id"])
            assert endpoint is not None
            endpoint.status = "available"
            session.commit()
        run = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id":target["id"],"sample_limit":1}).json()
        attempt = client.get(f"/api/v1/evaluation-runs/{run['id']}/attempts").json()[0]
        response = client.post("/api/v1/judge-assessments", json={"sample_attempt_id":attempt["id"],"judge_endpoint_id":target["id"]})
        assert response.status_code == 409
        assert "cannot judge its own" in response.json()["detail"]


def test_pairwise_judge_blinds_answers_runs_swap_test_and_detects_order_bias(tmp_path: Path) -> None:
    executor = JsonJudgeExecutor()
    app = create_app(
        Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode()),
        model_executor=executor,
    )
    with TestClient(app) as client:
        target_a = client.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"target-a-key","model_name":"target-a"}).json()
        target_b = client.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"target-b-key","model_name":"target-b"}).json()
        judge = client.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"judge-key","model_name":"judge-model"}).json()
        with app.state.database.get_session() as session:
            for endpoint_id in (target_a["id"], target_b["id"], judge["id"]):
                endpoint = session.get(ModelEndpoint, endpoint_id)
                assert endpoint is not None
                endpoint.status = "available"
            session.commit()
        run_a = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": target_a["id"], "sample_limit": 1}).json()
        run_b = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": target_b["id"], "sample_limit": 1}).json()
        attempt_a = client.get(f"/api/v1/evaluation-runs/{run_a['id']}/attempts").json()[0]
        attempt_b = client.get(f"/api/v1/evaluation-runs/{run_b['id']}/attempts").json()[0]
        response = client.post("/api/v1/judge-assessments/compare", json={"sample_attempt_id": attempt_a["id"], "comparison_sample_attempt_id": attempt_b["id"], "judge_endpoint_id": judge["id"], "rubric": {"criterion": "quality"}, "swap_test": True})
        assert response.status_code == 201
        assessments = response.json()
        assert len(assessments) == 2
        assert {tuple(item["answer_order"]) for item in assessments} == {("target", "comparison"), ("comparison", "target")}
        assert len({item["swap_test_group_id"] for item in assessments}) == 1
        assert all(item["selected_answer"] == "A" for item in assessments)
        assert all("target-a" not in str(snapshot) and "target-b" not in str(snapshot) for snapshot in executor.snapshots)
        agreement = client.get(f"/api/v1/judge-assessments/sample/{attempt_a['id']}/agreement")
        assert agreement.status_code == 200
        assert agreement.json()["status"] == "disagreement"
        assert agreement.json()["decisions"]["distinct"] == ["comparison", "target"]
