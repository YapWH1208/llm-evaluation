from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.core.config import DEFAULT_DATASET_DOWNLOAD_MAX_BYTES, Settings
from app.db.mongo import MongoDocumentStore
from app.services.datasets import DatasetDownloadPaused, DatasetError, clear_prepared_dataset_cache, dataset_disk_usage, dataset_source_suffix, prepare_dataset_cache, resolve_dataset_source, validate_prepared_dataset_cache, write_dataset_source


def accept_mongo_dataset_license(store: MongoDocumentStore, dataset_id: str) -> dict[str, Any]:
    dataset = _get_dataset(store, dataset_id)
    values: dict[str, Any] = {"license_accepted_at": datetime.now(timezone.utc)}
    if dataset["status"] == "license_required":
        values["status"] = "not_downloaded"
    updated = store.update_document("dataset_versions", dataset_id, values)
    assert updated is not None
    return updated


def store_mongo_uploaded_dataset(
    store: MongoDocumentStore,
    dataset_id: str,
    *,
    filename: str,
    content: bytes,
    data_root: str,
) -> dict[str, Any]:
    dataset = _get_dataset(store, dataset_id)
    if not content:
        raise DatasetError("Uploaded dataset is empty.")
    if len(content) > 64 * 1024 * 1024:
        raise DatasetError("Uploaded dataset exceeds the 64 MiB upload limit.")
    safe_name = Path(filename).name
    if not safe_name or safe_name in {".", ".."}:
        raise DatasetError("Uploaded dataset filename is invalid.")
    if Path(safe_name).suffix.lower() not in {".json", ".jsonl", ".csv", ".tsv", ".txt", ".zip", ".parquet"}:
        raise DatasetError("Uploaded dataset file type is not supported.")
    if dataset.get("license_text") and dataset.get("license_accepted_at") is None:
        store.update_document("dataset_versions", dataset_id, {"status": "license_required"})
        raise DatasetError("Dataset license must be accepted before upload.")
    destination = (Path(data_root).resolve() / "datasets" / "uploads" / dataset_id).resolve()
    root = (Path(data_root).resolve() / "datasets").resolve()
    if not destination.is_relative_to(root):
        raise DatasetError("Dataset upload path is outside the configured dataset root.")
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / safe_name
    temporary = destination / f".{safe_name}.part"
    import hashlib

    checksum = hashlib.sha256(content).hexdigest()
    expected_checksum = dataset.get("checksum")
    if isinstance(expected_checksum, str) and expected_checksum.lower() != checksum:
        store.update_document("dataset_versions", dataset_id, {"status": "corrupted", "error_message": "Uploaded dataset checksum verification failed."})
        raise DatasetError("Uploaded dataset checksum verification failed.")
    temporary.write_bytes(content)
    temporary.replace(target)
    store.update_document("dataset_versions", dataset_id, {"status": "preparing", "error_message": None})
    prepared_path = prepare_dataset_cache(target)
    updated = store.update_document("dataset_versions", dataset_id, {"source_url": target.as_uri(), "checksum": checksum, "size_bytes": len(content), "local_path": str(target), "prepared_path": str(prepared_path), "status": "ready", "error_message": None})
    assert updated is not None
    return updated


def download_mongo_dataset(
    store: MongoDocumentStore,
    dataset_id: str,
    data_root: str,
    settings: Settings | None = None,
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
    target = destination / f"dataset{dataset_source_suffix(source_url)}"
    temporary = destination / "dataset.part"
    store.update_document("dataset_versions", dataset_id, {"status": "downloading", "error_message": None})
    try:
        source, headers = resolve_dataset_source(
            source_url,
            str(dataset["revision"]),
            dataset.get("credential_binding_id") if isinstance(dataset.get("credential_binding_id"), str) else None,
            settings,
        )
        def ensure_not_paused() -> None:
            current = _get_dataset(store, dataset_id)
            if current.get("status") == "waiting":
                raise DatasetDownloadPaused("Dataset download was paused and can be retried.")

        actual_checksum = write_dataset_source(
            source,
            temporary,
            headers,
            ensure_not_paused,
            max_bytes=(settings.dataset_download_max_bytes if settings is not None else DEFAULT_DATASET_DOWNLOAD_MAX_BYTES),
            allowed_hosts=settings.dataset_allowed_hosts if settings is not None else (),
        )
        store.update_document("dataset_versions", dataset_id, {"status": "verifying"})
        expected_checksum = dataset.get("checksum")
        if isinstance(expected_checksum, str) and expected_checksum.lower() != actual_checksum:
            temporary.unlink(missing_ok=True)
            raise DatasetError("Dataset checksum verification failed.")
        temporary.replace(target)
        store.update_document("dataset_versions", dataset_id, {"status": "preparing"})
        prepared_path = prepare_dataset_cache(target)
        updated = store.update_document("dataset_versions", dataset_id, {"checksum": actual_checksum, "size_bytes": target.stat().st_size, "local_path": str(target), "prepared_path": str(prepared_path), "status": "ready", "error_message": None})
        assert updated is not None
        return updated
    except DatasetDownloadPaused as error:
        store.update_document("dataset_versions", dataset_id, {"status": "waiting", "error_message": None})
        raise DatasetError(str(error)) from error
    except (DatasetError, httpx.HTTPStatusError) as error:
        status_code = getattr(getattr(error, "response", None), "status_code", 0)
        credential_required = dataset.get("credential_binding_id") and ("credential binding" in str(error) or status_code in {401, 403})
        store.update_document("dataset_versions", dataset_id, {"status": "credential_required" if credential_required else "failed", "error_message": str(error)[:500]})
        raise DatasetError(str(error)) from error
    except (httpx.HTTPError, OSError) as error:
        store.update_document("dataset_versions", dataset_id, {"status": "failed", "error_message": str(error)[:500]})
        raise DatasetError(str(error)) from error


def clear_mongo_dataset_cache(store: MongoDocumentStore, dataset_id: str, data_root: str) -> dict[str, Any]:
    dataset = _get_dataset(store, dataset_id)
    for run in store.list_documents("evaluation_runs"):
        snapshot = run.get("configuration_snapshot") if isinstance(run.get("configuration_snapshot"), dict) else {}
        descriptors = snapshot.get("datasets") if isinstance(snapshot, dict) else None
        if isinstance(descriptors, list) and any(isinstance(descriptor, dict) and descriptor.get("dataset_version_id") == dataset_id for descriptor in descriptors):
            raise DatasetError("Dataset cache cannot be cleared while an evaluation run references this revision.")
    local_path = dataset.get("local_path")
    if isinstance(local_path, str) and local_path:
        root = (Path(data_root).resolve() / "datasets").resolve()
        target = Path(local_path).resolve()
        if not target.is_relative_to(root):
            raise DatasetError("Dataset cache path is outside the configured dataset root.")
        target.unlink(missing_ok=True)
    clear_prepared_dataset_cache(dataset.get("prepared_path") if isinstance(dataset.get("prepared_path"), str) else None, data_root)
    status = "license_required" if dataset.get("license_text") and dataset.get("license_accepted_at") is None else "not_downloaded"
    updated = store.update_document("dataset_versions", dataset_id, {"local_path": None, "prepared_path": None, "size_bytes": None, "status": status, "error_message": None})
    assert updated is not None
    return updated


def pause_mongo_dataset_download(store: MongoDocumentStore, dataset_id: str) -> dict[str, Any]:
    dataset = _get_dataset(store, dataset_id)
    if dataset.get("status") not in {"downloading", "verifying", "preparing"}:
        raise DatasetError("Only an active dataset download can be paused.")
    updated = store.update_document("dataset_versions", dataset_id, {"status": "waiting", "error_message": None})
    assert updated is not None
    return updated


def validate_mongo_dataset_cache(store: MongoDocumentStore, dataset_id: str, data_root: str) -> dict[str, Any]:
    dataset = _get_dataset(store, dataset_id)
    local_path = dataset.get("local_path")
    root = (Path(data_root).resolve() / "datasets").resolve()
    target = Path(str(local_path)).resolve() if local_path else None
    if target is None or not target.is_relative_to(root) or not target.is_file():
        store.update_document("dataset_versions", dataset_id, {"status": "corrupted", "error_message": "Dataset cache file is missing or outside the configured dataset root."})
        raise DatasetError("Dataset cache file is missing or outside the configured dataset root.")
    store.update_document("dataset_versions", dataset_id, {"status": "verifying", "error_message": None})
    import hashlib
    digest = hashlib.sha256()
    with target.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    checksum = digest.hexdigest()
    if dataset.get("checksum") and str(dataset["checksum"]).lower() != checksum:
        store.update_document("dataset_versions", dataset_id, {"status": "corrupted", "error_message": "Dataset cache checksum verification failed."})
        raise DatasetError("Dataset cache checksum verification failed.")
    prepared_path = dataset.get("prepared_path") if isinstance(dataset.get("prepared_path"), str) else None
    if not validate_prepared_dataset_cache(prepared_path, data_root):
        store.update_document("dataset_versions", dataset_id, {"status": "preparing", "error_message": None})
        prepared_path = str(prepare_dataset_cache(target))
    updated = store.update_document("dataset_versions", dataset_id, {"checksum": checksum, "size_bytes": target.stat().st_size, "prepared_path": prepared_path, "status": "ready", "error_message": None})
    assert updated is not None
    return updated


def mongo_dataset_disk_usage(data_root: str) -> dict[str, int | str]:
    return dataset_disk_usage(data_root)


def _get_dataset(store: MongoDocumentStore, dataset_id: str) -> dict[str, Any]:
    dataset = store.get_document("dataset_versions", dataset_id)
    if dataset is None:
        raise DatasetError("Dataset version not found.")
    return dataset
