import base64
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.db.mongo import MongoDocumentStore
from app.main import create_app
from app.modules.datasets.metadata import (
    DatasetMetadataError,
    normalize_capabilities,
    normalize_languages,
)
from tests.test_mongo_document_store import FakeClient


def test_dataset_metadata_normalization_is_deduplicated_and_stable() -> None:
    assert normalize_capabilities(
        [" Reasoning ", "text input", "reasoning", "tool-use"]
    ) == ["reasoning", "text_input", "tool_use"]
    assert normalize_languages(
        ["ZH-hans-cn", "en-us", "en-US"]
    ) == ["en-US", "zh-Hans-CN"]


@pytest.mark.parametrize(
    ("normalizer", "value"),
    [
        (normalize_capabilities, ["bad/control\nvalue"]),
        (normalize_capabilities, ["x" * 65]),
        (normalize_languages, ["english_US"]),
        (normalize_languages, ["en--US"]),
    ],
)
def test_dataset_metadata_rejects_unsafe_or_invalid_values(normalizer, value) -> None:
    with pytest.raises(DatasetMetadataError):
        normalizer(value)


def test_relational_dataset_metadata_create_edit_and_legacy_defaults(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}")
    )
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/datasets",
            json={
                "dataset_id": "metadata",
                "version": "1",
                "capabilities": [" Reasoning ", "text input", "reasoning"],
                "languages": ["ZH-hans-cn", "en-us", "en-US"],
                "evaluation_type": "generation",
            },
        )
        assert created.status_code == 201
        assert created.json()["capabilities"] == ["reasoning", "text_input"]
        assert created.json()["languages"] == ["en-US", "zh-Hans-CN"]
        assert created.json()["evaluation_type"] == "generation"

        updated = client.put(
            f"/api/v1/datasets/{created.json()['id']}",
            json={
                "dataset_id": "metadata",
                "version": "1",
                "capabilities": ["classification"],
                "languages": ["ms-MY"],
                "evaluation_type": "classification",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["capabilities"] == ["classification"]
        assert updated.json()["languages"] == ["ms-MY"]
        assert updated.json()["evaluation_type"] == "classification"

        omitted = client.post(
            "/api/v1/datasets",
            json={"dataset_id": "legacy-defaults", "version": "1"},
        )
        assert omitted.status_code == 201
        assert omitted.json()["capabilities"] == []
        assert omitted.json()["languages"] == []
        assert omitted.json()["evaluation_type"] == "custom"

        invalid = client.post(
            "/api/v1/datasets",
            json={"dataset_id": "invalid", "version": "1", "languages": ["english_US"]},
        )
        assert invalid.status_code == 422


def test_mongo_dataset_metadata_matches_relational_contract(tmp_path: Path) -> None:
    fake_client = FakeClient()
    settings = Settings.local_development(
        database_url="mongodb://mongo.test/platform",
        data_root=str(tmp_path),
    )
    store = MongoDocumentStore(settings, client=fake_client)
    app = create_app(settings, document_store=store)
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/datasets",
            json={
                "dataset_id": "mongo-metadata",
                "version": "1",
                "capabilities": ["Text Input", "reasoning"],
                "languages": ["EN-us", "zh-hans-CN"],
                "evaluation_type": "generation",
            },
        )
        assert created.status_code == 201
        assert created.json()["capabilities"] == ["reasoning", "text_input"]
        assert created.json()["languages"] == ["en-US", "zh-Hans-CN"]
        assert created.json()["evaluation_type"] == "generation"

        legacy = store.insert_document(
            "dataset_versions",
            {
                "dataset_id": "legacy-document",
                "version": "1",
                "revision": "main",
                "source_url": None,
                "credential_binding_id": None,
                "checksum": None,
                "local_path": None,
                "prepared_path": None,
                "size_bytes": None,
                "license_text": None,
                "license_accepted_at": None,
                "input_field": None,
                "reference_field": None,
                "status": "not_downloaded",
                "error_message": None,
                "created_at": datetime.fromisoformat(created.json()["created_at"]),
            },
        )
        listed = {item["id"]: item for item in client.get("/api/v1/datasets").json()}
        assert listed[legacy["id"]]["capabilities"] == []
        assert listed[legacy["id"]]["languages"] == []
        assert listed[legacy["id"]]["evaluation_type"] == "custom"


def test_mongo_ready_dataset_field_defaults_are_schema_validated(tmp_path: Path) -> None:
    fake_client = FakeClient()
    settings = Settings.local_development(
        database_url="mongodb://mongo.test/platform",
        data_root=str(tmp_path / "data"),
    )
    store = MongoDocumentStore(settings, client=fake_client)
    app = create_app(settings, document_store=store)
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/datasets",
            json={"dataset_id": "mongo-schema", "version": "1"},
        )
        uploaded = client.post(
            f"/api/v1/datasets/{created.json()['id']}/upload",
            json={
                "filename": "records.jsonl",
                "base64_data": base64.b64encode(
                    b'{"question":"2 + 2","answer":"4"}\n'
                ).decode("ascii"),
            },
        )
        assert uploaded.status_code == 200

        stale = client.put(
            f"/api/v1/datasets/{created.json()['id']}",
            json={
                "dataset_id": "mongo-schema",
                "version": "1",
                "input_field": "removed_question",
                "reference_field": "answer",
            },
        )
        assert stale.status_code == 409
        assert "preview schema" in stale.json()["detail"]


def test_dataset_field_defaults_are_distinct_and_revalidated_against_ready_schema(
    tmp_path: Path,
) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
            data_root=str(tmp_path / "data"),
        )
    )
    with TestClient(app) as client:
        identical = client.post(
            "/api/v1/datasets",
            json={
                "dataset_id": "identical",
                "version": "1",
                "input_field": "question",
                "reference_field": "question",
            },
        )
        assert identical.status_code == 422

        created = client.post(
            "/api/v1/datasets",
            json={
                "dataset_id": "schema-defaults",
                "version": "1",
                "input_field": "manual_input",
                "reference_field": "manual_output",
            },
        )
        assert created.status_code == 201
        uploaded = client.post(
            f"/api/v1/datasets/{created.json()['id']}/upload",
            json={
                "filename": "records.jsonl",
                "base64_data": base64.b64encode(
                    b'{"question":"2 + 2","answer":"4"}\n'
                ).decode("ascii"),
            },
        )
        assert uploaded.status_code == 200

        valid = client.put(
            f"/api/v1/datasets/{created.json()['id']}",
            json={
                "dataset_id": "schema-defaults",
                "version": "1",
                "input_field": "question",
                "reference_field": "answer",
            },
        )
        assert valid.status_code == 200

        stale = client.put(
            f"/api/v1/datasets/{created.json()['id']}",
            json={
                "dataset_id": "schema-defaults",
                "version": "1",
                "input_field": "removed_question",
                "reference_field": "answer",
            },
        )
        assert stale.status_code == 409
        assert "preview schema" in stale.json()["detail"]
