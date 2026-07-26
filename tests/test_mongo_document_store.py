from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.mongo import MongoDocumentStore, MongoValidation
from app.db.migrations import LATEST_SCHEMA_VERSION, MIGRATIONS
from app.main import create_app
from app.services.connection_tester import ConnectionTestResult


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
    assert claimed["_id"] == "high"
    assert claimed["status"] == "leased"
    tasks.documents[1]["status"] = "running"
    tasks.documents[1]["lease_expires_at"] = now - timedelta(seconds=1)
    client["override"]["sample_attempts"].insert_one({"_id": "attempt", "task_id": "high", "status": "running"})

    assert store.reclaim_expired_leases() == 1
    assert tasks.documents[1]["status"] == "pending"
    assert client["override"]["sample_attempts"].documents[0]["status"] == "pending"


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
