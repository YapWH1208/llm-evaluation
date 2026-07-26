from __future__ import annotations
from collections.abc import Generator
from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db.models import DatasetStatus, DatasetVersion
from app.db.mongo import MongoDocumentStore
from app.services.datasets import DatasetError, accept_license, clear_dataset_cache, download_dataset
from app.services.mongo_datasets import accept_mongo_dataset_license, clear_mongo_dataset_cache, download_mongo_dataset

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])
class DatasetCreate(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=128); version: str = Field(min_length=1, max_length=64)
    revision: str = "default"; source_url: str | None = None; checksum: str | None = None; license_text: str | None = None
class DatasetResponse(DatasetCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str; local_path: str | None; license_accepted_at: datetime | None; status: str; error_message: str | None; created_at: datetime
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
    store=get_document_store(request)
    if store is not None:
        if store.list_documents("dataset_versions",query={"dataset_id":payload.dataset_id,"version":payload.version,"revision":payload.revision}):raise HTTPException(409,"Dataset revision already exists")
        return store.insert_document("dataset_versions",{**payload.model_dump(),"local_path":None,"license_accepted_at":None,"status":DatasetStatus.LICENSE_REQUIRED.value if payload.license_text else DatasetStatus.NOT_DOWNLOADED.value,"error_message":None,"created_at":datetime.now()})
    assert session is not None
    item=DatasetVersion(**payload.model_dump(),status=DatasetStatus.LICENSE_REQUIRED.value if payload.license_text else DatasetStatus.NOT_DOWNLOADED.value);session.add(item)
    try: session.commit()
    except IntegrityError as error: session.rollback();raise HTTPException(409,"Dataset revision already exists") from error
    session.refresh(item);return item
@router.get("",response_model=list[DatasetResponse])
def list_datasets(request:Request,session:SessionDependency)->list[DatasetVersion|dict]:
    store=get_document_store(request)
    if store is not None:return store.list_documents("dataset_versions",sort=[("created_at",-1)])
    assert session is not None
    return list(session.scalars(select(DatasetVersion).order_by(DatasetVersion.created_at.desc())))
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
        if store is not None:return download_mongo_dataset(store,dataset_version_id,request.app.state.settings.data_root)
        assert session is not None
        return download_dataset(session,get_dataset_or_404(session,dataset_version_id),request.app.state.settings.data_root)
    except DatasetError as error: raise HTTPException(409,str(error)) from error

@router.delete("/{dataset_version_id}/cache",response_model=DatasetResponse)
def clear_dataset_version_cache(dataset_version_id:str,request:Request,session:SessionDependency)->DatasetVersion|dict:
    store=get_document_store(request)
    try:
        if store is not None:return clear_mongo_dataset_cache(store,dataset_version_id,request.app.state.settings.data_root)
        assert session is not None
        return clear_dataset_cache(session,get_dataset_or_404(session,dataset_version_id),request.app.state.settings.data_root)
    except DatasetError as error: raise HTTPException(409,str(error)) from error
