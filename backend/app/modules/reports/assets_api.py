from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from app.modules.reports.assets import AssetService


router = APIRouter(prefix="/api/v1/assets", tags=["media assets"])

PREVIEW_RESPONSE_HEADERS = {
    "Cache-Control": "private, no-store",
    "Content-Security-Policy": "sandbox; default-src 'none'",
    "X-Content-Type-Options": "nosniff",
}


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


def get_asset_service(request: Request) -> AssetService:
    return request.app.state.asset_service


AssetServiceDependency = Annotated[AssetService, Depends(get_asset_service)]


@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def create_asset(payload: AssetCreate, service: AssetServiceDependency) -> Any:
    return service.create(payload)


@router.get("/{asset_id}", response_model=AssetResponse)
def get_asset(asset_id: str, service: AssetServiceDependency) -> Any:
    return service.get(asset_id)


@router.get("/{asset_id}/content-part")
def get_asset_content_part(asset_id: str, service: AssetServiceDependency) -> dict[str, object]:
    return service.content_part(asset_id)


@router.get("/{asset_id}/download")
def download_asset(asset_id: str, service: AssetServiceDependency) -> FileResponse:
    path, mime_type, filename = service.download(asset_id)
    return FileResponse(path, media_type=mime_type, filename=filename, headers=PREVIEW_RESPONSE_HEADERS)
