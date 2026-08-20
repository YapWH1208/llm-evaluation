import base64
import hashlib
import json
from pathlib import Path
import zipfile
import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from app.modules.datasets.api import DatasetCreate
from app.core.config import DatasetCredentialBinding, Settings
from app.db.models import DatasetVersion
from app.db.mongo import MongoDocumentStore
from app.main import create_app
from app.modules.datasets.preparation import (
    DatasetError,
    dataset_edit_lifecycle_updates,
    prepare_dataset_cache,
    resolve_dataset_source,
    write_dataset_source,
)
from tests.test_mongo_document_store import FakeClient


def test_new_dataset_revisions_default_to_main_and_preserve_explicit_legacy_values(tmp_path: Path) -> None:
    assert DatasetCreate(dataset_id="schema-default", version="1").revision == "main"
    assert DatasetCreate(dataset_id="schema-legacy", version="1", revision="default").revision == "default"

    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
            data_root=str(tmp_path / "data"),
        )
    )
    with TestClient(app) as client:
        omitted = client.post("/api/v1/datasets", json={"dataset_id": "api-default", "version": "1"})
        explicit = client.post(
            "/api/v1/datasets",
            json={"dataset_id": "api-legacy", "version": "1", "revision": "default"},
        )

        assert omitted.status_code == 201
        assert omitted.json()["revision"] == "main"
        assert explicit.status_code == 201
        assert explicit.json()["revision"] == "default"

        session = app.state.database.get_session()
        try:
            model_default = DatasetVersion(dataset_id="model-default", version="1")
            session.add(model_default)
            session.commit()
            session.refresh(model_default)
            assert model_default.revision == "main"
        finally:
            session.close()


def test_dataset_license_gate_and_acknowledgement(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", data_root=str(tmp_path / "data"))
    )
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json={"dataset_id": "demo", "version": "1", "license_text": "terms"})
        assert created.status_code == 201
        body = created.json()
        assert body["status"] == "license_required"
        accepted = client.post(f"/api/v1/datasets/{body['id']}/accept-license")
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "not_downloaded"
        assert accepted.json()["license_accepted_at"]
        cleared = client.delete(f"/api/v1/datasets/{body['id']}/cache")
        assert cleared.status_code == 200
        assert cleared.json()["status"] == "not_downloaded"
        assert cleared.json()["local_path"] is None


def test_dataset_rejects_local_sources_and_uses_administrator_credential_bindings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.network.outbound.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 0))],
    )
    settings = Settings.local_development(
        database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
        data_root=str(tmp_path / "data"),
        dataset_credential_bindings={
            "private-dataset": DatasetCredentialBinding(
                environment_variable="LLE_TEST_PRIVATE_DATASET_TOKEN",
                allowed_hosts=("datasets.example.test",),
            )
        },
    )
    app = create_app(settings)
    with TestClient(app) as client:
        local = client.post(
            "/api/v1/datasets",
            json={"dataset_id": "local", "version": "1", "source_url": "file:///private/source.jsonl"},
        )
        assert local.status_code == 422
        assert "upload endpoint" in local.json()["detail"]
        legacy = client.post(
            "/api/v1/datasets",
            json={"dataset_id": "legacy", "version": "1", "credential_env_var": "LLE_DATASET_CREDENTIAL_TOKEN"},
        )
        assert legacy.status_code == 422
        assert "credential_binding_id" in str(legacy.json()["detail"])

        protected = client.post(
            "/api/v1/datasets",
            json={
                "dataset_id": "private",
                "version": "1",
                "source_url": "https://datasets.example.test/private.jsonl",
                "credential_binding_id": "private-dataset",
            },
        )
        assert protected.status_code == 201
        response = client.post(f"/api/v1/datasets/{protected.json()['id']}/download")
        assert response.status_code == 409
        assert "credential binding" in response.json()["detail"]
        items = {item["id"]: item for item in client.get("/api/v1/datasets").json()}
        assert items[protected.json()["id"]]["status"] == "credential_required"
        assert "credential_env_var" not in items[protected.json()["id"]]


def test_dataset_upload_is_checksum_verified_and_stored_outside_the_database(tmp_path: Path) -> None:
    content = b'{"question":"what is 2 + 2?","answer":"4"}\n'
    checksum = hashlib.sha256(content).hexdigest()
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
            data_root=str(tmp_path / "data"),
            dataset_credential_bindings={
                "dataset-token": DatasetCredentialBinding(
                    environment_variable="DATASET_TOKEN", allowed_hosts=("datasets.example.test",)
                )
            },
        )
    )
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json={"dataset_id": "uploaded", "version": "1", "checksum": checksum})
        assert created.status_code == 201
        uploaded = client.post(
            f"/api/v1/datasets/{created.json()['id']}/upload",
            json={"filename": "examples.jsonl", "base64_data": base64.b64encode(content).decode("ascii")},
        )
        assert uploaded.status_code == 200
        body = uploaded.json()
        assert body["status"] == "ready"
        assert body["checksum"] == checksum
        assert body["size_bytes"] == len(content)
        assert Path(body["local_path"]).read_bytes() == content
        assert Path(body["prepared_path"]).is_file()
        validated = client.post(f"/api/v1/datasets/{body['id']}/validate")
        assert validated.status_code == 200
        assert validated.json()["status"] == "ready"
        credentials = client.put(
            f"/api/v1/datasets/{body['id']}/credential-reference", json={"credential_binding_id": "dataset-token"}
        )
        assert credentials.status_code == 200
        assert credentials.json()["credential_binding_id"] == "dataset-token"
        usage = client.get("/api/v1/datasets/disk-usage")
        assert usage.status_code == 200
        assert usage.json()["cache_bytes"] >= len(content)
        assert usage.json()["available_bytes"] > 0
        unsupported = client.post(
            f"/api/v1/datasets/{body['id']}/upload",
            json={"filename": "examples.exe", "base64_data": base64.b64encode(content).decode("ascii")},
        )
        assert unsupported.status_code == 409
        assert "file type" in unsupported.json()["detail"]
        mismatch = client.post(
            "/api/v1/datasets", json={"dataset_id": "mismatch", "version": "1", "checksum": "0" * 64}
        ).json()
        rejected = client.post(
            f"/api/v1/datasets/{mismatch['id']}/upload",
            json={"filename": "examples.jsonl", "base64_data": base64.b64encode(content).decode("ascii")},
        )
        assert rejected.status_code == 409
        items = {item["id"]: item for item in client.get("/api/v1/datasets").json()}
        assert items[mismatch["id"]]["status"] == "corrupted"


def test_dataset_source_blocks_unsafe_schemes_private_networks_and_unapproved_bindings(
    tmp_path: Path, monkeypatch
) -> None:
    with pytest.raises(DatasetError, match="private or restricted"):
        resolve_dataset_source("https://127.0.0.1/private.jsonl", "main", None)
    with pytest.raises(DatasetError, match="HTTPS URL"):
        resolve_dataset_source("file:///private.jsonl", "main", None)
    with pytest.raises(DatasetError, match="HTTPS URL"):
        resolve_dataset_source(str(tmp_path / "private.jsonl"), "main", None)
    monkeypatch.setattr(
        "app.infrastructure.network.outbound.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 0))],
    )
    settings = Settings.local_development(
        database_url="sqlite:///./ignored.db",
        dataset_credential_bindings={
            "huggingface": DatasetCredentialBinding("HUGGINGFACE_TOKEN", ("huggingface.co",)),
        },
    )
    monkeypatch.setenv("HUGGINGFACE_TOKEN", "test-token")
    resolved, headers = resolve_dataset_source(
        "hf://owner/repository/path/to/file.jsonl", "main", "huggingface", settings
    )
    assert resolved == "https://huggingface.co/datasets/owner/repository/resolve/main/path/to/file.jsonl"
    assert headers == {"Authorization": "Bearer test-token"}

    canonical, _ = resolve_dataset_source(
        "hf://datasets/owner/repository/path with spaces/file.jsonl",
        "release/1",
        None,
        settings,
    )
    assert canonical == (
        "https://huggingface.co/datasets/owner/repository/resolve/release%2F1/path%20with%20spaces/file.jsonl"
    )

    owner_named_datasets, _ = resolve_dataset_source(
        "hf://datasets/foo/file.jsonl",
        "main",
        None,
        settings,
    )
    assert owner_named_datasets == "https://huggingface.co/datasets/datasets/foo/resolve/main/file.jsonl"
    two_part_datasets, _ = resolve_dataset_source(
        "hf://datasets/owner/repository",
        "main",
        None,
        settings,
    )
    assert two_part_datasets == "https://huggingface.co/datasets/datasets/owner/resolve/main/repository"

    for owner in ("models", "spaces"):
        shorthand, _ = resolve_dataset_source(
            f"hf://{owner}/owner/repository/file.jsonl",
            "main",
            None,
            settings,
        )
        assert shorthand == (f"https://huggingface.co/datasets/{owner}/owner/resolve/main/repository/file.jsonl")
        with pytest.raises(DatasetError, match="hf://owner/repository/path"):
            resolve_dataset_source(f"hf://{owner}/owner", "main", None, settings)
    with pytest.raises(DatasetError, match="not authorized"):
        resolve_dataset_source("https://other.example.test/dataset.jsonl", "main", "huggingface", settings)
    with pytest.raises(DatasetError, match="not configured"):
        resolve_dataset_source(
            "https://datasets.example.test/dataset.jsonl", "main", "LLE_DATASET_CREDENTIAL_TOKEN", settings
        )


def test_dataset_download_enforces_streamed_byte_limit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.network.outbound.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 0))],
    )
    monkeypatch.setattr(
        "app.modules.datasets.preparation.pinned_outbound_transport",
        lambda *_args, **_kwargs: httpx.MockTransport(lambda _request: httpx.Response(200, content=b"12345678")),
    )
    with pytest.raises(DatasetError, match="byte limit"):
        write_dataset_source("https://datasets.example.test/dataset.jsonl", tmp_path / "dataset.part", {}, max_bytes=6)


def test_dataset_preparation_rejects_archive_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../outside.jsonl", '{"question":"unsafe"}\n')
    with pytest.raises(DatasetError, match="unsafe file path"):
        prepare_dataset_cache(archive)


def _redirect_transport(monkeypatch: pytest.MonkeyPatch, handler, *, extra_public_hosts: tuple[str, ...] = ()) -> None:
    public = ("datasets.example.test",) + extra_public_hosts
    monkeypatch.setattr(
        "app.infrastructure.network.outbound.getaddrinfo",
        lambda host, *_args, **_kwargs: [
            (None, None, None, None, (("93.184.216.34", 0) if host in public else ("127.0.0.1", 0)))
        ],
    )
    monkeypatch.setattr(
        "app.modules.datasets.preparation.pinned_outbound_transport",
        lambda *_args, **_kwargs: httpx.MockTransport(handler),
    )


def test_dataset_download_follows_validated_redirects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if len(calls) == 1:
            return httpx.Response(307, headers={"location": "https://datasets.example.test/final.jsonl"})
        return httpx.Response(200, content=b'{"question":"q","answer":"a"}\n')

    _redirect_transport(monkeypatch, handler)
    digest = write_dataset_source("https://datasets.example.test/start.jsonl", tmp_path / "out.jsonl", {})
    assert digest == hashlib.sha256(b'{"question":"q","answer":"a"}\n').hexdigest()
    assert (tmp_path / "out.jsonl").read_bytes() == b'{"question":"q","answer":"a"}\n'
    assert calls == ["https://datasets.example.test/start.jsonl", "https://datasets.example.test/final.jsonl"]


def test_hugging_face_dataset_download_follows_resolve_cache_redirect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if len(calls) == 1:
            return httpx.Response(
                307,
                headers={"location": "/api/resolve-cache/datasets/owner/repository/revision/hello.txt"},
            )
        return httpx.Response(200, content=b"hello")

    _redirect_transport(monkeypatch, handler, extra_public_hosts=("huggingface.co",))
    source, _ = resolve_dataset_source("hf://datasets/owner/repository/hello.txt", "main", None)
    digest = write_dataset_source(source, tmp_path / "hello.txt", {})

    assert digest == hashlib.sha256(b"hello").hexdigest()
    assert calls == [
        "https://huggingface.co/datasets/owner/repository/resolve/main/hello.txt",
        "https://huggingface.co/api/resolve-cache/datasets/owner/repository/revision/hello.txt",
    ]


def test_dataset_download_rejects_redirect_to_private_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(307, headers={"location": "https://127.0.0.1/secret.jsonl"})

    _redirect_transport(monkeypatch, handler)
    with pytest.raises(DatasetError, match="private or restricted"):
        write_dataset_source("https://datasets.example.test/start.jsonl", tmp_path / "out.jsonl", {})


def test_dataset_download_rejects_redirect_without_location_and_hop_loops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_location(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(307)

    _redirect_transport(monkeypatch, no_location)
    with pytest.raises(DatasetError, match="without a Location header"):
        write_dataset_source("https://datasets.example.test/start.jsonl", tmp_path / "out.jsonl", {})

    def loop(request: httpx.Request) -> httpx.Response:
        return httpx.Response(307, headers={"location": str(request.url)})

    _redirect_transport(monkeypatch, loop)
    with pytest.raises(DatasetError, match="redirected more than 5 times"):
        write_dataset_source("https://datasets.example.test/start.jsonl", tmp_path / "out.jsonl", {})


def test_dataset_download_enforces_byte_limit_after_redirects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "final" in str(request.url):
            return httpx.Response(200, content=b"123456789")
        return httpx.Response(307, headers={"location": "https://datasets.example.test/final.jsonl"})

    _redirect_transport(monkeypatch, handler)
    with pytest.raises(DatasetError, match="byte limit"):
        write_dataset_source("https://datasets.example.test/start.jsonl", tmp_path / "out.jsonl", {}, max_bytes=6)


def test_dataset_download_does_not_forward_authorization_across_hosts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.headers))
        if "final" in str(request.url):
            return httpx.Response(200, content=b"ok")
        return httpx.Response(307, headers={"location": "https://cdn.example.test/final.jsonl"})

    _redirect_transport(monkeypatch, handler, extra_public_hosts=("cdn.example.test",))
    write_dataset_source(
        "https://datasets.example.test/start.jsonl", tmp_path / "out.jsonl", {"Authorization": "Bearer secret"}
    )
    assert any(key.lower() == "authorization" for key in seen[0])
    assert not any(key.lower() == "authorization" for key in seen[1])
    assert (tmp_path / "out.jsonl").read_bytes() == b"ok"


def test_dataset_download_rejects_redirect_outside_allowed_hosts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(307, headers={"location": "https://cdn.example.test/final.jsonl"})

    _redirect_transport(monkeypatch, handler, extra_public_hosts=("cdn.example.test",))
    with pytest.raises(DatasetError, match="not allowed"):
        write_dataset_source(
            "https://datasets.example.test/start.jsonl",
            tmp_path / "out.jsonl",
            {},
            allowed_hosts=("datasets.example.test",),
        )


def test_dataset_create_and_response_carry_input_and_reference_fields(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", data_root=str(tmp_path / "data"))
    )
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/datasets",
            json={
                "dataset_id": "fields",
                "version": "1",
                "input_field": "question",
                "reference_field": "answer",
            },
        )
        assert created.status_code == 201
        body = created.json()
        assert body["input_field"] == "question"
        assert body["reference_field"] == "answer"
        listed = {item["id"]: item for item in client.get("/api/v1/datasets").json()}
        assert listed[body["id"]]["input_field"] == "question"
        assert listed[body["id"]]["reference_field"] == "answer"


def test_dataset_preview_returns_first_rows_from_the_prepared_cache(tmp_path: Path) -> None:
    content = b'{"question":"what is 2 + 2?","answer":"4"}\n{"question":"what is 3 + 3?","answer":"6"}\n{"question":"what is 4 + 4?","answer":"8"}\n'
    app = create_app(
        Settings.local_development(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", data_root=str(tmp_path / "data"))
    )
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json={"dataset_id": "preview", "version": "1"}).json()
        uploaded = client.post(
            f"/api/v1/datasets/{created['id']}/upload",
            json={"filename": "rows.jsonl", "base64_data": base64.b64encode(content).decode("ascii")},
        )
        assert uploaded.status_code == 200
        preview = client.get(f"/api/v1/datasets/{created['id']}/preview")
        assert preview.status_code == 200
        body = preview.json()
        assert body["fields"] == ["question", "answer"]
        assert len(body["rows"]) == 3
        assert body["rows"][0] == {"question": "what is 2 + 2?", "answer": "4"}
        limited = client.get(f"/api/v1/datasets/{created['id']}/preview?limit=1")
        assert len(limited.json()["rows"]) == 1


def test_dataset_preview_requires_a_ready_dataset_and_caps_the_limit(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", data_root=str(tmp_path / "data"))
    )
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json={"dataset_id": "notready", "version": "1"}).json()
        blocked = client.get(f"/api/v1/datasets/{created['id']}/preview")
        assert blocked.status_code == 409
        assert "not ready" in blocked.json()["detail"]
        missing = client.get("/api/v1/datasets/does-not-exist/preview")
        assert missing.status_code == 404
        oversized = client.get(f"/api/v1/datasets/{created['id']}/preview?limit=999")
        assert oversized.status_code == 422


def test_dataset_preview_reports_a_corrupt_prepared_cache_instead_of_a_server_error(tmp_path: Path) -> None:
    content = b'{"question":"what is 2 + 2?","answer":"4"}\n'
    app = create_app(
        Settings.local_development(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", data_root=str(tmp_path / "data"))
    )
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json={"dataset_id": "corrupt", "version": "1"}).json()
        uploaded = client.post(
            f"/api/v1/datasets/{created['id']}/upload",
            json={"filename": "rows.jsonl", "base64_data": base64.b64encode(content).decode("ascii")},
        )
        assert uploaded.status_code == 200
        prepared = Path(uploaded.json()["prepared_path"]).parent
        manifest = json.loads((prepared / "manifest.json").read_text(encoding="utf-8"))
        index = prepared / str(manifest.get("index_path", "sample-index.jsonl"))
        index.unlink()
        preview = client.get(f"/api/v1/datasets/{created['id']}/preview")
        assert preview.status_code == 409
        assert "preview" in preview.json()["detail"]


def test_mongodb_dataset_update_and_delete_of_missing_version_return_404(tmp_path: Path) -> None:
    client = FakeClient()
    settings = Settings.local_development(
        database_url="mongodb://mongo.test/platform",
        data_root=str(tmp_path),
        secret_encryption_key=Fernet.generate_key().decode(),
    )
    app = create_app(settings, document_store=MongoDocumentStore(settings, client=client))
    with TestClient(app) as api:
        missing_update = api.put("/api/v1/datasets/does-not-exist", json={"dataset_id": "x", "version": "1"})
        assert missing_update.status_code == 404
        missing_delete = api.delete("/api/v1/datasets/does-not-exist")
        assert missing_delete.status_code == 404


def test_mongodb_dataset_update_enforces_revision_uniqueness(tmp_path: Path) -> None:
    client = FakeClient()
    settings = Settings.local_development(
        database_url="mongodb://mongo.test/platform",
        data_root=str(tmp_path),
        secret_encryption_key=Fernet.generate_key().decode(),
    )
    app = create_app(settings, document_store=MongoDocumentStore(settings, client=client))

    with TestClient(app) as api:
        api.post(
            "/api/v1/datasets",
            json={"dataset_id": "duplicate", "version": "1", "revision": "main"},
        )
        target = api.post(
            "/api/v1/datasets",
            json={"dataset_id": "target", "version": "1", "revision": "main"},
        ).json()
        response = api.put(
            f"/api/v1/datasets/{target['id']}",
            json={"dataset_id": "duplicate", "version": "1", "revision": "main"},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "Dataset revision already exists"
        persisted = next(item for item in api.get("/api/v1/datasets").json() if item["id"] == target["id"])
        assert persisted["dataset_id"] == "target"


def test_mongodb_dataset_duplicate_key_update_returns_409(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient()
    settings = Settings.local_development(
        database_url="mongodb://mongo.test/platform",
        data_root=str(tmp_path),
        secret_encryption_key=Fernet.generate_key().decode(),
    )
    store = MongoDocumentStore(settings, client=client)
    app = create_app(settings, document_store=store)

    class DuplicateKeyError(Exception):
        pass

    with TestClient(app, raise_server_exceptions=False) as api:
        dataset = api.post(
            "/api/v1/datasets",
            json={"dataset_id": "target", "version": "1", "revision": "main"},
        ).json()

        def duplicate_update(
            collection_name: str,
            document_id: str,
            values: dict[str, object],
        ) -> dict[str, object] | None:
            raise DuplicateKeyError

        monkeypatch.setattr(store, "update_document", duplicate_update)
        response = api.put(
            f"/api/v1/datasets/{dataset['id']}",
            json={"dataset_id": "duplicate", "version": "1", "revision": "main"},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "Dataset revision already exists"


def test_dataset_update_edits_metadata_and_enforces_uniqueness(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", data_root=str(tmp_path / "data"))
    )
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/datasets",
            json={"dataset_id": "dup", "version": "1", "revision": "default"},
        ).json()
        assert first["revision"] == "default"
        second = client.post("/api/v1/datasets", json={"dataset_id": "target", "version": "1"}).json()
        updated = client.put(
            f"/api/v1/datasets/{second['id']}",
            json={
                "dataset_id": "renamed",
                "version": "2",
                "revision": "fixed",
                "input_field": "prompt",
                "reference_field": "expected",
            },
        )
        assert updated.status_code == 200
        body = updated.json()
        assert body["dataset_id"] == "renamed"
        assert body["version"] == "2"
        assert body["revision"] == "fixed"
        assert body["input_field"] == "prompt"
        assert body["reference_field"] == "expected"
        conflicting = client.put(
            f"/api/v1/datasets/{second['id']}", json={"dataset_id": "dup", "version": "1", "revision": "default"}
        )
        assert conflicting.status_code == 409
        bad_source = client.put(
            f"/api/v1/datasets/{second['id']}",
            json={"dataset_id": "renamed", "version": "2", "revision": "fixed", "source_url": "file:///tmp/x.jsonl"},
        )
        assert bad_source.status_code == 422
        missing = client.put("/api/v1/datasets/does-not-exist", json={"dataset_id": "x", "version": "1"})
        assert missing.status_code == 404


@pytest.mark.parametrize(
    ("field", "new_value", "expected_status"),
    [
        ("source_url", "https://datasets.example.test/corrected.jsonl", "not_downloaded"),
        ("revision", "corrected", "not_downloaded"),
        ("checksum", "a" * 64, "not_downloaded"),
        ("license_text", "new terms", "license_required"),
        ("credential_binding_id", "corrected-binding", "not_downloaded"),
    ],
)
def test_inactive_dataset_material_edit_lifecycle_updates(
    field: str,
    new_value: str,
    expected_status: str,
) -> None:
    current = {
        "source_url": "https://datasets.example.test/broken.jsonl",
        "revision": "main",
        "checksum": None,
        "license_text": None,
        "credential_binding_id": None,
        "license_accepted_at": "accepted",
        "local_path": None,
        "prepared_path": None,
        "status": "failed",
        "error_message": "download failed",
    }
    values = {
        key: current[key]
        for key in (
            "source_url",
            "revision",
            "checksum",
            "license_text",
            "credential_binding_id",
        )
    }
    values[field] = new_value

    updates = dataset_edit_lifecycle_updates(current, values)

    assert updates["status"] == expected_status
    assert updates["error_message"] is None
    if field == "license_text":
        assert updates["license_accepted_at"] is None


def test_inactive_dataset_nonmaterial_or_cached_edit_preserves_lifecycle() -> None:
    current = {
        "source_url": "https://datasets.example.test/broken.jsonl",
        "revision": "main",
        "checksum": None,
        "license_text": None,
        "credential_binding_id": None,
        "license_accepted_at": None,
        "local_path": None,
        "prepared_path": None,
        "status": "failed",
        "error_message": "download failed",
    }
    unchanged = {
        key: current[key]
        for key in (
            "source_url",
            "revision",
            "checksum",
            "license_text",
            "credential_binding_id",
        )
    }

    assert dataset_edit_lifecycle_updates(current, unchanged) == {}
    assert (
        dataset_edit_lifecycle_updates(
            {**current, "local_path": "/cached/data.jsonl"},
            {
                **unchanged,
                "source_url": "https://datasets.example.test/corrected.jsonl",
            },
        )
        == {}
    )
    assert (
        dataset_edit_lifecycle_updates(
            {**current, "status": "downloading"},
            {
                **unchanged,
                "source_url": "https://datasets.example.test/corrected.jsonl",
            },
        )
        == {}
    )
    assert (
        dataset_edit_lifecycle_updates(
            {**current, "status": "waiting"},
            {
                **unchanged,
                "source_url": "https://datasets.example.test/corrected.jsonl",
            },
        )
        == {}
    )


def test_relational_failed_dataset_source_correction_resets_stale_failure(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
            data_root=str(tmp_path / "data"),
        )
    )
    original_source = "https://datasets.example.test/broken.jsonl"
    corrected_source = "https://datasets.example.test/corrected.jsonl"
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/datasets",
            json={
                "dataset_id": "repairable",
                "version": "1",
                "source_url": original_source,
            },
        ).json()
        with app.state.database.get_session() as session:
            dataset = session.get(DatasetVersion, created["id"])
            assert dataset is not None
            dataset.status = "failed"
            dataset.error_message = "old download failure"
            session.commit()

        corrected = client.put(
            f"/api/v1/datasets/{created['id']}",
            json={
                "dataset_id": "repairable",
                "version": "1",
                "source_url": corrected_source,
            },
        )
        assert corrected.status_code == 200
        assert corrected.json()["status"] == "not_downloaded"
        assert corrected.json()["error_message"] is None

        with app.state.database.get_session() as session:
            dataset = session.get(DatasetVersion, created["id"])
            assert dataset is not None
            dataset.status = "failed"
            dataset.error_message = "new download failure"
            session.commit()

        metadata_only = client.put(
            f"/api/v1/datasets/{created['id']}",
            json={
                "dataset_id": "repairable",
                "version": "1",
                "source_url": corrected_source,
                "input_field": "prompt",
            },
        )
        assert metadata_only.status_code == 200
        assert metadata_only.json()["status"] == "failed"
        assert metadata_only.json()["error_message"] == "new download failure"


def test_dataset_delete_removes_registration_and_cache_but_guards_referenced_versions(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", data_root=str(tmp_path / "data"))
    )
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json={"dataset_id": "doomed", "version": "1"}).json()
        content = b'{"question":"q?","answer":"a"}\n'
        uploaded = client.post(
            f"/api/v1/datasets/{created['id']}/upload",
            json={"filename": "rows.jsonl", "base64_data": base64.b64encode(content).decode("ascii")},
        )
        assert uploaded.status_code == 200
        deleted = client.delete(f"/api/v1/datasets/{created['id']}")
        assert deleted.status_code == 200
        listed = client.get("/api/v1/datasets").json()
        assert all(item["id"] != created["id"] for item in listed)
        gone = client.get(f"/api/v1/datasets/{created['id']}/preview")
        assert gone.status_code == 404
        missing = client.delete("/api/v1/datasets/does-not-exist")
        assert missing.status_code == 404


def test_dataset_delete_is_blocked_while_a_run_references_the_revision(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", data_root=str(tmp_path / "data"))
    )
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json={"dataset_id": "referenced", "version": "1"}).json()
        content = b'{"question":"q?","answer":"a"}\n'
        uploaded = client.post(
            f"/api/v1/datasets/{created['id']}/upload",
            json={"filename": "rows.jsonl", "base64_data": base64.b64encode(content).decode("ascii")},
        )
        assert uploaded.status_code == 200
        session = app.state.database.get_session()
        try:
            from app.db.models import DatasetVersion, EvaluationRun, ModelEndpoint

            session.add(
                ModelEndpoint(
                    id="endpoint-x",
                    display_name="test",
                    base_url="https://models.example.test/v1",
                    model_name="example-model",
                    encrypted_api_key="not-a-real-key",
                    api_key_mask="not-a-real-key",
                )
            )
            session.flush()
            dataset = session.get(DatasetVersion, created["id"])
            assert dataset is not None
            session.add(
                EvaluationRun(
                    model_endpoint_id="endpoint-x",
                    benchmark_id="dataset-evaluation",
                    benchmark_version="1",
                    configuration_snapshot={"datasets": [{"dataset_version_id": created["id"]}]},
                    status="completed",
                    total_samples=1,
                )
            )
            session.commit()
        finally:
            session.close()
    with TestClient(app) as client:
        blocked = client.delete(f"/api/v1/datasets/{created['id']}")
        assert blocked.status_code == 409
        assert "references this revision" in blocked.json()["detail"]
        listed = client.get("/api/v1/datasets").json()
        assert any(item["id"] == created["id"] for item in listed)
