from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
import pytest
import httpx

from app.core.config import Settings
from app.db.mongo import MongoDocumentStore, MongoValidation, MongoValidationError
from app.db.migrations import LATEST_SCHEMA_VERSION, MIGRATIONS
from app.main import create_app
from app.db.models import CapabilityDetection
from app.infrastructure.providers.contracts import CapabilityDetectionResult, ConnectionTestResult, SampleExecutionResult
from app.modules.evaluations.names import format_run_display_name
from app.benchmarks.text_quick_check import TextSample
from app.modules.analytics.aggregation import AGGREGATION_VERSION, recompute_mongo_aggregate_metrics
from app.modules.benchmarks.metrics import METRIC_PROFILE_VERSION


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

    monkeypatch.setattr("app.infrastructure.network.outbound.getaddrinfo", lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 0))])
    monkeypatch.setattr("app.modules.datasets.preparation.pinned_outbound_transport", lambda *_args, **_kwargs: httpx.MockTransport(lambda _request: httpx.Response(200, content=content)))


class FakeAdmin:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def command(self, value: str) -> dict[str, int]:
        self.commands.append(value)
        return {"ok": 1}


class FakeCollection:
    def __init__(self, *, validator: dict[str, Any] | None = None) -> None:
        self.documents: list[dict[str, Any]] = []
        self.indexes: list[tuple[Any, dict[str, Any]]] = []
        self.validator = validator

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

    def count_documents(self, query: dict[str, Any]) -> int:
        return sum(_matches(document, query) for document in self.documents)

    def distinct(self, field: str, query: dict[str, Any]) -> list[Any]:
        return list({document.get(field) for document in self.documents if _matches(document, query) and document.get(field) is not None})

    def options(self) -> dict[str, Any]:
        return {"validator": self.validator} if self.validator is not None else {}

    def find_one_and_update(self, query: dict[str, Any], update: dict[str, Any], *, sort: list[tuple[str, int]] | None = None, return_document: Any) -> dict[str, Any] | None:
        matches = [document for document in self.documents if _matches(document, query)]
        if sort:
            for key, direction in reversed(sort):
                matches.sort(key=lambda document: document.get(key), reverse=direction < 0)
        if not matches:
            return None
        matches[0].update(update.get("$set", {}))
        for key, value in update.get("$inc", {}).items():
            matches[0][key] = int(matches[0].get(key, 0)) + int(value)
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

    def create_collection(self, name: str, **options: Any) -> FakeCollection:
        if name in self.collections:
            raise RuntimeError("collection already exists")
        collection = FakeCollection(validator=options.get("validator"))
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
            if "$gt" in expected and not (actual > expected["$gt"]):
                return False
            continue
        if actual != expected:
            return False
    return True


def test_mongo_store_initializes_all_collections_indexes_and_versions() -> None:
    client = FakeClient()
    store = MongoDocumentStore(Settings.local_development(database_url="mongodb://mongo.test/platform"), client=client)

    assert store.settings.mongodb_database_name == "platform"
    assert store.migration_preview() == MIGRATIONS
    validation = store.initialize()

    assert validation.is_valid
    assert validation.current_version == LATEST_SCHEMA_VERSION
    assert client.admin.commands == ["ping"]
    assert len(client["platform"]["schema_migrations"].documents) == len(MIGRATIONS)
    assert len(client["platform"]["task_units"].indexes) == 1
    assert "users" not in client["platform"].list_collection_names()
    assert "audit_events" not in client["platform"].list_collection_names()


def test_mongo_store_backfills_missing_legacy_migration_ledger_before_upgrading() -> None:
    client = FakeClient()
    store = MongoDocumentStore(Settings.local_development(database_url="mongodb://mongo.test/platform"), client=client)
    store.initialize()
    database = client["platform"]
    del database.collections["schema_migrations"]
    database["schema_versions"].documents = [
        document for document in database["schema_versions"].documents if document["version"] <= 21
    ]

    validation = store.initialize()
    assert validation.is_valid
    assert [item["version"] for item in database["schema_migrations"].documents] == [
        migration.version for migration in MIGRATIONS
    ]
    assert store.initialize("validate").is_valid


def test_mongo_report_share_password_limiter_is_durable_and_expires() -> None:
    client = FakeClient()
    store = MongoDocumentStore(Settings.local_development(database_url="mongodb://mongo.test/platform"), client=client)
    store.initialize()
    now = datetime.now(timezone.utc)

    for _ in range(5):
        assert store.record_report_share_password_failure(
            share_id="share-id", client_key="client-hash", now=now, window=timedelta(minutes=5), limit=5
        )
    assert store.report_share_password_attempt_limit_reached(
        share_id="share-id", client_key="client-hash", now=now, limit=5
    )
    assert not store.record_report_share_password_failure(
        share_id="share-id", client_key="client-hash", now=now, window=timedelta(minutes=5), limit=5
    )
    assert store.record_report_share_password_failure(
        share_id="share-id", client_key="client-hash", now=now + timedelta(minutes=6), window=timedelta(minutes=5), limit=5
    )


def test_mongo_validation_detects_missing_index_and_migration() -> None:
    client = FakeClient()
    store = MongoDocumentStore(Settings.local_development(database_url="mongodb://mongo.test/platform"), client=client)
    store.initialize()
    client["platform"]["task_units"].indexes.clear()
    client["platform"]["schema_migrations"].documents = [
        document for document in client["platform"]["schema_migrations"].documents if document["version"] != 22
    ]

    validation = store.validate_schema()
    assert "task_units.status_1_next_retry_at_1_priority_-1_created_at_1" in validation.missing_indexes
    assert "20260729_add_remediation_persistence_contracts" in validation.missing_migrations
    with pytest.raises(MongoValidationError):
        store.initialize("validate")


def test_mongo_validation_detects_missing_collection_validator() -> None:
    client = FakeClient()
    store = MongoDocumentStore(Settings.local_development(database_url="mongodb://mongo.test/platform"), client=client)
    store.initialize()
    client["platform"]["task_units"].validator = None

    validation = store.validate_schema()
    assert "task_units" in validation.missing_validators
    with pytest.raises(MongoValidationError, match="missing validators"):
        store.initialize("validate")


def test_mongo_store_claims_by_priority_and_reclaims_expired_leases() -> None:
    client = FakeClient()
    store = MongoDocumentStore(Settings.local_development(database_url="mongodb://mongo.test/platform", mongodb_database="override"), client=client)
    store.initialize()
    now = datetime.now(timezone.utc)
    tasks = client["override"]["task_units"]
    tasks.insert_one({"_id": "low", "status": "pending", "priority": 1, "created_at": now})
    tasks.insert_one({"_id": "high", "status": "pending", "priority": 9, "created_at": now})

    claimed = store.claim_task(worker_id="worker-a", lease_seconds=30)

    assert claimed is not None
    assert claimed["id"] == "high"
    assert claimed["status"] == "leased"
    assert claimed["lease_version"] == 1
    original_token = claimed["lease_token"]
    tasks.documents[1]["status"] = "running"
    tasks.documents[1]["lease_expires_at"] = now - timedelta(seconds=1)
    client["override"]["sample_attempts"].insert_one({"_id": "attempt", "task_id": "high", "status": "running"})

    assert store.reclaim_expired_leases() == 1
    assert tasks.documents[1]["status"] == "pending"
    assert tasks.documents[1]["lease_version"] == 2
    assert client["override"]["sample_attempts"].documents[0]["status"] == "pending"
    reclaimed = store.claim_task(worker_id="worker-b", lease_seconds=30)
    assert reclaimed is not None
    assert reclaimed["id"] == "high"
    assert reclaimed["lease_version"] == 3
    assert reclaimed["lease_token"] != original_token
    assert store.heartbeat_task(task_id="high", lease_token=str(original_token)) is None


def test_mongo_store_claim_honors_run_and_shared_credential_limits() -> None:
    client = FakeClient()
    store = MongoDocumentStore(Settings.local_development(database_url="mongodb://mongo.test/platform"), client=client)
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

    monkeypatch.setattr(cli.Settings, "from_environment", lambda: Settings.local_development(database_url="mongodb://mongo.test/platform"))
    monkeypatch.setattr(cli, "MongoDocumentStore", FakeMongoStore)

    assert cli.main(["database", "initialize"]) == 0
    assert '"database": "mongodb"' in capsys.readouterr().out
    assert created[0].closed is True


class SuccessfulTester:
    def test(self, _endpoint: Any, _api_key: str) -> ConnectionTestResult:
        return ConnectionTestResult(True, "Connection succeeded.", 200)


def test_mongodb_app_model_endpoint_crud_uses_document_store() -> None:
    client = FakeClient()
    settings = Settings.local_development(
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
    settings = Settings.local_development(
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
        assert api.put(
            f"/api/v1/model-endpoints/{endpoint['id']}/capabilities",
            json={"capability_key": "text_input", "user_declared_status": "unsupported"},
        ).json()["effective_status"] == "detected_user_unsupported"
        assert api.get(f"/api/v1/model-endpoints/{endpoint['id']}/capabilities/conflicts").json()[0]["resolution_options"] == ["keep_disabled", "force_enable", "redetect"]


def test_mongodb_run_queue_executes_and_persists_sample_evidence() -> None:
    captured: list[tuple[str, str, int, dict[str, Any], str]] = []

    class ExactExecutor:
        def execute(self, endpoint: Any, api_key: str, input_snapshot: dict[str, Any]) -> SampleExecutionResult:
            captured.append((endpoint.base_url, endpoint.model_name, endpoint.timeout_seconds, endpoint.custom_headers, api_key))
            assert endpoint.model_name == "model"
            assert api_key == "rotated-secret"
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
    settings = Settings.local_development(
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
            json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "model", "timeout_seconds": 42, "custom_headers": {"X-Run-Mode": "frozen"}},
        ).json()
        assert api.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = api.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1})
        assert run.status_code == 201
        assert run.json()["display_name"] == format_run_display_name(
            "model",
            "text-quick-check",
            datetime.fromisoformat(run.json()["created_at"]),
        )
        changed = api.patch(
            f"/api/v1/model-endpoints/{endpoint['id']}",
            json={"base_url": "https://changed.models.example.test/v1", "api_key": "rotated-secret", "model_name": "changed", "timeout_seconds": 5, "custom_headers": {"X-Run-Mode": "changed"}},
        )
        assert changed.status_code == 200
        completed = api.post(f"/api/v1/evaluation-runs/{run.json()['id']}/execute")
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
        attempts = api.get(f"/api/v1/evaluation-runs/{run.json()['id']}/attempts")
        assert [(item["status"], item["score"]) for item in attempts.json()] == [("succeeded", 1.0)]
        assert attempts.json()[0]["metric_evidence"] == {"profile_version": METRIC_PROFILE_VERSION}
        assert attempts.json()[0]["request_snapshot"]["model"] == "model"
        assert api.get(f"/api/v1/evaluation-runs/{run.json()['id']}/progress").json()["completion_rate"] == 1
        metrics = api.get(f"/api/v1/analytics/runs/{run.json()['id']}/metrics")
        assert metrics.status_code == 200
        metrics_by_name = {metric["metric_name"]: metric for metric in metrics.json()}
        assert metrics_by_name["score"]["metric_value"] == 1.0
        assert metrics_by_name["f1_macro"]["metric_value"] is None
        assert metrics_by_name["f1_macro"]["availability_reason"]
        assert metrics_by_name["score"]["aggregation_version"] == "2.0.0"
        scatter = api.get(
            "/api/v1/analytics/scatter",
            params={"x_axis": "score", "y_axis": "average_latency_ms"},
        )
        assert scatter.status_code == 200
        assert scatter.json()["plotted_count"] == 1
        assert scatter.json()["points"][0]["run_id"] == run.json()["id"]
        leaderboard = api.get("/api/v1/leaderboard")
        assert leaderboard.status_code == 200
        assert leaderboard.json()["total"] == 1
        assert leaderboard.json()["items"][0]["run_id"] == run.json()["id"]
        assert leaderboard.json()["items"][0]["score"] == 1.0
        assert captured == [("https://models.example.test/v1", "model", 42, {"X-Run-Mode": "frozen"}, "rotated-secret")]


def test_mongodb_manifest_dataset_source_is_registered_and_prepared_automatically(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "manifest-samples.jsonl"
    source.write_text('{"question":"2 + 2"}\n', encoding="utf-8")
    _configure_dataset_download(monkeypatch, source.read_bytes())
    plugin = SimpleNamespace(
        manifest={
            "benchmark_id": "text-quick-check",
            "version": "1.0.0",
            "required_capabilities": ["text_input"],
            "scoring": {"type": "exact_match"},
            "datasets": [{"dataset_id": "manifest-mongo-samples", "version": "2026.07", "revision": "r1", "source_url": "https://datasets.example.test/manifest-samples.jsonl"}],
        },
        samples=lambda _limit: (TextSample("manifest-001", "Reply with only the number: what is 2 + 2?", "4"),),
    )
    monkeypatch.setattr("app.modules.evaluations.mongo_executor.get_installed_plugin", lambda *_args: plugin)
    client = FakeClient()
    settings = Settings.local_development(database_url="mongodb://mongo.test/platform", data_root=str(tmp_path / "data"), secret_encryption_key=Fernet.generate_key().decode())
    app = create_app(settings, connection_tester=SuccessfulTester(), document_store=MongoDocumentStore(settings, client=client))
    with TestClient(app) as api:
        endpoint = api.post("/api/v1/model-endpoints", json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "model"}).json()
        assert api.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        preflight = api.post("/api/v1/evaluation-runs/validate", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1})
        assert preflight.status_code == 200
        assert preflight.json()["can_queue"] is True
        assert preflight.json()["datasets"][0]["status"] == "will_register"

        run = api.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1})
        assert run.status_code == 201
        dataset_id = run.json()["configuration_snapshot"]["datasets"][0]["dataset_version_id"]
        assert {item["id"]: item for item in api.get("/api/v1/datasets").json()}[dataset_id]["status"] == "not_downloaded"

        preparation = api.post("/api/v1/workers/claim", json={"worker_id": "dataset-worker"}).json()
        assert preparation["task_type"] == "dataset_preparation"
        assert api.post(f"/api/v1/workers/tasks/{preparation['id']}/execute", json={"lease_token": preparation["lease_token"]}).json()["status"] == "succeeded"
        assert {item["id"]: item for item in api.get("/api/v1/datasets").json()}[dataset_id]["status"] == "ready"


def test_mongodb_run_scheduling_and_benchmark_rerun_preserve_source_run() -> None:
    client = FakeClient()
    settings = Settings.local_development(database_url="mongodb://mongo.test/platform", secret_encryption_key=Fernet.generate_key().decode())
    app = create_app(settings, connection_tester=SuccessfulTester(), document_store=MongoDocumentStore(settings, client=client))
    with TestClient(app) as api:
        endpoint = api.post("/api/v1/model-endpoints", json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "model"}).json()
        assert api.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        source = api.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}).json()
        assert api.patch(f"/api/v1/evaluation-runs/{source['id']}/scheduling", json={"max_concurrency": 2}).json()["max_concurrency"] == 2
        rerun = api.post(f"/api/v1/evaluation-runs/{source['id']}/rerun-benchmark")
        assert rerun.status_code == 201
        assert rerun.json()["display_name"] == format_run_display_name(
            "model",
            "text-quick-check",
            datetime.fromisoformat(rerun.json()["created_at"]),
        )
        assert rerun.json()["configuration_snapshot"]["rerun_of"] == {"run_id": source["id"], "kind": "benchmark"}


def test_mongodb_benchmark_samples_are_split_into_shards_before_scoring(monkeypatch) -> None:
    class ExactExecutor:
        def execute(self, endpoint: Any, _api_key: str, _input_snapshot: dict[str, Any]) -> SampleExecutionResult:
            return SampleExecutionResult(True, {"model": endpoint.model_name}, "{}", "4")

    plugin = SimpleNamespace(
        manifest={"benchmark_id": "text-quick-check", "version": "1.0.0", "required_capabilities": ["text_input"], "scoring": {"type": "exact_match"}, "datasets": [], "shard_size": 2},
        samples=lambda _limit: tuple(TextSample(f"shard-{index}", "Reply with only the number: what is 2 + 2?", "4") for index in range(5)),
    )
    monkeypatch.setattr("app.modules.evaluations.mongo_executor.get_installed_plugin", lambda *_args: plugin)
    client = FakeClient()
    settings = Settings.local_development(database_url="mongodb://mongo.test/platform", secret_encryption_key=Fernet.generate_key().decode())
    app = create_app(settings, connection_tester=SuccessfulTester(), model_executor=ExactExecutor(), document_store=MongoDocumentStore(settings, client=client))
    with TestClient(app) as api:
        endpoint = api.post("/api/v1/model-endpoints", json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "model"}).json()
        assert api.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = api.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 5}).json()
        tasks = [task for task in api.get("/api/v1/tasks", params={"run_id": run["id"]}).json() if task["task_type"] == "evaluation_shard"]
        assert [task["payload"]["sample_ids"] for task in tasks] == [["shard-0", "shard-1"], ["shard-2", "shard-3"], ["shard-4"]]
        completed = api.post(f"/api/v1/evaluation-runs/{run['id']}/execute")
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
        assert completed.json()["completed_samples"] == 5


def test_mongodb_worker_claim_heartbeat_and_execute_are_lease_safe(tmp_path: Path) -> None:
    class ExactExecutor:
        def execute(self, endpoint: Any, _api_key: str, _input_snapshot: dict[str, Any]) -> SampleExecutionResult:
            return SampleExecutionResult(True, {"model": endpoint.model_name}, "{}", "4")

    client = FakeClient()
    settings = Settings.local_development(database_url="mongodb://mongo.test/platform", data_root=str(tmp_path / "data"), secret_encryption_key=Fernet.generate_key().decode())
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


def test_mongodb_report_delete_removes_shares_password_attempts_and_artifact(tmp_path: Path) -> None:
    client = FakeClient()
    settings = Settings.local_development(
        database_url="mongodb://mongo.test/platform",
        data_root=str(tmp_path),
        secret_encryption_key=Fernet.generate_key().decode(),
    )
    store = MongoDocumentStore(settings, client=client)
    app = create_app(settings, document_store=store)
    now = datetime.now(timezone.utc)

    with TestClient(app) as api:
        artifact = tmp_path / "reports" / "run-id" / "report.json"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("{}", encoding="utf-8")
        store.insert_document("reports", {"id": "report-id", "run_id": "run-id", "report_type": "single_model", "format": "json", "artifact_path": str(artifact), "generator_version": "1.4.0", "generated_at": now})
        store.insert_document("report_shares", {"id": "share-id", "report_id": "report-id", "token_hash": "hash", "expires_at": now + timedelta(days=1), "allow_download": False, "revoked_at": None, "created_at": now})
        store.insert_document("report_share_password_attempts", {"id": "attempt-id", "share_id": "share-id", "client_key": "client-hash", "failure_count": 3, "expires_at": now + timedelta(minutes=5), "updated_at": now})

        assert api.delete("/api/v1/reports/report-id").status_code == 204
        assert api.delete("/api/v1/reports/report-id").status_code == 404

    assert store.get_document("reports", "report-id") is None
    assert store.list_documents("report_shares", query={"report_id": "report-id"}) == []
    assert store.list_documents("report_share_password_attempts", query={"share_id": "share-id"}) == []
    assert not artifact.exists()


def test_mongodb_reclaimed_worker_cannot_persist_a_late_model_result(tmp_path: Path) -> None:
    client = FakeClient()
    settings = Settings.local_development(
        database_url="mongodb://mongo.test/platform",
        data_root=str(tmp_path),
        secret_encryption_key=Fernet.generate_key().decode(),
    )
    store = MongoDocumentStore(settings, client=client)

    class LeaseLosingExecutor:
        def execute(self, _endpoint: Any, _api_key: str, _input_snapshot: dict[str, Any]) -> SampleExecutionResult:
            running = store.list_documents("task_units", query={"task_type": "evaluation_shard", "status": "running"})
            assert len(running) == 1
            assert store.update_document("task_units", running[0]["id"], {"lease_expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)})
            assert store.reclaim_expired_leases() == 1
            return SampleExecutionResult(True, {"model": "late"}, '{"choices":[{"message":{"content":"4"}}]}', "4")

    app = create_app(settings, connection_tester=SuccessfulTester(), model_executor=LeaseLosingExecutor(), document_store=store)
    with TestClient(app) as api:
        endpoint = api.post("/api/v1/model-endpoints", json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "model"}).json()
        assert api.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = api.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}).json()
        claim = api.post("/api/v1/workers/claim", json={"worker_id": "worker-a"}).json()
        late = api.post(f"/api/v1/workers/tasks/{claim['id']}/execute", json={"lease_token": claim["lease_token"]})
        assert late.status_code == 409
        attempt = api.get(f"/api/v1/evaluation-runs/{run['id']}/attempts").json()[0]
        assert attempt["status"] == "pending"
        assert attempt["raw_response"] is None


def test_mongodb_pause_invalidates_a_running_lease_before_a_late_result_can_commit(tmp_path: Path) -> None:
    client = FakeClient()
    settings = Settings.local_development(
        database_url="mongodb://mongo.test/platform",
        data_root=str(tmp_path),
        secret_encryption_key=Fernet.generate_key().decode(),
    )
    store = MongoDocumentStore(settings, client=client)

    class PausingExecutor:
        def execute(self, _endpoint: Any, _api_key: str, _input_snapshot: dict[str, Any]) -> SampleExecutionResult:
            from app.modules.evaluations.api import pause_evaluation_run

            run = store.list_documents("evaluation_runs", query={"status": "running"})[0]
            pause_evaluation_run(str(run["id"]), SimpleNamespace(app=app), None)
            return SampleExecutionResult(True, {"model": "late"}, '{"choices":[{"message":{"content":"4"}}]}', "4")

    app = create_app(settings, connection_tester=SuccessfulTester(), model_executor=PausingExecutor(), document_store=store)
    with TestClient(app) as api:
        endpoint = api.post("/api/v1/model-endpoints", json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "model"}).json()
        assert api.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = api.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "sample_limit": 1}).json()
        claim = api.post("/api/v1/workers/claim", json={"worker_id": "worker-a", "run_id": run["id"]}).json()
        late = api.post(f"/api/v1/workers/tasks/{claim['id']}/execute", json={"lease_token": claim["lease_token"]})
        assert late.status_code == 409
        assert api.get(f"/api/v1/evaluation-runs/{run['id']}").json()["status"] == "paused"
        attempt = api.get(f"/api/v1/evaluation-runs/{run['id']}/attempts").json()[0]
        assert attempt["status"] == "pending"
        assert attempt["raw_response"] is None


def test_mongodb_workspace_catalogs_store_prompts_benchmarks_and_dataset_licenses(tmp_path: Path) -> None:
    client = FakeClient()
    settings = Settings.local_development(database_url="mongodb://mongo.test/platform", data_root=str(tmp_path / "data"), secret_encryption_key=Fernet.generate_key().decode())
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
        uploaded = api.post(f"/api/v1/datasets/{dataset.json()['id']}/upload", json={"filename": "examples.jsonl", "base64_data": base64.b64encode(b'{"question":"2 + 2"}\n').decode("ascii")})
        assert uploaded.status_code == 200
        assert uploaded.json()["status"] == "ready"
        assert uploaded.json()["size_bytes"] == len(b'{"question":"2 + 2"}\n')
        assert api.post(f"/api/v1/datasets/{dataset.json()['id']}/validate").json()["status"] == "ready"
        assert api.put(f"/api/v1/datasets/{dataset.json()['id']}/credential-reference", json={"credential_binding_id": None}).json()["credential_binding_id"] is None
        assert api.get("/api/v1/datasets/disk-usage").json()["cache_bytes"] >= len(b'{"question":"2 + 2"}\n')


def test_mongodb_assets_support_custom_multimodal_runs(tmp_path) -> None:
    class ExactExecutor:
        def execute(self, endpoint: Any, _api_key: str, input_snapshot: dict[str, Any]) -> SampleExecutionResult:
            assert input_snapshot["messages"][0]["content"][1]["type"] == "image"
            return SampleExecutionResult(True, {"model": endpoint.model_name}, "{}", "ok")

    client = FakeClient()
    settings = Settings.local_development(database_url="mongodb://mongo.test/platform", data_root=str(tmp_path), secret_encryption_key=Fernet.generate_key().decode())
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
    settings = Settings.local_development(
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
        assert comparison.json()["runs"]["a"]["display_name"] == first["display_name"]
        assert comparison.json()["runs"]["b"]["display_name"] == second["display_name"]
        comparison_metrics = {
            metric["metric_name"]: metric
            for metric in comparison.json()["named_metrics"]
        }
        assert comparison_metrics["score"]["run_a"]["value"] == 1.0
        assert comparison_metrics["score"]["run_b"]["value"] == 1.0
        assert comparison_metrics["score"]["delta"] == 0.0
        assert comparison.json()["outcome_distribution"][0]["count"] in {0, 1}

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


def test_mongo_dataset_update_and_delete(tmp_path: Path) -> None:
    client = FakeClient()
    settings = Settings.local_development(database_url="mongodb://mongo.test/platform", data_root=str(tmp_path / "data"), secret_encryption_key=Fernet.generate_key().decode())
    app = create_app(settings, document_store=MongoDocumentStore(settings, client=client))
    with TestClient(app) as api:
        created = api.post("/api/v1/datasets", json={"dataset_id": "m", "version": "1", "input_field": "q", "reference_field": "a"})
        assert created.status_code == 201
        body = created.json()
        assert body["input_field"] == "q"
        assert body["revision"] == "main"
        updated = api.put(f"/api/v1/datasets/{body['id']}", json={"dataset_id": "m2", "version": "2", "revision": "default"})
        assert updated.status_code == 200
        assert updated.json()["dataset_id"] == "m2"
        assert updated.json()["revision"] == "default"
        deleted = api.delete(f"/api/v1/datasets/{body['id']}")
        assert deleted.status_code == 200
        assert api.get("/api/v1/datasets").json() == []


def test_mongo_failed_dataset_source_correction_resets_stale_failure(tmp_path: Path) -> None:
    client = FakeClient()
    settings = Settings.local_development(
        database_url="mongodb://mongo.test/platform",
        data_root=str(tmp_path / "data"),
        secret_encryption_key=Fernet.generate_key().decode(),
    )
    store = MongoDocumentStore(settings, client=client)
    app = create_app(settings, document_store=store)
    original_source = "https://datasets.example.test/broken.jsonl"
    corrected_source = "https://datasets.example.test/corrected.jsonl"
    with TestClient(app) as api:
        created = api.post("/api/v1/datasets", json={
            "dataset_id": "repairable-mongo",
            "version": "1",
            "source_url": original_source,
        }).json()
        store.update_document("dataset_versions", created["id"], {
            "status": "failed",
            "error_message": "old download failure",
        })

        corrected = api.put(f"/api/v1/datasets/{created['id']}", json={
            "dataset_id": "repairable-mongo",
            "version": "1",
            "source_url": corrected_source,
        })

        assert corrected.status_code == 200
        assert corrected.json()["status"] == "not_downloaded"
        assert corrected.json()["error_message"] is None


def test_mongo_dataset_run_uses_and_freezes_selected_input_field(tmp_path: Path) -> None:
    client = FakeClient()
    settings = Settings.local_development(
        database_url="mongodb://mongo.test/platform",
        data_root=str(tmp_path / "data"),
        secret_encryption_key=Fernet.generate_key().decode(),
    )
    store = MongoDocumentStore(settings, client=client)
    app = create_app(
        settings,
        connection_tester=SuccessfulTester(),
        document_store=store,
    )
    content = b'{"distractor":"wrong","question":"chosen","answer":"1"}\n'
    with TestClient(app) as api:
        endpoint = api.post("/api/v1/model-endpoints", json={
            "base_url": "https://models.example.test/v1",
            "api_key": "secret",
            "model_name": "model",
        }).json()
        assert api.post(
            f"/api/v1/model-endpoints/{endpoint['id']}/connection-test"
        ).status_code == 200
        dataset = api.post("/api/v1/datasets", json={
            "dataset_id": "mongo-input-selection",
            "version": "1",
        }).json()
        uploaded = api.post(f"/api/v1/datasets/{dataset['id']}/upload", json={
            "filename": "samples.jsonl",
            "base64_data": base64.b64encode(content).decode("ascii"),
        })
        assert uploaded.status_code == 200

        created = api.post("/api/v1/evaluation-runs/dataset", json={
            "model_endpoint_id": endpoint["id"],
            "dataset_version_id": dataset["id"],
            "input_field": "question",
            "reference_field": "answer",
            "sample_limit": 10,
        })

        assert created.status_code == 201
        run = created.json()
        assert run["configuration_snapshot"]["input_field"] == "question"
        assert run["configuration_snapshot"]["reference_field"] == "answer"
        attempts = store.list_documents("sample_attempts", query={"run_id": run["id"]})
        assert attempts[0]["input_snapshot"]["messages"][-1]["content"] == "chosen"


def test_mongo_dataset_run_inherits_profile_defaults_with_record_precedence(
    tmp_path: Path,
) -> None:
    client = FakeClient()
    settings = Settings.local_development(
        database_url="mongodb://mongo.test/platform",
        data_root=str(tmp_path / "data"),
        secret_encryption_key=Fernet.generate_key().decode(),
    )
    store = MongoDocumentStore(settings, client=client)
    app = create_app(
        settings,
        connection_tester=SuccessfulTester(),
        document_store=store,
    )
    content = (
        b'{"question":"first","answer":"1","metadata":{"languages":["fr"],"evaluation_type":"generation"}}\n'
        b'{"question":"second","answer":"2"}\n'
    )
    with TestClient(app) as api:
        endpoint = api.post(
            "/api/v1/model-endpoints",
            json={
                "base_url": "https://models.example.test/v1",
                "api_key": "secret",
                "model_name": "model",
            },
        ).json()
        assert api.post(
            f"/api/v1/model-endpoints/{endpoint['id']}/connection-test"
        ).status_code == 200
        dataset = api.post(
            "/api/v1/datasets",
            json={
                "dataset_id": "mongo-profiled",
                "version": "1",
                "input_field": "question",
                "reference_field": "answer",
                "capabilities": ["classification"],
                "languages": ["en-US"],
                "evaluation_type": "classification",
            },
        ).json()
        uploaded = api.post(
            f"/api/v1/datasets/{dataset['id']}/upload",
            json={
                "filename": "profiled.jsonl",
                "base64_data": base64.b64encode(content).decode("ascii"),
            },
        )
        assert uploaded.status_code == 200

        created = api.post(
            "/api/v1/evaluation-runs/dataset",
            json={
                "model_endpoint_id": endpoint["id"],
                "dataset_version_id": dataset["id"],
                "sample_limit": 10,
            },
        )
        assert created.status_code == 201
        snapshot = created.json()["configuration_snapshot"]
        assert snapshot["input_field"] == "question"
        assert snapshot["reference_field"] == "answer"
        assert snapshot["dataset_profile"]["evaluation_type"] == "classification"
        attempts = store.list_documents(
            "sample_attempts", query={"run_id": created.json()["id"]}
        )
        by_prompt = {
            attempt["input_snapshot"]["messages"][-1]["content"]: attempt
            for attempt in attempts
        }
        assert by_prompt["first"]["input_snapshot"]["metadata"]["languages"] == ["fr"]
        assert by_prompt["first"]["input_snapshot"]["metadata"]["capabilities"] == ["classification"]
        assert by_prompt["first"]["reference_snapshot"]["dataset_profile"]["evaluation_type"] == "generation"
        assert by_prompt["second"]["input_snapshot"]["metadata"]["languages"] == ["en-US"]
        assert by_prompt["second"]["reference_snapshot"]["dataset_profile"]["evaluation_type"] == "classification"


def test_mongo_dataset_run_scoring_rule_precedence_validation_and_snapshots(tmp_path: Path) -> None:
    client = FakeClient()
    settings = Settings.local_development(
        database_url="mongodb://mongo.test/platform",
        data_root=str(tmp_path / "data"),
        secret_encryption_key=Fernet.generate_key().decode(),
    )
    store = MongoDocumentStore(settings, client=client)
    app = create_app(
        settings,
        connection_tester=SuccessfulTester(),
        document_store=store,
    )
    content = b'{"question":"blue sky","answer":"BLUE"}\n'
    with TestClient(app) as api:
        endpoint = api.post("/api/v1/model-endpoints", json={
            "base_url": "https://models.example.test/v1",
            "api_key": "secret",
            "model_name": "model",
        }).json()
        assert api.post(
            f"/api/v1/model-endpoints/{endpoint['id']}/connection-test"
        ).status_code == 200
        dataset = api.post("/api/v1/datasets", json={
            "dataset_id": "mongo-scoring",
            "version": "1",
        }).json()
        assert api.post(f"/api/v1/datasets/{dataset['id']}/upload", json={
            "filename": "samples.jsonl",
            "base64_data": base64.b64encode(content).decode("ascii"),
        }).status_code == 200
        package_rule = {"type": "regex_match", "pattern": "BLUE"}
        package = api.post("/api/v1/prompt-packages", json={
            "name": "mongo-scoring-template",
            "version": "1.0.0",
            "user_template": "Q: {{question}}",
            "scoring_rule": package_rule,
        })
        assert package.status_code == 201
        base_payload = {
            "model_endpoint_id": endpoint["id"],
            "dataset_version_id": dataset["id"],
            "input_field": "question",
            "reference_field": "answer",
            "sample_limit": 10,
        }

        expected_rules = [
            (base_payload, {"type": "exact_match"}),
            ({**base_payload, "prompt_package_id": package.json()["id"]}, package_rule),
            ({
                **base_payload,
                "prompt_package_id": package.json()["id"],
                "scoring_rule": {"type": "token_f1"},
            }, {"type": "token_f1"}),
        ]
        for payload, expected_rule in expected_rules:
            preflight = api.post("/api/v1/evaluation-runs/dataset/preflight", json=payload)
            assert preflight.status_code == 200
            assert preflight.json()["can_queue"] is True
            created = api.post("/api/v1/evaluation-runs/dataset", json=payload)
            assert created.status_code == 201
            run = created.json()
            assert run["configuration_snapshot"]["scoring_rule"] == expected_rule
            attempts = store.list_documents("sample_attempts", query={"run_id": run["id"]})
            assert attempts
            assert all(attempt["reference_snapshot"]["scoring"] == expected_rule for attempt in attempts)

        judge = api.post("/api/v1/model-endpoints", json={
            "base_url": "https://judge.example.test/v1",
            "api_key": "judge-secret",
            "model_name": "judge-model",
            "custom_headers": {"X-Judge-Secret": "must-not-appear"},
        }).json()
        assert api.post(f"/api/v1/model-endpoints/{judge['id']}/connection-test").status_code == 200
        judge_rule = {
            "type": "llm_judge",
            "judge_endpoint_id": judge["id"],
            "system_message": "Judge each candidate against the reference.",
        }
        judge_payload = {**base_payload, "scoring_rule": judge_rule}
        judge_preflight = api.post("/api/v1/evaluation-runs/dataset/preflight", json=judge_payload)
        assert judge_preflight.status_code == 200
        assert judge_preflight.json()["can_queue"] is True
        assert judge_preflight.json()["judge_estimate"]["estimated_requests"] == 1
        judge_run = api.post("/api/v1/evaluation-runs/dataset", json=judge_payload)
        assert judge_run.status_code == 201
        snapshot = judge_run.json()["configuration_snapshot"]
        assert snapshot["judge"]["endpoint"]["id"] == judge["id"]
        assert snapshot["judge"]["reference_field"] == "answer"
        assert "judge-secret" not in str(snapshot)
        assert "must-not-appear" not in str(snapshot)
        attempts = store.list_documents("sample_attempts", query={"run_id": judge_run.json()["id"]})
        assert all(attempt["reference_snapshot"]["judge"] == snapshot["judge"] for attempt in attempts)

        unavailable_judge = api.post("/api/v1/model-endpoints", json={
            "base_url": "https://offline-judge.example.test/v1",
            "api_key": "offline-judge-secret",
            "model_name": "offline-judge",
        }).json()

        for invalid_rule, message in (
            ({**judge_rule, "judge_endpoint_id": endpoint["id"]}, "cannot judge its own"),
            ({**judge_rule, "judge_endpoint_id": "missing-judge"}, "Judge model endpoint not found"),
            ({**judge_rule, "judge_endpoint_id": unavailable_judge["id"]}, "must pass a connection test"),
        ):
            invalid_preflight = api.post(
                "/api/v1/evaluation-runs/dataset/preflight",
                json={**base_payload, "scoring_rule": invalid_rule},
            )
            assert invalid_preflight.status_code == 200
            assert invalid_preflight.json()["can_queue"] is False
            assert any(message in issue for issue in invalid_preflight.json()["issues"])
            assert api.post(
                "/api/v1/evaluation-runs/dataset",
                json={**base_payload, "scoring_rule": invalid_rule},
            ).status_code == 409

        run_count = len(store.list_documents("evaluation_runs"))
        invalid_rule = {**base_payload, "scoring_rule": {"type": "regex_match"}}
        assert api.post(
            "/api/v1/evaluation-runs/dataset/preflight",
            json=invalid_rule,
        ).status_code == 422
        assert api.post(
            "/api/v1/evaluation-runs/dataset",
            json=invalid_rule,
        ).status_code == 422
        assert len(store.list_documents("evaluation_runs")) == run_count


def test_mongo_dataset_run_automatically_records_llm_judge_evidence(tmp_path: Path) -> None:
    class JudgeExecutor:
        def __init__(self) -> None:
            self.judge_inputs: list[dict[str, Any]] = []
            self.judge_endpoint_calls: list[tuple[str, str, int]] = []

        def execute(self, endpoint: Any, _api_key: str, input_snapshot: dict[str, Any]) -> SampleExecutionResult:
            if endpoint.model_name == "judge-model":
                self.judge_endpoint_calls.append((endpoint.base_url, endpoint.model_name, endpoint.timeout_seconds))
                self.judge_inputs.append(input_snapshot)
                return SampleExecutionResult(
                    True,
                    {"model": endpoint.model_name},
                    '{"choices":[{"message":{"content":"{\\"score\\": 0.8, \\"label\\": \\"pass\\"}"}}]}',
                    '{"score": 0.8, "label": "pass"}',
                    input_tokens=12,
                    output_tokens=8,
                )
            return SampleExecutionResult(True, {"model": endpoint.model_name}, "{}", "BLUE")

    client = FakeClient()
    settings = Settings.local_development(
        database_url="mongodb://mongo.test/platform",
        data_root=str(tmp_path / "data"),
        secret_encryption_key=Fernet.generate_key().decode(),
    )
    store = MongoDocumentStore(settings, client=client)
    executor = JudgeExecutor()
    app = create_app(
        settings,
        connection_tester=SuccessfulTester(),
        model_executor=executor,
        document_store=store,
    )
    with TestClient(app) as api:
        target = api.post(
            "/api/v1/model-endpoints",
            json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "target-model"},
        ).json()
        judge = api.post(
            "/api/v1/model-endpoints",
            json={"base_url": "https://judge.example.test/v1", "api_key": "judge-secret", "model_name": "judge-model", "input_cost_per_million": 2, "output_cost_per_million": 3},
        ).json()
        assert api.post(f"/api/v1/model-endpoints/{target['id']}/connection-test").status_code == 200
        assert api.post(f"/api/v1/model-endpoints/{judge['id']}/connection-test").status_code == 200
        dataset = api.post("/api/v1/datasets", json={"dataset_id": "mongo-judge", "version": "1"}).json()
        assert api.post(
            f"/api/v1/datasets/{dataset['id']}/upload",
            json={
                "filename": "samples.jsonl",
                "base64_data": base64.b64encode(b'{"question":"blue sky","answer":"BLUE"}\n').decode("ascii"),
            },
        ).status_code == 200
        system_message = "Judge the target answer using the supplied reference."
        run = api.post(
            "/api/v1/evaluation-runs/dataset",
            json={
                "model_endpoint_id": target["id"],
                "dataset_version_id": dataset["id"],
                "input_field": "question",
                "reference_field": "answer",
                "scoring_rule": {
                    "type": "llm_judge",
                    "judge_endpoint_id": judge["id"],
                    "system_message": system_message,
                },
            },
        )
        assert run.status_code == 201
        store.update_document(
            "model_endpoints",
            judge["id"],
            {
                "base_url": "https://judge-edited.example.test/v1",
                "model_name": "judge-edited-model",
                "timeout_seconds": 30,
                "input_cost_per_million": 99,
                "output_cost_per_million": 99,
            },
        )
        assert api.post(f"/api/v1/evaluation-runs/{run.json()['id']}/execute").json()["status"] == "completed"
        assert executor.judge_endpoint_calls == [("https://judge.example.test/v1", "judge-model", 60)]
        attempts = api.get(f"/api/v1/evaluation-runs/{run.json()['id']}/attempts").json()
        assert len(attempts) == 1
        assert attempts[0]["status"] == "succeeded"
        assert attempts[0]["score"] is None
        judge_evidence = attempts[0]["metric_evidence"]["llm_judge"]
        assert isinstance(judge_evidence["assessment_id"], str)
        assert judge_evidence["status"] == "succeeded"
        assert judge_evidence["score"] == 0.8
        assert judge_evidence["label"] == "pass"
        metrics = {
            item["metric_name"]: item
            for item in api.get(f"/api/v1/analytics/runs/{run.json()['id']}/metrics").json()
        }
        assert metrics["llm_judge"]["metric_value"] == 0.8
        assert metrics["llm_judge"]["sample_count"] == 1
        assert metrics["llm_judge"]["confidence_interval"] == {
            "method": "normal_95",
            "lower": 0.8,
            "upper": 0.8,
        }
        leaderboard = api.get("/api/v1/leaderboard", params={"available_metric": "llm_judge"})
        assert [item["run_id"] for item in leaderboard.json()["items"]] == [run.json()["id"]]
        assessments = store.list_documents("judge_assessments", query={"sample_attempt_id": attempts[0]["id"]})
        assert len(assessments) == 1
        assert assessments[0]["rubric"] == {"source": "llm_judge_metric", "reference_field": "answer"}
        assert assessments[0]["input_tokens"] == 12
        assert assessments[0]["output_tokens"] == 8
        assert assessments[0]["estimated_cost"] == round((12 * 2 + 8 * 3) / 1_000_000, 12)
        assert executor.judge_inputs[0]["messages"][0]["content"] == system_message
        judge_payload = json.loads(executor.judge_inputs[0]["messages"][1]["content"])
        assert judge_payload["reference"]["answer"] == "BLUE"


def test_mongo_dataset_delete_is_blocked_while_a_run_references_the_revision(tmp_path: Path) -> None:
    client = FakeClient()
    settings = Settings.local_development(database_url="mongodb://mongo.test/platform", data_root=str(tmp_path / "data"), secret_encryption_key=Fernet.generate_key().decode())
    app = create_app(settings, document_store=MongoDocumentStore(settings, client=client))
    with TestClient(app) as api:
        created = api.post("/api/v1/datasets", json={"dataset_id": "guarded", "version": "1"}).json()
        app.state.document_store.insert_document("evaluation_runs", {
            "model_endpoint_id": "endpoint-x",
            "benchmark_id": "dataset-evaluation",
            "benchmark_version": "1",
            "configuration_snapshot": {"datasets": [{"dataset_version_id": created["id"]}]},
            "status": "completed",
            "total_samples": 1,
        })
        blocked = api.delete(f"/api/v1/datasets/{created['id']}")
        assert blocked.status_code == 409
        assert "references this revision" in blocked.json()["detail"]
        listed = api.get("/api/v1/datasets").json()
        assert any(item["id"] == created["id"] for item in listed)


def test_mongo_recompute_replaces_legacy_aggregation_rows_for_the_run() -> None:
    store = MongoDocumentStore(Settings.local_development(database_url="mongodb://mongo.test/platform"), client=FakeClient())
    run = store.insert_document("evaluation_runs", {
        "model_endpoint_id": "endpoint-1",
        "benchmark_id": "benchmark-a",
        "benchmark_version": "1.0.0",
        "configuration_snapshot": {"dataset_profile": {"evaluation_type": "custom"}},
        "status": "completed",
        "total_samples": 1,
        "completed_samples": 1,
        "successful_samples": 1,
        "failed_samples": 0,
        "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
    })
    store.insert_document("aggregate_metrics", {
        "run_id": run["id"],
        "benchmark_id": "benchmark-a",
        "model_endpoint_id": "endpoint-1",
        "metric_name": "score",
        "metric_value": 0.5,
        "availability_reason": None,
        "sample_count": 1,
        "aggregation_version": "1.0.0",
    })
    rows = recompute_mongo_aggregate_metrics(store, run["id"])
    remaining = store.list_documents("aggregate_metrics", query={"run_id": run["id"]})
    assert rows
    assert remaining
    assert all(row["aggregation_version"] == AGGREGATION_VERSION for row in remaining)
