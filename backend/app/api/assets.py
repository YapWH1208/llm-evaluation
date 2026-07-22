from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MediaAsset
from app.services.content_ir import asset_content_part
from app.services.media_assets import (
    MediaAssetError,
    decode_and_validate_asset,
    safe_asset_path,
    safe_filename,
    store_asset,
)


router = APIRouter(prefix="/api/v1/assets", tags=["media assets"])


class AssetCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=1024)
    mime_type: str = Field(min_length=3, max_length=128)
    base64_data: str = Field(min_length=1)


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    media_kind: str
    mime_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


def get_session(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.database.get_session()
    try:
        yield session
    finally:
        session.close()


SessionDependency = Annotated[Session, Depends(get_session)]


def get_asset_or_404(session: Session, asset_id: str) -> MediaAsset:
    asset = session.get(MediaAsset, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Media asset not found")
    return asset


@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def create_asset(payload: AssetCreate, request: Request, session: SessionDependency) -> MediaAsset:
    try:
        data, mime_type, media_kind = decode_and_validate_asset(payload.base64_data, payload.mime_type)
        sha256, storage_path = store_asset(request.app.state.settings.data_root, data)
    except MediaAssetError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    existing = session.scalar(select(MediaAsset).where(MediaAsset.sha256 == sha256))
    if existing is not None:
        return existing
    asset = MediaAsset(
        original_filename=safe_filename(payload.filename),
        media_kind=media_kind,
        mime_type=mime_type,
        size_bytes=len(data),
        sha256=sha256,
        storage_path=storage_path,
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


@router.get("/{asset_id}", response_model=AssetResponse)
def get_asset(asset_id: str, session: SessionDependency) -> MediaAsset:
    return get_asset_or_404(session, asset_id)


@router.get("/{asset_id}/content-part")
def get_asset_content_part(asset_id: str, session: SessionDependency) -> dict[str, object]:
    asset = get_asset_or_404(session, asset_id)
    return asset_content_part(asset.id, asset.media_kind, asset.mime_type)


@router.get("/{asset_id}/download")
def download_asset(asset_id: str, request: Request, session: SessionDependency) -> FileResponse:
    asset = get_asset_or_404(session, asset_id)
    try:
        path = safe_asset_path(request.app.state.settings.data_root, asset.storage_path)
    except MediaAssetError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    return FileResponse(path, media_type=asset.mime_type, filename=asset.original_filename)
