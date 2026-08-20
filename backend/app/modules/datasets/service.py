from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.core.config import DEFAULT_DATASET_DOWNLOAD_MAX_BYTES, Settings
from app.core.errors import ConflictError, NotFoundError
from app.modules.datasets.models import DatasetStatus
from app.modules.datasets.ports import DatasetRepository
from app.modules.datasets.preparation import (
    DatasetDownloadPaused,
    clear_prepared_dataset_cache,
    dataset_disk_usage,
    dataset_edit_lifecycle_updates,
    dataset_source_suffix,
    prepare_dataset_cache,
    preview_dataset_records,
    resolve_dataset_source,
    validate_dataset_field_defaults,
    validate_prepared_dataset_cache,
    write_dataset_source,
)
from app.modules.datasets.records import DatasetRecordError


class DatasetService:
    """Owns dataset registration, preparation, and cache lifecycle behavior."""

    def __init__(self, repository: DatasetRepository) -> None:
        self.repository = repository

    def list(self) -> list[dict[str, Any]]:
        return self.repository.list()

    def create(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        values = dict(payload)
        values["status"] = (
            DatasetStatus.LICENSE_REQUIRED.value if values.get("license_text") else DatasetStatus.NOT_DOWNLOADED.value
        )
        values.update(
            {
                "local_path": None,
                "prepared_path": None,
                "size_bytes": None,
                "license_accepted_at": None,
                "error_message": None,
            }
        )
        try:
            return self.repository.create(values)
        except ValueError as error:
            raise ConflictError(str(error)) from error

    def get(self, dataset_version_id: str) -> dict[str, Any]:
        dataset = self.repository.get(dataset_version_id)
        if dataset is None:
            raise NotFoundError("Dataset version not found", context={"dataset_version_id": dataset_version_id})
        return dataset

    def disk_usage(self, data_root: str) -> dict[str, int | str]:
        return dataset_disk_usage(data_root)

    def prepare(self, descriptor: Mapping[str, Any], data_root: str, settings: Settings) -> dict[str, Any]:
        frozen_id = descriptor.get("dataset_version_id")
        if isinstance(frozen_id, str):
            dataset = self.repository.get(frozen_id)
        else:
            dataset_id = descriptor.get("dataset_id")
            dataset = (
                self.repository.find(
                    dataset_id=dataset_id,
                    version=descriptor.get("version") if isinstance(descriptor.get("version"), str) else None,
                    revision=descriptor.get("revision") if isinstance(descriptor.get("revision"), str) else None,
                )
                if isinstance(dataset_id, str)
                else None
            )
        if dataset is None:
            raise NotFoundError(
                f"Required dataset {descriptor.get('dataset_id', frozen_id)} is not registered.",
                context={"dataset_version_id": frozen_id, "dataset_id": descriptor.get("dataset_id")},
            )
        if dataset.get("status") == DatasetStatus.READY.value:
            return dataset
        return self.download(str(dataset["id"]), data_root, settings)

    def preview(self, dataset_version_id: str, data_root: str, *, limit: int) -> dict[str, object]:
        dataset = self.get(dataset_version_id)
        prepared_path = dataset.get("prepared_path")
        if dataset.get("status") != DatasetStatus.READY.value or not isinstance(prepared_path, str):
            raise ConflictError("Dataset is not ready; download and verify it before previewing.")
        try:
            return preview_dataset_records(prepared_path, data_root, limit=limit)
        except DatasetRecordError as error:
            raise ConflictError(f"Dataset preview is unavailable: {error}") from error

    def update(self, dataset_version_id: str, payload: Mapping[str, Any], *, data_root: str) -> dict[str, Any]:
        current = self.get(dataset_version_id)
        values = {
            key: payload.get(key)
            for key in (
                "dataset_id",
                "version",
                "revision",
                "source_url",
                "checksum",
                "license_text",
                "credential_binding_id",
                "input_field",
                "reference_field",
                "capabilities",
                "languages",
                "evaluation_type",
            )
        }
        validate_dataset_field_defaults(
            current.get("prepared_path") if isinstance(current.get("prepared_path"), str) else None,
            data_root,
            input_field=values["input_field"] if isinstance(values["input_field"], str) else None,
            reference_field=values["reference_field"] if isinstance(values["reference_field"], str) else None,
        )
        values.update(dataset_edit_lifecycle_updates(current, values))
        try:
            updated = self.repository.update(dataset_version_id, values)
        except ValueError as error:
            raise ConflictError(str(error)) from error
        if updated is None:
            raise NotFoundError("Dataset version not found", context={"dataset_version_id": dataset_version_id})
        return updated

    def accept_license(self, dataset_version_id: str) -> dict[str, Any]:
        dataset = self.get(dataset_version_id)
        values: dict[str, Any] = {"license_accepted_at": datetime.now(timezone.utc)}
        if dataset.get("status") == DatasetStatus.LICENSE_REQUIRED.value:
            values["status"] = DatasetStatus.NOT_DOWNLOADED.value
        updated = self.repository.update(dataset_version_id, values)
        assert updated is not None
        return updated

    def set_credential_binding(self, dataset_version_id: str, binding_id: str | None) -> dict[str, Any]:
        dataset = self.get(dataset_version_id)
        values: dict[str, Any] = {"credential_binding_id": binding_id}
        if dataset.get("status") == DatasetStatus.CREDENTIAL_REQUIRED.value:
            values.update({"status": DatasetStatus.NOT_DOWNLOADED.value, "error_message": None})
        updated = self.repository.update(dataset_version_id, values)
        assert updated is not None
        return updated

    def download(self, dataset_version_id: str, data_root: str, settings: Settings | None = None) -> dict[str, Any]:
        dataset = self.get(dataset_version_id)
        source_url = dataset.get("source_url")
        if not isinstance(source_url, str) or not source_url:
            raise ConflictError("Dataset has no downloadable source URL.")
        if dataset.get("license_text") and dataset.get("license_accepted_at") is None:
            self.repository.update(dataset_version_id, {"status": DatasetStatus.LICENSE_REQUIRED.value})
            raise ConflictError("Dataset license must be accepted before download.")
        destination = (
            Path(data_root).resolve()
            / "datasets"
            / str(dataset["dataset_id"])
            / str(dataset["version"])
            / str(dataset["revision"])
        )
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / f"dataset{dataset_source_suffix(source_url)}"
        temporary = destination / "dataset.part"
        self.repository.update(dataset_version_id, {"status": DatasetStatus.DOWNLOADING.value, "error_message": None})

        try:
            source, headers = resolve_dataset_source(
                source_url, str(dataset["revision"]), dataset.get("credential_binding_id"), settings
            )

            def ensure_not_paused() -> None:
                current = self.get(dataset_version_id)
                if current.get("status") == DatasetStatus.WAITING.value:
                    raise DatasetDownloadPaused("Dataset download was paused and can be retried.")

            checksum = write_dataset_source(
                source,
                temporary,
                headers,
                ensure_not_paused,
                max_bytes=settings.dataset_download_max_bytes
                if settings is not None
                else DEFAULT_DATASET_DOWNLOAD_MAX_BYTES,
                allowed_hosts=settings.dataset_allowed_hosts if settings is not None else (),
            )
            self.repository.update(dataset_version_id, {"status": DatasetStatus.VERIFYING.value})
            expected = dataset.get("checksum")
            if isinstance(expected, str) and expected.lower() != checksum:
                temporary.unlink(missing_ok=True)
                raise ConflictError("Dataset checksum verification failed.")
            temporary.replace(target)
            self.repository.update(dataset_version_id, {"status": DatasetStatus.PREPARING.value})
            prepared_path = prepare_dataset_cache(target)
            updated = self.repository.update(
                dataset_version_id,
                {
                    "checksum": checksum,
                    "size_bytes": target.stat().st_size,
                    "local_path": str(target),
                    "prepared_path": str(prepared_path),
                    "status": DatasetStatus.READY.value,
                    "error_message": None,
                },
            )
            assert updated is not None
            return updated
        except DatasetDownloadPaused as error:
            self.repository.update(dataset_version_id, {"status": DatasetStatus.WAITING.value, "error_message": None})
            raise ConflictError(str(error)) from error
        except (httpx.HTTPStatusError, ConflictError) as error:
            status_code = getattr(getattr(error, "response", None), "status_code", 0)
            credential_required = bool(dataset.get("credential_binding_id")) and (
                (isinstance(error, ConflictError) and error.context.get("reason") == "credential")
                or status_code in {401, 403}
            )
            self.repository.update(
                dataset_version_id,
                {
                    "status": DatasetStatus.CREDENTIAL_REQUIRED.value
                    if credential_required
                    else DatasetStatus.FAILED.value,
                    "error_message": str(error)[:500],
                },
            )
            raise ConflictError(str(error)) from error
        except (httpx.HTTPError, OSError) as error:
            self.repository.update(
                dataset_version_id, {"status": DatasetStatus.FAILED.value, "error_message": str(error)[:500]}
            )
            raise ConflictError(str(error)) from error

    def pause(self, dataset_version_id: str) -> dict[str, Any]:
        dataset = self.get(dataset_version_id)
        if dataset.get("status") not in {
            DatasetStatus.DOWNLOADING.value,
            DatasetStatus.VERIFYING.value,
            DatasetStatus.PREPARING.value,
        }:
            raise ConflictError("Only an active dataset download can be paused.")
        updated = self.repository.update(
            dataset_version_id, {"status": DatasetStatus.WAITING.value, "error_message": None}
        )
        assert updated is not None
        return updated

    def validate(self, dataset_version_id: str, data_root: str) -> dict[str, Any]:
        dataset = self.get(dataset_version_id)
        local_path = dataset.get("local_path")
        if not isinstance(local_path, str) or not local_path:
            raise ConflictError("Dataset has no cached file to validate.")
        root = (Path(data_root).resolve() / "datasets").resolve()
        target = Path(local_path).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            self.repository.update(
                dataset_version_id,
                {
                    "status": DatasetStatus.CORRUPTED.value,
                    "error_message": "Dataset cache file is missing or outside the configured dataset root.",
                },
            )
            raise ConflictError("Dataset cache file is missing or outside the configured dataset root.")
        self.repository.update(dataset_version_id, {"status": DatasetStatus.VERIFYING.value, "error_message": None})
        digest = hashlib.sha256()
        with target.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        checksum = digest.hexdigest()
        if dataset.get("checksum") and checksum != str(dataset["checksum"]).lower():
            self.repository.update(
                dataset_version_id,
                {
                    "status": DatasetStatus.CORRUPTED.value,
                    "error_message": "Dataset cache checksum verification failed.",
                },
            )
            raise ConflictError("Dataset cache checksum verification failed.")
        prepared_path = dataset.get("prepared_path") if isinstance(dataset.get("prepared_path"), str) else None
        if not validate_prepared_dataset_cache(prepared_path, data_root):
            self.repository.update(dataset_version_id, {"status": DatasetStatus.PREPARING.value})
            prepared_path = str(prepare_dataset_cache(target))
        updated = self.repository.update(
            dataset_version_id,
            {
                "checksum": checksum,
                "size_bytes": target.stat().st_size,
                "prepared_path": prepared_path,
                "status": DatasetStatus.READY.value,
                "error_message": None,
            },
        )
        assert updated is not None
        return updated

    def clear_cache(self, dataset_version_id: str, data_root: str) -> dict[str, Any]:
        dataset = self.get(dataset_version_id)
        self._ensure_not_referenced(dataset_version_id)
        self._remove_files(dataset, data_root)
        status = (
            DatasetStatus.LICENSE_REQUIRED.value
            if dataset.get("license_text") and dataset.get("license_accepted_at") is None
            else DatasetStatus.NOT_DOWNLOADED.value
        )
        updated = self.repository.update(
            dataset_version_id,
            {"local_path": None, "prepared_path": None, "size_bytes": None, "status": status, "error_message": None},
        )
        assert updated is not None
        return updated

    def delete(self, dataset_version_id: str, data_root: str) -> dict[str, Any]:
        dataset = self.get(dataset_version_id)
        self._ensure_not_referenced(dataset_version_id)
        if dataset.get("status") in {
            DatasetStatus.DOWNLOADING.value,
            DatasetStatus.PREPARING.value,
            DatasetStatus.VERIFYING.value,
            DatasetStatus.REMOVING.value,
        }:
            raise ConflictError("Dataset cannot be deleted while it is downloading or preparing.")
        self._remove_files(dataset, data_root)
        deleted = self.repository.delete(dataset_version_id)
        assert deleted is not None
        return deleted

    def upload(self, dataset_version_id: str, *, filename: str, content: bytes, data_root: str) -> dict[str, Any]:
        dataset = self.get(dataset_version_id)
        if not content:
            raise ConflictError("Uploaded dataset is empty.")
        if len(content) > 64 * 1024 * 1024:
            raise ConflictError("Uploaded dataset exceeds the 64 MiB upload limit.")
        safe_name = Path(filename).name
        if not safe_name or safe_name in {".", ".."}:
            raise ConflictError("Uploaded dataset filename is invalid.")
        if Path(safe_name).suffix.lower() not in {".json", ".jsonl", ".csv", ".tsv", ".txt", ".zip", ".parquet"}:
            raise ConflictError("Uploaded dataset file type is not supported.")
        if dataset.get("license_text") and dataset.get("license_accepted_at") is None:
            self.repository.update(dataset_version_id, {"status": DatasetStatus.LICENSE_REQUIRED.value})
            raise ConflictError("Dataset license must be accepted before upload.")
        destination = (Path(data_root).resolve() / "datasets" / "uploads" / dataset_version_id).resolve()
        root = (Path(data_root).resolve() / "datasets").resolve()
        if not destination.is_relative_to(root):
            raise ConflictError("Dataset upload path is outside the configured dataset root.")
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / safe_name
        checksum = hashlib.sha256(content).hexdigest()
        expected = dataset.get("checksum")
        if isinstance(expected, str) and expected.lower() != checksum:
            self.repository.update(
                dataset_version_id,
                {
                    "status": DatasetStatus.CORRUPTED.value,
                    "error_message": "Uploaded dataset checksum verification failed.",
                },
            )
            raise ConflictError("Uploaded dataset checksum verification failed.")
        temporary = destination / f".{safe_name}.part"
        temporary.write_bytes(content)
        temporary.replace(target)
        self.repository.update(dataset_version_id, {"status": DatasetStatus.PREPARING.value})
        prepared_path = prepare_dataset_cache(target)
        updated = self.repository.update(
            dataset_version_id,
            {
                "source_url": target.as_uri(),
                "checksum": checksum,
                "size_bytes": len(content),
                "local_path": str(target),
                "prepared_path": str(prepared_path),
                "status": DatasetStatus.READY.value,
                "error_message": None,
            },
        )
        assert updated is not None
        return updated

    def _ensure_not_referenced(self, dataset_version_id: str) -> None:
        if self.repository.is_referenced(dataset_version_id):
            raise ConflictError(
                "Dataset cannot be cleared or deleted while an evaluation run references this revision."
            )

    @staticmethod
    def _remove_files(dataset: Mapping[str, Any], data_root: str) -> None:
        local_path = dataset.get("local_path")
        if isinstance(local_path, str) and local_path:
            root = (Path(data_root).resolve() / "datasets").resolve()
            target = Path(local_path).resolve()
            if not target.is_relative_to(root):
                raise ConflictError("Dataset cache path is outside the configured dataset root.")
            target.unlink(missing_ok=True)
        clear_prepared_dataset_cache(
            dataset.get("prepared_path") if isinstance(dataset.get("prepared_path"), str) else None, data_root
        )
        upload_dir = (Path(data_root).resolve() / "datasets" / "uploads" / str(dataset.get("id"))).resolve()
        if upload_dir.is_relative_to((Path(data_root).resolve() / "datasets").resolve()):
            import shutil

            shutil.rmtree(upload_dir, ignore_errors=True)


__all__ = [
    "DatasetService",
    "DatasetDownloadPaused",
    "resolve_dataset_source",
    "write_dataset_source",
    "prepare_dataset_cache",
    "dataset_edit_lifecycle_updates",
]
