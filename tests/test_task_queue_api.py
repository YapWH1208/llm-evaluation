from pathlib import Path
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db import TaskUnit
from app.main import create_app
from app.infrastructure.providers.contracts import ConnectionTestResult


class SuccessfulTester:
    def test(self, _endpoint, _api_key: str) -> ConnectionTestResult:
        return ConnectionTestResult(True, "Connection succeeded.", 200)


def test_task_queue_lists_and_reprioritizes_pending_tasks(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode("utf-8")),
        connection_tester=SuccessfulTester(),
    )
    with TestClient(app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={"base_url": "https://models.example.test/v1", "api_key": "test-secret-key", "model_name": "example-model"},
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}).json()
        tasks = client.get("/api/v1/tasks", params={"run_id": run["id"]}).json()
        assert [task["task_type"] for task in tasks] == ["dataset_preparation", "benchmark", "evaluation_shard"]
        assert len(client.get("/api/v1/tasks", params={"run_id": run["id"], "limit": 1}).json()) == 1
        evaluation_task = next(task for task in tasks if task["task_type"] == "evaluation_shard")
        assert evaluation_task["priority"] == 0
        updated = client.patch(f"/api/v1/tasks/{evaluation_task['id']}", json={"priority": 25})
        assert updated.status_code == 200
        assert updated.json()["priority"] == 25


def test_worker_events_expose_queue_worker_and_error_snapshots(tmp_path: Path) -> None:
    app = create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode("utf-8")))
    with TestClient(app) as client:
        stream = client.get("/api/v1/workers/events?once=true")
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert "event: worker" in stream.text
        assert '"queue"' in stream.text


def test_reclaimed_task_fences_stale_heartbeat_and_issues_a_new_lease_version(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode("utf-8")),
        connection_tester=SuccessfulTester(),
    )
    with TestClient(app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={"base_url": "https://models.example.test/v1", "api_key": "test-secret-key", "model_name": "example-model"},
        ).json()
        assert client.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = client.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}).json()
        first = client.post("/api/v1/workers/claim", json={"worker_id": "worker-a"}).json()
        assert first is not None
        with app.state.database.get_session() as session:
            task = session.get(TaskUnit, first["id"])
            assert task is not None
            task.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            session.commit()

        assert client.post("/api/v1/workers/reclaim-expired").json() == {"reclaimed": 1}
        second = client.post("/api/v1/workers/claim", json={"worker_id": "worker-b"}).json()
        assert second is not None
        assert second["id"] == first["id"]
        assert second["lease_token"] != first["lease_token"]
        assert second["lease_version"] > first["lease_version"]
        stale = client.post(
            f"/api/v1/workers/tasks/{first['id']}/heartbeat",
            json={"lease_token": first["lease_token"], "lease_seconds": 60},
        )
        assert stale.status_code == 409
        valid = client.post(
            f"/api/v1/workers/tasks/{second['id']}/heartbeat",
            json={"lease_token": second["lease_token"], "lease_seconds": 60},
        )
        assert valid.status_code == 200
        assert valid.json()["lease_version"] == second["lease_version"]
