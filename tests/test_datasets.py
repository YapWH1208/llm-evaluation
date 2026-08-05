import base64
import hashlib
import json
from pathlib import Path
import zipfile
import httpx
import pytest
from fastapi.testclient import TestClient
from app.core.config import DatasetCredentialBinding, Settings
from app.main import create_app
from app.services.datasets import DatasetError, prepare_dataset_cache, resolve_dataset_source, write_dataset_source

def test_dataset_license_gate_and_acknowledgement(tmp_path: Path) -> None:
    app=create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path/'db.sqlite'}",data_root=str(tmp_path/'data')))
    with TestClient(app) as client:
        created=client.post("/api/v1/datasets",json={"dataset_id":"demo","version":"1","license_text":"terms"})
        assert created.status_code==201
        body=created.json();assert body["status"]=="license_required"
        accepted=client.post(f"/api/v1/datasets/{body['id']}/accept-license")
        assert accepted.status_code==200;assert accepted.json()["status"]=="not_downloaded";assert accepted.json()["license_accepted_at"]
        cleared=client.delete(f"/api/v1/datasets/{body['id']}/cache")
        assert cleared.status_code==200;assert cleared.json()["status"]=="not_downloaded";assert cleared.json()["local_path"] is None


def test_dataset_rejects_local_sources_and_uses_administrator_credential_bindings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.outbound_network.getaddrinfo", lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 0))])
    settings = Settings.local_development(
        database_url=f"sqlite:///{tmp_path/'db.sqlite'}",
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
        local = client.post("/api/v1/datasets", json={"dataset_id":"local","version":"1","source_url":"file:///private/source.jsonl"})
        assert local.status_code == 422
        assert "upload endpoint" in local.json()["detail"]
        legacy = client.post("/api/v1/datasets", json={"dataset_id":"legacy","version":"1","credential_env_var":"LLE_ADMIN_TOKEN"})
        assert legacy.status_code == 422
        assert "credential_binding_id" in str(legacy.json()["detail"])

        protected = client.post("/api/v1/datasets", json={"dataset_id":"private","version":"1","source_url":"https://datasets.example.test/private.jsonl","credential_binding_id":"private-dataset"})
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
    app = create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path/'db.sqlite'}", data_root=str(tmp_path / "data"), dataset_credential_bindings={"dataset-token": DatasetCredentialBinding(environment_variable="DATASET_TOKEN", allowed_hosts=("datasets.example.test",))}))
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json={"dataset_id":"uploaded","version":"1","checksum":checksum})
        assert created.status_code == 201
        uploaded = client.post(f"/api/v1/datasets/{created.json()['id']}/upload", json={"filename":"examples.jsonl","base64_data":base64.b64encode(content).decode("ascii")})
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
        credentials = client.put(f"/api/v1/datasets/{body['id']}/credential-reference", json={"credential_binding_id": "dataset-token"})
        assert credentials.status_code == 200
        assert credentials.json()["credential_binding_id"] == "dataset-token"
        usage = client.get("/api/v1/datasets/disk-usage")
        assert usage.status_code == 200
        assert usage.json()["cache_bytes"] >= len(content)
        assert usage.json()["available_bytes"] > 0
        unsupported = client.post(f"/api/v1/datasets/{body['id']}/upload", json={"filename":"examples.exe","base64_data":base64.b64encode(content).decode("ascii")})
        assert unsupported.status_code == 409
        assert "file type" in unsupported.json()["detail"]
        mismatch = client.post("/api/v1/datasets", json={"dataset_id":"mismatch","version":"1","checksum":"0" * 64}).json()
        rejected = client.post(f"/api/v1/datasets/{mismatch['id']}/upload", json={"filename":"examples.jsonl","base64_data":base64.b64encode(content).decode("ascii")})
        assert rejected.status_code == 409
        items = {item["id"]: item for item in client.get("/api/v1/datasets").json()}
        assert items[mismatch["id"]]["status"] == "corrupted"


def test_dataset_source_blocks_unsafe_schemes_private_networks_and_unapproved_bindings(tmp_path: Path, monkeypatch) -> None:
    with pytest.raises(DatasetError, match="private or restricted"):
        resolve_dataset_source("https://127.0.0.1/private.jsonl", "main", None)
    with pytest.raises(DatasetError, match="HTTPS URL"):
        resolve_dataset_source("file:///private.jsonl", "main", None)
    with pytest.raises(DatasetError, match="HTTPS URL"):
        resolve_dataset_source(str(tmp_path / "private.jsonl"), "main", None)
    monkeypatch.setattr("app.services.outbound_network.getaddrinfo", lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 0))])
    settings = Settings.local_development(
        database_url="sqlite:///./ignored.db",
        dataset_credential_bindings={
            "huggingface": DatasetCredentialBinding("HUGGINGFACE_TOKEN", ("huggingface.co",)),
        },
    )
    monkeypatch.setenv("HUGGINGFACE_TOKEN", "test-token")
    resolved, headers = resolve_dataset_source("hf://owner/repository/path/to/file.jsonl", "main", "huggingface", settings)
    assert resolved == "https://huggingface.co/datasets/owner/repository/resolve/main/path/to/file.jsonl"
    assert headers == {"Authorization": "Bearer test-token"}
    with pytest.raises(DatasetError, match="not authorized"):
        resolve_dataset_source("https://other.example.test/dataset.jsonl", "main", "huggingface", settings)
    with pytest.raises(DatasetError, match="not configured"):
        resolve_dataset_source("https://datasets.example.test/dataset.jsonl", "main", "LLE_ADMIN_TOKEN", settings)


def test_dataset_download_enforces_streamed_byte_limit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.outbound_network.getaddrinfo", lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 0))])
    monkeypatch.setattr(
        "app.services.datasets.pinned_outbound_transport",
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
