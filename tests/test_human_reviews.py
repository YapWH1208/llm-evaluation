from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.models import ModelEndpoint
from app.main import create_app


def _sample_attempt(client: TestClient, app) -> dict[str, object]:
    endpoint = client.post(
        "/api/v1/model-endpoints",
        json={"base_url": "https://models.example.test/v1", "api_key": "target-key", "model_name": "target"},
    ).json()
    with app.state.database.get_session() as session:
        stored = session.get(ModelEndpoint, endpoint["id"])
        assert stored is not None
        stored.status = "available"
        session.commit()
    run = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}).json()
    return client.get(f"/api/v1/evaluation-runs/{run['id']}/attempts").json()[0]


def test_human_review_agreement_requires_two_independent_reviewers_then_records_adjudication(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(database_url=f"sqlite:///{tmp_path / 'reviews.db'}", secret_encryption_key=Fernet.generate_key().decode())
    )
    with TestClient(app) as client:
        attempt = _sample_attempt(client, app)
        first = client.post(
            "/api/v1/reviews",
            json={"sample_attempt_id": attempt["id"], "reviewer_id": "reviewer-a", "rubric": {"quality": "high"}, "score": 0.9, "labels": ["correct"], "review_stage": "primary"},
        )
        assert first.status_code == 201
        awaiting = client.get(f"/api/v1/reviews/sample/{attempt['id']}/agreement")
        assert awaiting.json()["status"] == "awaiting_second_review"
        second = client.post(
            "/api/v1/reviews",
            json={"sample_attempt_id": attempt["id"], "reviewer_id": "reviewer-b", "score": 0.2, "labels": ["incorrect"], "review_stage": "secondary"},
        )
        assert second.status_code == 201
        disagreement = client.get(f"/api/v1/reviews/sample/{attempt['id']}/agreement")
        assert disagreement.json()["status"] == "needs_adjudication"
        assert disagreement.json()["numeric_score"]["range"] == 0.7
        adjudicated = client.post(
            "/api/v1/reviews",
            json={"sample_attempt_id": attempt["id"], "reviewer_id": "reviewer-c", "score": 0.6, "labels": ["partially-correct"], "review_stage": "adjudication", "adjudicates_review_ids": [first.json()["id"], second.json()["id"]]},
        )
        assert adjudicated.status_code == 201
        agreement = client.get(f"/api/v1/reviews/sample/{attempt['id']}/agreement").json()
        assert agreement["status"] == "adjudicated"
        assert agreement["adjudication_review_id"] == adjudicated.json()["id"]


def test_reviewer_cannot_submit_the_same_review_stage_twice(tmp_path: Path) -> None:
    app = create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path / 'reviews.db'}", secret_encryption_key=Fernet.generate_key().decode()))
    with TestClient(app) as client:
        attempt = _sample_attempt(client, app)
        payload = {"sample_attempt_id": attempt["id"], "reviewer_id": "reviewer-a", "review_stage": "primary"}
        assert client.post("/api/v1/reviews", json=payload).status_code == 201
        duplicate = client.post("/api/v1/reviews", json=payload)
        assert duplicate.status_code == 409
