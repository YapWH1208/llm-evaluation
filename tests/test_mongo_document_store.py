from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.mongo import MongoDocumentStore, MongoValidation
from app.db.migrations import LATEST_SCHEMA_VERSION, MIGRATIONS
from app.main import create_app
from app.db.models import CapabilityDetection
from app.services.capability_detector import CapabilityDetectionResult
from app.services.connection_tester import ConnectionTestResult
from app.services.model_executor import SampleExecutionResult


class FakeAdmin:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def command(self, value: str) -> dict[str, int]:
        self.commands.append(value)
        return {"ok": 1}


class FakeCollection:
    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []
        self.indexes: list[tuple[Any, dict[str, Any]]] = []

    def create_index(self, keys: Any, **options: Any) -> None:
        self.indexes.append((keys, options))

    def insert_one(self, document: dict[str, Any]) -> None:
        self.documents.append(dict(document))

    def find_one(self, query: dict[str, Any] | None = None, *, sort: list[tuple[str, int]] | None = None) -> dict[str, Any] | None:
        matches = [document for document in self.documents if _matches(document, query or {})]
        if sort:
            for key, direction in reversed(sort):
                matches.sort(key=lambda document: document.get(key), reverse=direction < 0)
        return dict(matches[0]) if matches else None

    def find(self, query: dict[str, Any], _projection: dict[str, int] | None = None) -> "FakeCursor":
        return FakeCursor([dict(document) for document in self.documents if _matches(document, query)])

    def find_one_and_update(self, query: dict[str, Any], update: dict[str, Any], *, sort: list[tuple[str, int]] | None = None, return_document: Any) -> dict[str, Any] | None:
        matches = [document for document in self.documents if _matches(document, query)]
        if sort:
            for key, direction in reversed(sort):
                matches.sort(key=lambda document: document.get(key), reverse=direction < 0)
        if not matches:
            return None
        matches[0].update(update["$set"])
        return dict(matches[0])

    def update_many(self, query: dict[str, Any], update: dict[str, Any]) -> None:
        for document in self.documents:
            if _matches(document, query):
                document.update(update["$set"])

    def delete_one(self, query: dict[str, Any]):
        for index, document in enumerate(self.documents):
            if _matches(document, query):
                self.documents.pop(index)
                return type("DeleteResult", (), {"deleted_count": 1})()
        return type("DeleteResult", (), {"deleted_count": 0})()


class FakeCursor(list[dict[str, Any]]):
    def sort(self, specification: list[tuple[str, int]]) -> "FakeCursor":
        for key, direction in reversed(specification):
            super().sort(key=lambda document: document.get(key), reverse=direction < 0)
        return self


class FakeDatabase:
    def __init__(self) -> None:
        self.collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections.setdefault(name, FakeCollection())

    def create_collection(self, name: str) -> FakeCollection:
        if name in self.collections:
            raise RuntimeError("collection already exists")
        collection = FakeCollection()
        self.collections[name] = collection
        return collection

    def list_collection_names(self) -> list[str]:
        return list(self.collections)


class FakeClient:
    def __init__(self) -> None:
        self.admin = FakeAdmin()
        self.databases: dict[str, FakeDatabase] = {}
        self.closed = False

    def __getitem__(self, name: str) -> FakeDatabase:
        return self.databases.setdefault(name, FakeDatabase())

    def close(self) -> None:
        self.closed = True


def _matches(document: dict[str, Any], query: dict[str, Any]) -> bool:
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(document, child) for child in expected):
                return False
            continue
        actual = document.get(key)
        if isinstance(expected, dict):
            if "$exists" in expected and (key in document) != expected["$exists"]:
                return False
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$lt" in expected and not (actual < expected["$lt"]):
                return False
            if "$lte" in expected and not (actual <= expected["$lte"]):
                return False
            if "$gte" in expected and not (actual >= expected["$gte"]):
                return False
            continue
        if actual != expected:
            return False
    return True


def test_mongo_store_initializes_all_collections_indexes_and_versions() -> None:
    client = FakeClient()
    store = MongoDocumentStore(Settings(database_url="mongodb://mongo.test/platform"), client=client)

    assert store.settings.mongodb_database_name == "platform"
    assert store.migration_preview() == MIGRATIONS
    validation = store.initialize()

    assert validation.is_valid
    assert validation.current_version == LATEST_SCHEMA_VERSION
    assert client.admin.commands == ["ping"]
    assert len(client["platform"]["schema_migrations"].documents) == len(MIGRATIONS)
    assert len(client["platform"]["task_units"].indexes) == 1
    assert len(client["platform"]["users"].indexes) == 2


def test_mongo_store_claims_by_priority_and_reclaims_expired_leases() -> None:
    client = FakeClient()
    store = MongoDocumentStore(Settings(database_url="mongodb://mongo.test/platform", mongodb_database="override"), client=client)
    store.initialize()
    now = datetime.now(timezone.utc)
    tasks = client["override"]["task_units"]
    tasks.insert_one({"_id": "low", "status": "pending", "priority": 1, "created_at": now})
    tasks.insert_one({"_id": "high", "status": "pending", "priority": 9, "created_at": now})

    claimed = store.claim_task(worker_id="worker-a", lease_seconds=30)

    assert claimed is not None
    assert claimed["id"] == "high"
    assert claimed["status"] == "leased"
    tasks.documents[1]["status"] = "running"
    tasks.documents[1]["lease_expires_at"] = now - timedelta(seconds=1)
    client["override"]["sample_attempts"].insert_one({"_id": "attempt", "task_id": "high", "status": "running"})

    assert store.reclaim_expired_leases() == 1
    assert tasks.documents[1]["status"] == "pending"
    assert client["override"]["sample_attempts"].documents[0]["status"] == "pending"


def test_mongo_store_claim_honors_run_and_shared_credential_limits() -> None:
    client = FakeClient()
    store = MongoDocumentStore(Settings(database_url="mongodb://mongo.test/platform"), client=client)
    store.initialize()
    now = datetime.now(timezone.utc)
    first_endpoint = store.insert_document("model_endpoints", {"max_concurrency": 3, "api_key_fingerprint": "shared", "api_key_max_concurrency": 1})
    second_endpoint = store.insert_document("model_endpoints", {"max_concurrency": 3, "api_key_fingerprint": "shared", "api_key_max_concurrency": 1})
    first_run = store.insert_document("evaluation_runs", {"model_endpoint_id": first_endpoint["id"], "benchmark_id": "benchmark", "benchmark_version": "1", "max_concurrency": 1})
    second_run = store.insert_document("evaluation_runs", {"model_endpoint_id": second_endpoint["id"], "benchmark_id": "benchmark", "benchmark_version": "1"})
    for run in (first_run, first_run, second_run):
        store.insert_document("task_units", {"run_id": run["id"], "status": "pending", "priority": 1, "payload": {"sample_ids": ["sample"], "estimated_request_count": 1}, "created_at": now})

    assert store.claim_task(worker_id="worker-a", run_id=first_run["id"]) is not None
    assert store.claim_task(worker_id="worker-b", run_id=first_run["id"]) is None
    assert store.claim_task(worker_id="worker-c", run_id=second_run["id"]) is None


def test_database_cli_routes_mongodb_operations_to_document_store(monkeypatch, capsys) -> None:
    import app.cli as cli

    created: list[FakeMongoStore] = []

    class FakeMongoStore:
        def __init__(self, settings: Settings) -> None:
            assert settings.database_kind == "mongodb"
            created.append(self)
            self.closed = False

        def migration_preview(self):
            return ()

        def initialize(self, _mode: str):
            return MongoValidation("mongodb", LATEST_SCHEMA_VERSION, LATEST_SCHEMA_VERSION, ())

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(cli.Settings, "from_environment", lambda: Settings(database_url="mongodb://mongo.test/platform"))
    monkeypatch.setattr(cli, "MongoDocumentStore", FakeMongoStore)

    assert cli.main(["database", "initialize"]) == 0
    assert '"database": "mongodb"' in capsys.readouterr().out
    assert created[0].closed is True


class SuccessfulTester:
    def test(self, _endpoint: Any, _api_key: str) -> ConnectionTestResult:
        return ConnectionTestResult(True, "Connection succeeded.", 200)


def test_mongodb_app_model_endpoint_crud_uses_document_store() -> None:
    client = FakeClient()
    settings = Settings(
        database_url="mongodb://mongo.test/platform",
        secret_encryption_key=Fernet.generate_key().decode(),
    )
    store = MongoDocumentStore(settings, client=client)
    app = create_app(settings, connection_tester=SuccessfulTester(), document_store=store)

    with TestClient(app) as api:
        created = api.post(
            "/api/v1/model-endpoints",
            json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "model"},
        )
        assert created.status_code == 201
        endpoint = created.json()
        assert endpoint["status"] == "unverified"
        assert "secret" not in str(endpoint)

        tested = api.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test")
        assert tested.status_code == 200
        assert tested.json()["status"] == "available"

        updated = api.patch(f"/api/v1/model-endpoints/{endpoint['id']}", json={"max_concurrency": 3})
        assert updated.status_code == 200
        assert updated.json()["max_concurrency"] == 3
        assert api.get("/api/v1/model-endpoints").json()[0]["id"] == endpoint["id"]
        assert api.delete(f"/api/v1/model-endpoints/{endpoint['id']}").status_code == 204
        assert api.get(f"/api/v1/model-endpoints/{endpoint['id']}").status_code == 404


def test_mongodb_app_preserves_capability_declarations_and_detection_evidence() -> None:
    class Detector:
        def detect(self, endpoint: Any, api_key: str, capability_keys: list[str]):
            assert endpoint.model_name == "model"
            assert api_key == "secret"
            assert capability_keys == ["text_input"]
            return [
                CapabilityDetectionResult(
                    "text_input",
                    CapabilityDetection.PASSED,
                    {"adapter_version": "test/1", "outcome": "passed"},
                )
            ]

    client = FakeClient()
    settings = Settings(
        database_url="mongodb://mongo.test/platform",
        secret_encryption_key=Fernet.generate_key().decode(),
    )
    app = create_app(
        settings,
        capability_detector=Detector(),
        document_store=MongoDocumentStore(settings, client=client),
    )
    with TestClient(app) as api:
        endpoint = api.post(
            "/api/v1/model-endpoints",
            json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "model"},
        ).json()
        declared = api.put(
            f"/api/v1/model-endpoints/{endpoint['id']}/capabilities",
            json={"capability_key": "text_input", "user_declared_status": "supported"},
        )
        assert declared.json()["effective_status"] == "user_verified"
        detected = api.post(
            f"/api/v1/model-endpoints/{endpoint['id']}/capabilities/detect",
            json={"capability_keys": ["text_input"]},
        )
        assert detected.status_code == 200
        assert detected.json()[0]["effective_status"] == "verified_by_both"
        assert detected.json()[0]["detection_evidence"]["adapter_version"] == "test/1"


def test_mongodb_run_queue_executes_and_persists_sample_evidence() -> None:
    class ExactExecutor:
        def execute(self, endpoint: Any, api_key: str, input_snapshot: dict[str, Any]) -> SampleExecutionResult:
            assert endpoint.model_name == "model"
            assert api_key == "secret"
            assert input_snapshot["messages"]
            return SampleExecutionResult(
                True,
                {"model": endpoint.model_name, "messages": input_snapshot["messages"]},
                '{"choices":[{"message":{"content":"4"}}]}',
                "4",
                latency_ms=12.5,
                input_tokens=5,
                output_tokens=1,
            )

    client = FakeClient()
    settings = Settings(
        database_url="mongodb://mongo.test/platform",
        secret_encryption_key=Fernet.generate_key().decode(),
    )
    app = create_app(
        settings,
        connection_tester=SuccessfulTester(),
        model_executor=ExactExecutor(),
        document_store=MongoDocumentStore(settings, client=client),
    )
    with TestClient(app) as api:
        endpoint = api.post(
            "/api/v1/model-endpoints",
            json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "model"},
        ).json()
        assert api.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = api.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1})
        assert run.status_code == 201
        completed = api.post(f"/api/v1/evaluation-runs/{run.json()['id']}/execute")
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
        attempts = api.get(f"/api/v1/evaluation-runs/{run.json()['id']}/attempts")
        assert [(item["status"], item["score"]) for item in attempts.json()] == [("succeeded", 1.0)]
        assert attempts.json()[0]["request_snapshot"]["model"] == "model"


def test_mongodb_worker_claim_heartbeat_and_execute_are_lease_safe(tmp_path: Path) -> None:
    class ExactExecutor:
        def execute(self, endpoint: Any, _api_key: str, _input_snapshot: dict[str, Any]) -> SampleExecutionResult:
            return SampleExecutionResult(True, {"model": endpoint.model_name}, "{}", "4")

    client = FakeClient()
    settings = Settings(database_url="mongodb://mongo.test/platform", data_root=str(tmp_path / "data"), secret_encryption_key=Fernet.generate_key().decode())
    app = create_app(
        settings,
        connection_tester=SuccessfulTester(),
        model_executor=ExactExecutor(),
        document_store=MongoDocumentStore(settings, client=client),
    )
    with TestClient(app) as api:
        endpoint = api.post("/api/v1/model-endpoints", json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "model"}).json()
        assert api.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = api.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}).json()
        task = api.post("/api/v1/workers/claim", json={"worker_id": "worker-a"}).json()
        heartbeat = api.post(f"/api/v1/workers/tasks/{task['id']}/heartbeat", json={"lease_token": task["lease_token"]})
        assert heartbeat.status_code == 200
        execution = api.post(f"/api/v1/workers/tasks/{task['id']}/execute", json={"lease_token": task["lease_token"]})
        assert execution.status_code == 200
        assert execution.json()["status"] == "succeeded"
        scoring = api.post("/api/v1/workers/claim", json={"worker_id": "worker-b"}).json()
        assert scoring["task_type"] == "scoring"
        assert api.post(f"/api/v1/workers/tasks/{scoring['id']}/execute", json={"lease_token": scoring["lease_token"]}).json()["status"] == "succeeded"
        aggregation = api.post("/api/v1/workers/claim", json={"worker_id": "worker-c"}).json()
        assert aggregation["task_type"] == "aggregation"
        assert api.post(f"/api/v1/workers/tasks/{aggregation['id']}/execute", json={"lease_token": aggregation["lease_token"]}).json()["status"] == "succeeded"
        report = api.post("/api/v1/workers/claim", json={"worker_id": "worker-d"}).json()
        assert report["task_type"] == "report_generation"
        assert api.post(f"/api/v1/workers/tasks/{report['id']}/execute", json={"lease_token": report["lease_token"]}).json()["status"] == "succeeded"
        assert api.get(f"/api/v1/evaluation-runs/{run['id']}").json()["status"] == "completed"
        assert len(api.get(f"/api/v1/reports/run/{run['id']}").json()) == 1


def test_mongodb_workspace_catalogs_store_prompts_benchmarks_and_dataset_licenses() -> None:
    client = FakeClient()
    settings = Settings(database_url="mongodb://mongo.test/platform", secret_encryption_key=Fernet.generate_key().decode())
    app = create_app(settings, document_store=MongoDocumentStore(settings, client=client))
    with TestClient(app) as api:
        benchmarks = api.get("/api/v1/benchmarks")
        assert benchmarks.status_code == 200
        assert any(item["benchmark_id"] == "text-quick-check" for item in benchmarks.json())
        prompt = api.post("/api/v1/prompt-packages", json={"name": "qa", "version": "1", "user_template": "{{ question }}"})
        assert prompt.status_code == 201
        assert api.get("/api/v1/prompt-packages").json()[0]["id"] == prompt.json()["id"]
        dataset = api.post("/api/v1/datasets", json={"dataset_id": "demo", "version": "1", "license_text": "accept me"})
        assert dataset.status_code == 201
        assert dataset.json()["status"] == "license_required"
        accepted = api.post(f"/api/v1/datasets/{dataset.json()['id']}/accept-license")
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "not_downloaded"


def test_mongodb_assets_support_custom_multimodal_runs(tmp_path) -> None:
    class ExactExecutor:
        def execute(self, endpoint: Any, _api_key: str, input_snapshot: dict[str, Any]) -> SampleExecutionResult:
            assert input_snapshot["messages"][0]["content"][1]["type"] == "image"
            return SampleExecutionResult(True, {"model": endpoint.model_name}, "{}", "ok")

    client = FakeClient()
    settings = Settings(database_url="mongodb://mongo.test/platform", data_root=str(tmp_path), secret_encryption_key=Fernet.generate_key().decode())
    app = create_app(settings, connection_tester=SuccessfulTester(), model_executor=ExactExecutor(), document_store=MongoDocumentStore(settings, client=client))
    with TestClient(app) as api:
        endpoint = api.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"secret","model_name":"model"}).json()
        assert api.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        asset = api.post("/api/v1/assets", json={"filename":"dot.png","mime_type":"image/png","base64_data":"iVBORw0KGgo="})
        assert asset.status_code == 201
        run = api.post("/api/v1/evaluation-runs/custom-multimodal", json={"model_endpoint_id":endpoint["id"],"sample_id":"image-1","reference_answer":"ok","messages":[{"role":"user","content":[{"type":"text","text":"Describe"},{"type":"image","source":{"asset_id":asset.json()["id"]},"mime_type":"image/png"}]}]})
        assert run.status_code == 201
        assert api.post(f"/api/v1/evaluation-runs/{run.json()['id']}/execute").json()["status"] == "completed"


def test_mongodb_admin_judge_and_comparison_routes_use_document_store(tmp_path) -> None:
    class JudgeExecutor:
        def execute(self, endpoint: Any, _api_key: str, _input_snapshot: dict[str, Any]) -> SampleExecutionResult:
            if endpoint.model_name == "judge":
                return SampleExecutionResult(
                    True,
                    {"model": endpoint.model_name},
                    '{"choices":[{"message":{"content":"{\\"score\\": 0.75, \\"label\\": \\"good\\"}"}}]}',
                    '{"score": 0.75, "label": "good"}',
                )
            return SampleExecutionResult(True, {"model": endpoint.model_name}, "{}", "4")

    client = FakeClient()
    settings = Settings(
        database_url="mongodb://mongo.test/platform",
        data_root=str(tmp_path),
        secret_encryption_key=Fernet.generate_key().decode(),
    )
    app = create_app(
        settings,
        connection_tester=SuccessfulTester(),
        model_executor=JudgeExecutor(),
        document_store=MongoDocumentStore(settings, client=client),
    )
    with TestClient(app) as api:
        user = api.post("/api/v1/users", json={"email": "reviewer@example.test", "display_name": "Reviewer"})
        assert user.status_code == 201
        assert api.get("/api/v1/users").json()[0]["email"] == "reviewer@example.test"

        endpoint_ids: list[str] = []
        for model_name in ("target", "target-b", "judge"):
            endpoint = api.post(
                "/api/v1/model-endpoints",
                json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": model_name},
            ).json()
            endpoint_ids.append(endpoint["id"])
            assert api.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200

        first = api.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint_ids[0], "sample_limit": 1}).json()
        second = api.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint_ids[1], "sample_limit": 1}).json()
        assert api.post(f"/api/v1/evaluation-runs/{first['id']}/execute").status_code == 200
        assert api.post(f"/api/v1/evaluation-runs/{second['id']}/execute").status_code == 200
        metrics = api.get(f"/api/v1/analytics/runs/{first['id']}/metrics")
        assert metrics.status_code == 200
        assert {metric["metric_name"] for metric in metrics.json()} >= {"accuracy", "success_rate", "estimated_cost"}
        comparison = api.get("/api/v1/comparisons", params={"run_a": first["id"], "run_b": second["id"]})
        assert comparison.status_code == 200
        assert comparison.json()["shared_samples"] == 1

        attempt = api.get(f"/api/v1/evaluation-runs/{first['id']}/attempts").json()[0]
        assessment = api.post(
            "/api/v1/judge-assessments",
            json={"sample_attempt_id": attempt["id"], "judge_endpoint_id": endpoint_ids[2], "rubric": {"quality": "high"}},
        )
        assert assessment.status_code == 201
        assert assessment.json()["score"] == 0.75
        assert api.get(f"/api/v1/judge-assessments/sample/{attempt['id']}").json()[0]["label"] == "good"
        primary_review = api.post(
            "/api/v1/reviews",
            json={"sample_attempt_id": attempt["id"], "reviewer_id": "reviewer-a", "score": 0.9, "labels": ["correct"], "review_stage": "primary"},
        )
        secondary_review = api.post(
            "/api/v1/reviews",
            json={"sample_attempt_id": attempt["id"], "reviewer_id": "reviewer-b", "score": 0.1, "labels": ["incorrect"], "review_stage": "secondary"},
        )
        assert primary_review.status_code == 201
        assert secondary_review.status_code == 201
        agreement = api.get(f"/api/v1/reviews/sample/{attempt['id']}/agreement")
        assert agreement.json()["status"] == "needs_adjudication"
        assert api.get("/api/v1/audit-events").status_code == 200
