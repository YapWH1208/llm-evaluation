from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db.models import ModelEndpoint
from app.main import create_app
from app.services.model_executor import SampleExecutionResult


class JsonJudgeExecutor:
    def execute(self, endpoint, api_key: str, input_snapshot: dict[str, object]) -> SampleExecutionResult:
        assert endpoint.model_name == "judge-model"
        assert api_key == "judge-key"
        assert input_snapshot["messages"][0]["role"] == "system"
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
