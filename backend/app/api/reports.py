from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Report, ReportShare
from app.db.mongo import MongoDocumentStore
from app.services.reports import ReportError, generate_report
from app.services.mongo_reports import generate_mongo_report


router = APIRouter(prefix="/api/v1/reports", tags=["reports"])
public_router = APIRouter(prefix="/shared-reports", tags=["shared reports"])


class ReportCreate(BaseModel):
    run_id: str
    format: str = "html"


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


def get_session(request: Request) -> Generator[Session | None, None, None]:
    if getattr(request.app.state,"document_store",None) is not None:
        yield None;return
    session = request.app.state.database.get_session()
    try:
        yield session
    finally:
        session.close()


SessionDependency = Annotated[Session | None, Depends(get_session)]


@router.post("", response_model=ReportResponse)
def create(payload: ReportCreate, request: Request, session: SessionDependency) -> Report | dict:
    store:MongoDocumentStore|None=getattr(request.app.state,"document_store",None)
    try:
        if store is not None:return generate_mongo_report(store,payload.run_id,payload.format,request.app.state.settings.data_root)
        assert session is not None
        return generate_report(session, payload.run_id, payload.format, request.app.state.settings.data_root)
    except ReportError as error:
        raise HTTPException(409, str(error)) from error


@router.get("/run/{run_id}", response_model=list[ReportResponse])
def list_for_run(run_id: str, request: Request, session: SessionDependency) -> list[Report|dict]:
    store:MongoDocumentStore|None=getattr(request.app.state,"document_store",None)
    if store is not None:return store.list_documents("reports",query={"run_id":run_id},sort=[("generated_at",-1)])
    assert session is not None
    return list(session.scalars(select(Report).where(Report.run_id == run_id).order_by(Report.generated_at.desc())))


@router.post("/{report_id}/shares", response_model=ReportShareResponse, status_code=status.HTTP_201_CREATED)
def create_share(report_id: str, payload: ReportShareCreate, request: Request, session: SessionDependency) -> ReportShareResponse:
    report = _get_report(report_id, session)
    if report.format in {"json", "csv"} and not (payload.include_evidence and payload.allow_download):
        raise HTTPException(409, "Raw-evidence JSON/CSV reports require explicit evidence sharing and download permission.")
    now = datetime.now(timezone.utc)
    expires_at = payload.expires_at or now + timedelta(days=7)
    if _as_utc(expires_at) <= now:
        raise HTTPException(422, "Share expiration must be in the future.")
    token = secrets.token_urlsafe(32)
    password = payload.password.get_secret_value() if payload.password is not None else None
    share = ReportShare(
        report_id=report.id,
        token_hash=_hash_value(token),
        password_hash=_hash_value(password) if password else None,
        expires_at=expires_at,
        allow_download=payload.allow_download,
    )
    session.add(share)
    session.commit()
    session.refresh(share)
    return _share_response(share, request, token)


@router.get("/{report_id}/shares", response_model=list[ReportShareResponse])
def list_shares(report_id: str, request: Request, session: SessionDependency) -> list[ReportShareResponse]:
    _get_report(report_id, session)
    return [_share_response(share, request) for share in session.scalars(select(ReportShare).where(ReportShare.report_id == report_id).order_by(ReportShare.created_at.desc()))]


@router.post("/{report_id}/shares/{share_id}/revoke", response_model=ReportShareResponse)
def revoke_share(report_id: str, share_id: str, request: Request, session: SessionDependency) -> ReportShareResponse:
    share = session.get(ReportShare, share_id)
    if share is None or share.report_id != report_id:
        raise HTTPException(404, "Report share not found")
    share.revoked_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(share)
    return _share_response(share, request)


@router.get("/{report_id}/download")
def download(report_id: str, session: SessionDependency) -> FileResponse:
    report = _get_report(report_id, session)
    return _report_file_response(report, download=True)


@public_router.get("/{token}")
def open_shared_report(token: str, request: Request, session: SessionDependency) -> FileResponse:
    share = session.scalar(select(ReportShare).where(ReportShare.token_hash == _hash_value(token)))
    now = datetime.now(timezone.utc)
    if share is None or share.revoked_at is not None or _as_utc(share.expires_at) <= now:
        raise HTTPException(404, "Shared report not found or expired")
    if share.password_hash is not None:
        supplied = request.headers.get("X-Report-Password", "")
        if not hmac.compare_digest(_hash_value(supplied), share.password_hash):
            raise HTTPException(401, "Valid report-share password required")
    report = _get_report(share.report_id, session)
    return _report_file_response(report, download=share.allow_download)


def _get_report(report_id: str, session: Session) -> Report:
    report = session.get(Report, report_id)
    if report is None:
        raise HTTPException(404, "Report not found")
    return report


def _report_file_response(report: Report, *, download: bool) -> FileResponse:
    path = Path(report.artifact_path)
    if not path.is_file():
        raise HTTPException(404, "Report artifact is no longer available")
    media_type = {"json": "application/json", "csv": "text/csv", "html": "text/html", "markdown": "text/markdown", "pdf": "application/pdf"}.get(report.format, "application/octet-stream")
    return FileResponse(path, filename=path.name if download else None, media_type=media_type)


def _share_response(share: ReportShare, request: Request, token: str | None = None) -> ReportShareResponse:
    base_url = str(request.base_url).rstrip("/")
    return ReportShareResponse(
        id=share.id,
        report_id=share.report_id,
        expires_at=share.expires_at,
        allow_download=share.allow_download,
        revoked_at=share.revoked_at,
        created_at=share.created_at,
        share_url=f"{base_url}/shared-reports/{token}" if token else None,
    )


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
