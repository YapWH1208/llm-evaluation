from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.db.mongo import MongoDocumentStore
from app.services.datasets import DatasetError


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
    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise DatasetError("Dataset source URL must be HTTP or HTTPS.")
    if dataset.get("license_text") and dataset.get("license_accepted_at") is None:
        store.update_document("dataset_versions", dataset_id, {"status": "license_required"})
        raise DatasetError("Dataset license must be accepted before download.")
    destination = Path(data_root).resolve() / "datasets" / str(dataset["dataset_id"]) / str(dataset["version"]) / str(dataset["revision"])
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / "dataset.bin"
    temporary = destination / "dataset.part"
    store.update_document("dataset_versions", dataset_id, {"status": "downloading", "error_message": None})
    digest = hashlib.sha256()
    try:
        with httpx.stream("GET", source_url, timeout=60, follow_redirects=True) as response:
            response.raise_for_status()
            with temporary.open("wb") as file:
                for chunk in response.iter_bytes():
                    file.write(chunk)
                    digest.update(chunk)
        actual_checksum = digest.hexdigest()
        store.update_document("dataset_versions", dataset_id, {"status": "verifying"})
        expected_checksum = dataset.get("checksum")
        if isinstance(expected_checksum, str) and expected_checksum.lower() != actual_checksum:
            temporary.unlink(missing_ok=True)
            raise DatasetError("Dataset checksum verification failed.")
        temporary.replace(target)
        updated = store.update_document("dataset_versions", dataset_id, {"checksum": actual_checksum, "local_path": str(target), "status": "ready", "error_message": None})
        assert updated is not None
        return updated
    except (httpx.HTTPError, OSError, DatasetError) as error:
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
