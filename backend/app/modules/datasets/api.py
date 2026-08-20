from __future__ import annotations

import base64
import binascii
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.errors import ConflictError
from app.modules.datasets.metadata import (
    DatasetMetadataError,
    normalize_capabilities,
    normalize_evaluation_type,
    normalize_languages,
)
from app.modules.datasets.service import DatasetService

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


class DatasetCreate(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    revision: str = "main"
    source_url: str | None = None
    checksum: str | None = None
    license_text: str | None = None
    input_field: str | None = None
    reference_field: str | None = None
    capabilities: list[str] = Field(default_factory=list, max_length=32)
    languages: list[str] = Field(default_factory=list, max_length=32)
    evaluation_type: str = "custom"
    credential_binding_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")
    credential_env_var: str | None = None

    @model_validator(mode="after")
    def normalize(self) -> "DatasetCreate":
        if self.credential_env_var is not None:
            raise ValueError(
                "credential_env_var is no longer accepted. Configure an administrator-owned credential_binding_id instead."
            )
        if self.input_field is not None and not self.input_field.strip():
            raise ValueError("input_field must not be blank when provided.")
        if self.reference_field is not None and not self.reference_field.strip():
            raise ValueError("reference_field must not be blank when provided.")
        if self.input_field is not None:
            self.input_field = self.input_field.strip()
        if self.reference_field is not None:
            self.reference_field = self.reference_field.strip()
        if self.input_field is not None and self.input_field == self.reference_field:
            raise ValueError("Input and reference fields must name different dataset columns.")
        try:
            self.capabilities = normalize_capabilities(self.capabilities)
            self.languages = normalize_languages(self.languages)
            self.evaluation_type = normalize_evaluation_type(self.evaluation_type)
        except DatasetMetadataError as error:
            raise ValueError(str(error)) from error
        return self


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    dataset_id: str
    version: str
    revision: str
    source_url: str | None
    credential_binding_id: str | None
    checksum: str | None
    local_path: str | None
    prepared_path: str | None = None
    size_bytes: int | None = None
    license_text: str | None
    license_accepted_at: datetime | None
    input_field: str | None = None
    reference_field: str | None = None
    status: str
    error_message: str | None
    created_at: datetime
    capabilities: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    evaluation_type: str = "custom"


class DatasetUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    base64_data: str = Field(min_length=1, max_length=89_478_488)


class DatasetCredentialReference(BaseModel):
    credential_binding_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")
    credential_env_var: str | None = None

    @model_validator(mode="after")
    def reject_legacy_credential_environment_variable(self) -> "DatasetCredentialReference":
        if self.credential_env_var is not None:
            raise ValueError(
                "credential_env_var is no longer accepted. Configure an administrator-owned credential_binding_id instead."
            )
        return self


class DatasetDiskUsage(BaseModel):
    root: str
    cache_bytes: int
    available_bytes: int
    total_bytes: int


class DatasetPreviewResponse(BaseModel):
    fields: list[str]
    rows: list[dict[str, str]]


def _service(request: Request) -> DatasetService:
    return request.app.state.dataset_service


def _validate_registration(payload: DatasetCreate, request: Request) -> None:
    _validate_credential_binding(payload.credential_binding_id, request)
    if payload.source_url is None:
        return
    parsed = urlparse(payload.source_url)
    if parsed.scheme == "https" and parsed.netloc:
        return
    if parsed.scheme == "hf" and parsed.netloc and len([part for part in parsed.path.split("/") if part]) >= 2:
        return
    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "Dataset source_url must be HTTPS or hf://owner/repository/path. Use the upload endpoint for local files.",
    )


def _validate_credential_binding(binding_id: str | None, request: Request) -> None:
    if binding_id is not None and binding_id not in request.app.state.settings.dataset_credential_bindings:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Dataset credential binding {binding_id!r} is not configured. Ask an administrator to configure LLE_DATASET_CREDENTIAL_BINDINGS_JSON.",
        )


def _decode_upload(value: str) -> bytes:
    encoded = value.split(",", 1)[1] if value.startswith("data:") and "," in value else value
    try:
        return base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ConflictError("Uploaded dataset must be valid base64 data.") from error


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
def create_dataset(payload: DatasetCreate, request: Request) -> dict[str, Any]:
    _validate_registration(payload, request)
    return _service(request).create(payload.model_dump(exclude={"credential_env_var"}))


@router.get("", response_model=list[DatasetResponse])
def list_datasets(request: Request) -> list[dict[str, Any]]:
    return _service(request).list()


@router.get("/disk-usage", response_model=DatasetDiskUsage)
def get_dataset_disk_usage(request: Request) -> dict[str, int | str]:
    return _service(request).disk_usage(request.app.state.settings.data_root)


@router.get("/{dataset_version_id}/preview", response_model=DatasetPreviewResponse)
def preview_dataset_version(
    dataset_version_id: str, request: Request, limit: int = Query(default=5, ge=1, le=50)
) -> dict[str, object]:
    return _service(request).preview(dataset_version_id, request.app.state.settings.data_root, limit=limit)


@router.put("/{dataset_version_id}", response_model=DatasetResponse)
def update_dataset_version(dataset_version_id: str, payload: DatasetCreate, request: Request) -> dict[str, Any]:
    _validate_registration(payload, request)
    return _service(request).update(
        dataset_version_id,
        payload.model_dump(exclude={"credential_env_var"}),
        data_root=request.app.state.settings.data_root,
    )


@router.post("/{dataset_version_id}/accept-license", response_model=DatasetResponse)
def accept_dataset_license(dataset_version_id: str, request: Request) -> dict[str, Any]:
    return _service(request).accept_license(dataset_version_id)


@router.post("/{dataset_version_id}/download", response_model=DatasetResponse)
def download_dataset_version(dataset_version_id: str, request: Request) -> dict[str, Any]:
    return _service(request).download(
        dataset_version_id, request.app.state.settings.data_root, request.app.state.settings
    )


@router.post("/{dataset_version_id}/retry", response_model=DatasetResponse)
def retry_dataset_download(dataset_version_id: str, request: Request) -> dict[str, Any]:
    return download_dataset_version(dataset_version_id, request)


@router.post("/{dataset_version_id}/pause", response_model=DatasetResponse)
def pause_dataset(dataset_version_id: str, request: Request) -> dict[str, Any]:
    return _service(request).pause(dataset_version_id)


@router.post("/{dataset_version_id}/validate", response_model=DatasetResponse)
def validate_dataset(dataset_version_id: str, request: Request) -> dict[str, Any]:
    return _service(request).validate(dataset_version_id, request.app.state.settings.data_root)


@router.put("/{dataset_version_id}/credential-reference", response_model=DatasetResponse)
def set_dataset_credential_reference(
    dataset_version_id: str, payload: DatasetCredentialReference, request: Request
) -> dict[str, Any]:
    _validate_credential_binding(payload.credential_binding_id, request)
    return _service(request).set_credential_binding(dataset_version_id, payload.credential_binding_id)


@router.post("/{dataset_version_id}/upload", response_model=DatasetResponse)
def upload_dataset_version(dataset_version_id: str, payload: DatasetUpload, request: Request) -> dict[str, Any]:
    return _service(request).upload(
        dataset_version_id,
        filename=payload.filename,
        content=_decode_upload(payload.base64_data),
        data_root=request.app.state.settings.data_root,
    )


@router.delete("/{dataset_version_id}/cache", response_model=DatasetResponse)
def clear_dataset_version_cache(dataset_version_id: str, request: Request) -> dict[str, Any]:
    return _service(request).clear_cache(dataset_version_id, request.app.state.settings.data_root)


@router.delete("/{dataset_version_id}", response_model=DatasetResponse)
def delete_dataset_version(dataset_version_id: str, request: Request) -> dict[str, Any]:
    return _service(request).delete(dataset_version_id, request.app.state.settings.data_root)
