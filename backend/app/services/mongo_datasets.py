from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.db.mongo import MongoDocumentStore
from app.services.datasets import DatasetError, resolve_dataset_source, write_dataset_source


def accept_mongo_dataset_license(store: MongoDocumentStore, dataset_id: str) -> dict[str, Any]:
    dataset = _get_dataset(store, dataset_id)
    values: dict[str, Any] = {"license_accepted_at": datetime.now(timezone.utc)}
    if dataset["status"] == "license_required":
        values["status"] = "not_downloaded"
    updated = store.update_document("dataset_versions", dataset_id, values)
    assert updated is not None
    return updated


def download_mongo_dataset(
    store: MongoDocumentStore,
    dataset_id: str,
    data_root: str,
) -> dict[str, Any]:
    dataset = _get_dataset(store, dataset_id)
    source_url = dataset.get("source_url")
    if not isinstance(source_url, str) or not source_url:
        raise DatasetError("Dataset has no downloadable source URL.")
    if dataset.get("license_text") and dataset.get("license_accepted_at") is None:
        store.update_document("dataset_versions", dataset_id, {"status": "license_required"})
        raise DatasetError("Dataset license must be accepted before download.")
    destination = Path(data_root).resolve() / "datasets" / str(dataset["dataset_id"]) / str(dataset["version"]) / str(dataset["revision"])
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / "dataset.bin"
    temporary = destination / "dataset.part"
    store.update_document("dataset_versions", dataset_id, {"status": "downloading", "error_message": None})
    try:
        source, headers = resolve_dataset_source(source_url, str(dataset["revision"]), dataset.get("credential_env_var") if isinstance(dataset.get("credential_env_var"), str) else None)
        actual_checksum = write_dataset_source(source, temporary, headers)
        store.update_document("dataset_versions", dataset_id, {"status": "verifying"})
        expected_checksum = dataset.get("checksum")
        if isinstance(expected_checksum, str) and expected_checksum.lower() != actual_checksum:
            temporary.unlink(missing_ok=True)
            raise DatasetError("Dataset checksum verification failed.")
        temporary.replace(target)
        updated = store.update_document("dataset_versions", dataset_id, {"checksum": actual_checksum, "local_path": str(target), "status": "ready", "error_message": None})
        assert updated is not None
        return updated
    except (DatasetError, httpx.HTTPStatusError) as error:
        status_code = getattr(getattr(error, "response", None), "status_code", 0)
        credential_required = dataset.get("credential_env_var") and ("environment variable" in str(error) or status_code in {401, 403})
        store.update_document("dataset_versions", dataset_id, {"status": "credential_required" if credential_required else "failed", "error_message": str(error)[:500]})
        raise DatasetError(str(error)) from error
    except (httpx.HTTPError, OSError) as error:
        store.update_document("dataset_versions", dataset_id, {"status": "failed", "error_message": str(error)[:500]})
        raise DatasetError(str(error)) from error


def clear_mongo_dataset_cache(store: MongoDocumentStore, dataset_id: str, data_root: str) -> dict[str, Any]:
    dataset = _get_dataset(store, dataset_id)
    local_path = dataset.get("local_path")
    if isinstance(local_path, str) and local_path:
        root = (Path(data_root).resolve() / "datasets").resolve()
        target = Path(local_path).resolve()
        if not target.is_relative_to(root):
            raise DatasetError("Dataset cache path is outside the configured dataset root.")
        target.unlink(missing_ok=True)
    status = "license_required" if dataset.get("license_text") and dataset.get("license_accepted_at") is None else "not_downloaded"
    updated = store.update_document("dataset_versions", dataset_id, {"local_path": None, "status": status, "error_message": None})
    assert updated is not None
    return updated


def _get_dataset(store: MongoDocumentStore, dataset_id: str) -> dict[str, Any]:
    dataset = store.get_document("dataset_versions", dataset_id)
    if dataset is None:
        raise DatasetError("Dataset version not found.")
    return dataset
