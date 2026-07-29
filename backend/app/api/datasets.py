from __future__ import annotations
import base64
import binascii
from collections.abc import Generator
from datetime import datetime
from typing import Annotated
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db.models import DatasetStatus, DatasetVersion
from app.db.mongo import MongoDocumentStore
from app.services.datasets import DatasetError, accept_license, clear_dataset_cache, dataset_disk_usage, download_dataset, pause_dataset_download, store_uploaded_dataset, validate_dataset_cache
from app.services.mongo_datasets import accept_mongo_dataset_license, clear_mongo_dataset_cache, download_mongo_dataset, mongo_dataset_disk_usage, pause_mongo_dataset_download, store_mongo_uploaded_dataset, validate_mongo_dataset_cache

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])
class DatasetCreate(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=128); version: str = Field(min_length=1, max_length=64)
    revision: str = "default"; source_url: str | None = None; checksum: str | None = None; license_text: str | None = None
    credential_binding_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")
    credential_env_var: str | None = None

    @model_validator(mode="after")
    def reject_legacy_credential_environment_variable(self) -> "DatasetCreate":
        if self.credential_env_var is not None:
            raise ValueError(
                "credential_env_var is no longer accepted. Configure an administrator-owned "
                "credential_binding_id instead."
            )
        return self


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; dataset_id: str; version: str; revision: str; source_url: str | None; credential_binding_id: str | None
    checksum: str | None; local_path: str | None; prepared_path: str | None = None; size_bytes: int | None = None; license_text: str | None
    license_accepted_at: datetime | None; status: str; error_message: str | None; created_at: datetime


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
                "credential_env_var is no longer accepted. Configure an administrator-owned "
                "credential_binding_id instead."
            )
        return self


class DatasetDiskUsage(BaseModel):
    root: str
    cache_bytes: int
    available_bytes: int
    total_bytes: int
def get_session(request: Request) -> Generator[Session | None, None, None]:
    if getattr(request.app.state,"document_store",None) is not None:
        yield None
        return
    session=request.app.state.database.get_session()
    try: yield session
    finally: session.close()
SessionDependency=Annotated[Session|None,Depends(get_session)]
def get_document_store(request:Request)->MongoDocumentStore|None:return getattr(request.app.state,"document_store",None)
def get_dataset_or_404(session: Session, dataset_id: str) -> DatasetVersion:
    item=session.get(DatasetVersion,dataset_id)
    if item is None: raise HTTPException(404,"Dataset version not found")
    return item
@router.post("",response_model=DatasetResponse,status_code=status.HTTP_201_CREATED)
def create_dataset(payload: DatasetCreate,request:Request,session:SessionDependency)->DatasetVersion|dict:
    _validate_dataset_registration(payload, request)
    store=get_document_store(request)
    if store is not None:
        if store.list_documents("dataset_versions",query={"dataset_id":payload.dataset_id,"version":payload.version,"revision":payload.revision}):raise HTTPException(409,"Dataset revision already exists")
        return store.insert_document("dataset_versions",{**payload.model_dump(exclude={"credential_env_var"}),"local_path":None,"prepared_path":None,"size_bytes":None,"license_accepted_at":None,"status":DatasetStatus.LICENSE_REQUIRED.value if payload.license_text else DatasetStatus.NOT_DOWNLOADED.value,"error_message":None,"created_at":datetime.now()})
    assert session is not None
    item=DatasetVersion(**payload.model_dump(exclude={"credential_env_var"}),status=DatasetStatus.LICENSE_REQUIRED.value if payload.license_text else DatasetStatus.NOT_DOWNLOADED.value);session.add(item)
    try: session.commit()
    except IntegrityError as error: session.rollback();raise HTTPException(409,"Dataset revision already exists") from error
    session.refresh(item);return item
@router.get("",response_model=list[DatasetResponse])
def list_datasets(request:Request,session:SessionDependency)->list[DatasetVersion|dict]:
    store=get_document_store(request)
    if store is not None:return store.list_documents("dataset_versions",sort=[("created_at",-1)])
    assert session is not None
    return list(session.scalars(select(DatasetVersion).order_by(DatasetVersion.created_at.desc())))


@router.get("/disk-usage", response_model=DatasetDiskUsage)
def get_dataset_disk_usage(request: Request) -> dict[str, int | str]:
    return mongo_dataset_disk_usage(request.app.state.settings.data_root) if get_document_store(request) is not None else dataset_disk_usage(request.app.state.settings.data_root)
@router.post("/{dataset_version_id}/accept-license",response_model=DatasetResponse)
def accept_dataset_license(dataset_version_id:str,request:Request,session:SessionDependency)->DatasetVersion|dict:
    store=get_document_store(request)
    if store is not None:
        try:return accept_mongo_dataset_license(store,dataset_version_id)
        except DatasetError as error:raise HTTPException(404,str(error)) from error
    assert session is not None
    return accept_license(session,get_dataset_or_404(session,dataset_version_id))
@router.post("/{dataset_version_id}/download",response_model=DatasetResponse)
def download_dataset_version(dataset_version_id:str,request:Request,session:SessionDependency)->DatasetVersion|dict:
    store=get_document_store(request)
    try:
        if store is not None:return download_mongo_dataset(store,dataset_version_id,request.app.state.settings.data_root,request.app.state.settings)
        assert session is not None
        return download_dataset(session,get_dataset_or_404(session,dataset_version_id),request.app.state.settings.data_root,request.app.state.settings)
    except DatasetError as error: raise HTTPException(409,str(error)) from error


@router.post("/{dataset_version_id}/retry", response_model=DatasetResponse)
def retry_dataset_download(dataset_version_id: str, request: Request, session: SessionDependency) -> DatasetVersion | dict:
    return download_dataset_version(dataset_version_id, request, session)


@router.post("/{dataset_version_id}/pause", response_model=DatasetResponse)
def pause_dataset(dataset_version_id: str, request: Request, session: SessionDependency) -> DatasetVersion | dict:
    try:
        store = get_document_store(request)
        if store is not None:
            return pause_mongo_dataset_download(store, dataset_version_id)
        assert session is not None
        return pause_dataset_download(session, get_dataset_or_404(session, dataset_version_id))
    except DatasetError as error:
        raise HTTPException(409, str(error)) from error


@router.post("/{dataset_version_id}/validate", response_model=DatasetResponse)
def validate_dataset(dataset_version_id: str, request: Request, session: SessionDependency) -> DatasetVersion | dict:
    try:
        store = get_document_store(request)
        if store is not None:
            return validate_mongo_dataset_cache(store, dataset_version_id, request.app.state.settings.data_root)
        assert session is not None
        return validate_dataset_cache(session, get_dataset_or_404(session, dataset_version_id), request.app.state.settings.data_root)
    except DatasetError as error:
        raise HTTPException(409, str(error)) from error


@router.put("/{dataset_version_id}/credential-reference", response_model=DatasetResponse)
def set_dataset_credential_reference(dataset_version_id: str, payload: DatasetCredentialReference, request: Request, session: SessionDependency) -> DatasetVersion | dict:
    _validate_credential_binding(payload.credential_binding_id, request)
    store = get_document_store(request)
    if store is not None:
        if store.get_document("dataset_versions", dataset_version_id) is None:
            raise HTTPException(404, "Dataset version not found")
        updated = store.update_document("dataset_versions", dataset_version_id, {"credential_binding_id": payload.credential_binding_id})
        assert updated is not None
        return updated
    assert session is not None
    dataset = get_dataset_or_404(session, dataset_version_id)
    dataset.credential_binding_id = payload.credential_binding_id
    if dataset.status == DatasetStatus.CREDENTIAL_REQUIRED.value:
        dataset.status = DatasetStatus.NOT_DOWNLOADED.value
        dataset.error_message = None
    session.commit()
    session.refresh(dataset)
    return dataset


@router.post("/{dataset_version_id}/upload", response_model=DatasetResponse)
def upload_dataset_version(dataset_version_id: str, payload: DatasetUpload, request: Request, session: SessionDependency) -> DatasetVersion | dict:
    try:
        content = _decode_upload(payload.base64_data)
        store = get_document_store(request)
        if store is not None:
            return store_mongo_uploaded_dataset(store, dataset_version_id, filename=payload.filename, content=content, data_root=request.app.state.settings.data_root)
        assert session is not None
        return store_uploaded_dataset(session, get_dataset_or_404(session, dataset_version_id), filename=payload.filename, content=content, data_root=request.app.state.settings.data_root)
    except DatasetError as error:
        raise HTTPException(409, str(error)) from error

@router.delete("/{dataset_version_id}/cache",response_model=DatasetResponse)
def clear_dataset_version_cache(dataset_version_id:str,request:Request,session:SessionDependency)->DatasetVersion|dict:
    store=get_document_store(request)
    try:
        if store is not None:return clear_mongo_dataset_cache(store,dataset_version_id,request.app.state.settings.data_root)
        assert session is not None
        return clear_dataset_cache(session,get_dataset_or_404(session,dataset_version_id),request.app.state.settings.data_root)
    except DatasetError as error: raise HTTPException(409,str(error)) from error


def _decode_upload(value: str) -> bytes:
    encoded = value.split(",", 1)[1] if value.startswith("data:") and "," in value else value
    try:
        return base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise DatasetError("Uploaded dataset must be valid base64 data.") from error


def _validate_dataset_registration(payload: DatasetCreate, request: Request) -> None:
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
            f"Dataset credential binding {binding_id!r} is not configured. "
            "Ask an administrator to configure LLE_DATASET_CREDENTIAL_BINDINGS_JSON.",
        )
