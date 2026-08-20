from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from app.core.config import Settings
from app.db.database import Database
from app.db.models import EvaluationRun, ModelEndpoint, SampleAttempt, TaskUnit
from app.db.mongo import MongoDocumentStore
from app.modules.evaluations.repositories import (
    MongoEvaluationRepository,
    SqliteEvaluationRepository,
)
from app.modules.evaluations.service import EvaluationService
from tests.test_mongo_document_store import FakeClient


@pytest.fixture(params=("sqlite", "mongo"))
def evaluation_adapter(request: pytest.FixtureRequest, tmp_path: Path):
    now = datetime.now(timezone.utc)
    endpoint_id = "endpoint-contract"
    run_id = "run-contract"
    task_id = "task-contract"
    attempt_id = "attempt-contract"

    if request.param == "sqlite":
        database = Database(Settings.local_development(database_url=f"sqlite:///{tmp_path / 'contract.db'}"))
        database.initialize()
        with database.get_session() as session:
            session.add(
                ModelEndpoint(
                    id=endpoint_id,
                    display_name="Contract model",
                    base_url="https://models.example.test/v1",
                    model_name="contract-model",
                    encrypted_api_key="encrypted",
                    api_key_mask="****",
                    status="available",
                )
            )
            session.flush()
            session.add(
                EvaluationRun(
                    id=run_id,
                    model_endpoint_id=endpoint_id,
                    benchmark_id="contract-benchmark",
                    benchmark_version="1.0.0",
                    configuration_snapshot={},
                    status="running",
                    total_samples=1,
                    created_at=now,
                )
            )
            session.flush()
            session.add(
                TaskUnit(
                    id=task_id,
                    run_id=run_id,
                    task_type="evaluation_shard",
                    payload={},
                    status="running",
                    lease_version=3,
                )
            )
            session.flush()
            session.add(
                SampleAttempt(
                    id=attempt_id,
                    run_id=run_id,
                    task_id=task_id,
                    sample_id="sample-1",
                    input_snapshot={},
                    reference_snapshot={},
                    status="running",
                )
            )
            session.commit()
        repository: Any = SqliteEvaluationRepository(database)
        yield repository, EvaluationService(repository, data_root=str(tmp_path)), run_id
        database.dispose()
        return

    store = MongoDocumentStore(
        Settings.local_development(database_url="mongodb://mongo.test/platform"),
        client=FakeClient(),
    )
    store.initialize()
    store.insert_document(
        "model_endpoints",
        {"id": endpoint_id, "model_name": "contract-model", "currency": "USD"},
    )
    store.insert_document(
        "evaluation_runs",
        {
            "id": run_id,
            "model_endpoint_id": endpoint_id,
            "benchmark_id": "contract-benchmark",
            "benchmark_version": "1.0.0",
            "configuration_snapshot": {},
            "status": "running",
            "total_samples": 1,
            "completed_samples": 0,
            "successful_samples": 0,
            "failed_samples": 0,
            "created_at": now,
        },
    )
    store.insert_document(
        "task_units",
        {
            "id": task_id,
            "run_id": run_id,
            "task_type": "evaluation_shard",
            "payload": {},
            "status": "running",
            "priority": 0,
            "attempt_count": 1,
            "lease_version": 3,
            "created_at": now,
            "updated_at": now,
        },
    )
    store.insert_document(
        "sample_attempts",
        {
            "id": attempt_id,
            "run_id": run_id,
            "task_id": task_id,
            "sample_id": "sample-1",
            "attempt_number": 1,
            "input_snapshot": {},
            "reference_snapshot": {},
            "status": "running",
            "created_at": now,
        },
    )
    repository = MongoEvaluationRepository(store)
    yield repository, EvaluationService(repository, data_root=str(tmp_path)), run_id
    store.close()


def test_lifecycle_contract_is_identical_for_each_adapter(evaluation_adapter) -> None:
    repository, service, run_id = evaluation_adapter

    assert [run["id"] for run in service.list()] == [run_id]
    paused = service.pause(run_id)
    assert paused["status"] == "paused"
    task = repository.list_tasks(run_id)[0]
    attempt = repository.list_attempts(run_id)[0]
    assert task["status"] == "cancelled"
    assert task["lease_version"] == 4
    assert attempt["status"] == "pending"

    assert service.resume(run_id)["status"] == "queued"
    assert repository.list_tasks(run_id)[0]["status"] == "pending"

    repository.update_run(run_id, {"status": "completed"})
    archived = service.archive(run_id)
    assert archived["archived_at"] is not None
    service.delete(run_id)
    assert repository.get_run(run_id) is None
