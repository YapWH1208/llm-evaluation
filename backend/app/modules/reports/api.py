from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.modules.reports.service import ReportService


router = APIRouter(prefix="/api/v1/reports", tags=["reports"])
public_router = APIRouter(prefix="/shared-reports", tags=["shared reports"])


class ReportCreate(BaseModel):
    run_id: str
    format: str = "html"
    report_type: Literal[
        "single_model",
        "multi_model_comparison",
        "regression",
        "prompt_comparison",
        "benchmark",
        "reliability",
        "cost",
        "human_review",
    ] = "single_model"
    related_run_ids: list[str] = Field(default_factory=list, max_length=20)


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    report_type: str
    format: str
    artifact_path: str
    generator_version: str
    generated_at: datetime


class ReportShareCreate(BaseModel):
    expires_at: datetime | None = None
    password: SecretStr | None = None
    allow_download: bool = False
    include_evidence: bool = False


class ReportShareResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    report_id: str
    expires_at: datetime
    allow_download: bool
    revoked_at: datetime | None
    created_at: datetime
    share_url: str | None = None


def get_report_service(request: Request) -> ReportService:
    return request.app.state.report_service


ReportServiceDependency = Annotated[ReportService, Depends(get_report_service)]


@router.post("", response_model=ReportResponse)
def create(payload: ReportCreate, service: ReportServiceDependency) -> Any:
    return service.generate(
        payload.run_id,
        payload.format,
        report_type=payload.report_type,
        related_run_ids=payload.related_run_ids,
    )


@router.get("/run/{run_id}", response_model=list[ReportResponse])
def list_for_run(run_id: str, service: ReportServiceDependency) -> list[Any]:
    return service.list_for_run(run_id)


@router.post("/{report_id}/shares", response_model=ReportShareResponse, status_code=status.HTTP_201_CREATED)
def create_share(
    report_id: str, payload: ReportShareCreate, request: Request, service: ReportServiceDependency
) -> dict[str, Any]:
    return service.create_share(report_id, payload, base_url=_base_url(request))


@router.get("/{report_id}/shares", response_model=list[ReportShareResponse])
def list_shares(report_id: str, request: Request, service: ReportServiceDependency) -> list[dict[str, Any]]:
    return service.list_shares(report_id, base_url=_base_url(request))


@router.post("/{report_id}/shares/{share_id}/revoke", response_model=ReportShareResponse)
def revoke_share(report_id: str, share_id: str, request: Request, service: ReportServiceDependency) -> dict[str, Any]:
    return service.revoke_share(report_id, share_id, base_url=_base_url(request))


@router.get("/{report_id}/download")
def download(report_id: str, service: ReportServiceDependency) -> FileResponse:
    path, media_type, download_file = service.download(report_id)
    return FileResponse(path, filename=path.name if download_file else None, media_type=media_type)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(report_id: str, service: ReportServiceDependency) -> Response:
    service.delete(report_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@public_router.get("/{token}")
def open_shared_report(token: str, request: Request, service: ReportServiceDependency) -> FileResponse:
    path, media_type, download_file = service.open_shared(
        token,
        supplied_password=request.headers.get("X-Report-Password", ""),
        client_host=request.client.host if request.client is not None else "unknown",
    )
    response = FileResponse(path, filename=path.name if download_file else None, media_type=media_type)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "X-Report-Password"
    return response


def _base_url(request: Request) -> str:
    return request.app.state.settings.public_web_url or str(request.base_url).rstrip("/")
