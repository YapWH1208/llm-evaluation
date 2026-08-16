from __future__ import annotations

import hashlib
import hmac
import base64
import secrets
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Report, ReportShare, ReportSharePasswordAttempt
from app.db.mongo import MongoDocumentStore
from app.services.reports import ReportError, delete_report_artifact, generate_report
from app.services.mongo_reports import generate_mongo_report


router = APIRouter(prefix="/api/v1/reports", tags=["reports"])
public_router = APIRouter(prefix="/shared-reports", tags=["shared reports"])
_PASSWORD_WINDOW = timedelta(minutes=5)
_PASSWORD_ATTEMPT_LIMIT = 5


class ReportCreate(BaseModel):
    run_id: str
    format: str = "html"
    report_type: Literal["single_model", "multi_model_comparison", "regression", "prompt_comparison", "benchmark", "reliability", "cost", "human_review"] = "single_model"
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
        if store is not None:return generate_mongo_report(store,payload.run_id,payload.format,request.app.state.settings.data_root,report_type=payload.report_type,related_run_ids=payload.related_run_ids)
        assert session is not None
        return generate_report(session, payload.run_id, payload.format, request.app.state.settings.data_root, report_type=payload.report_type, related_run_ids=payload.related_run_ids)
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
    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        report = store.get_document("reports", report_id)
        if report is None: raise HTTPException(404, "Report not found")
        if report["format"] in {"json", "csv"} and not (payload.include_evidence and payload.allow_download): raise HTTPException(409, "Raw-evidence JSON/CSV reports require explicit evidence sharing and download permission.")
        now = datetime.now(timezone.utc); expires_at = payload.expires_at or now + timedelta(days=7)
        if _as_utc(expires_at) <= now: raise HTTPException(422, "Share expiration must be in the future.")
        token = secrets.token_urlsafe(32); password = payload.password.get_secret_value() if payload.password is not None else None
        share = store.insert_document("report_shares", {"report_id": report_id, "token_hash": _hash_value(token), "password_hash": _hash_password(password) if password else None, "expires_at": expires_at, "allow_download": payload.allow_download, "revoked_at": None, "created_at": now})
        return _share_document_response(share, request, token)
    assert session is not None
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
        password_hash=_hash_password(password) if password else None,
        expires_at=expires_at,
        allow_download=payload.allow_download,
    )
    session.add(share)
    session.commit()
    session.refresh(share)
    return _share_response(share, request, token)


@router.get("/{report_id}/shares", response_model=list[ReportShareResponse])
def list_shares(report_id: str, request: Request, session: SessionDependency) -> list[ReportShareResponse]:
    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        if store.get_document("reports", report_id) is None: raise HTTPException(404, "Report not found")
        return [_share_document_response(item, request) for item in store.list_documents("report_shares", query={"report_id": report_id}, sort=[("created_at", -1)])]
    assert session is not None
    _get_report(report_id, session)
    return [_share_response(share, request) for share in session.scalars(select(ReportShare).where(ReportShare.report_id == report_id).order_by(ReportShare.created_at.desc()))]


@router.post("/{report_id}/shares/{share_id}/revoke", response_model=ReportShareResponse)
def revoke_share(report_id: str, share_id: str, request: Request, session: SessionDependency) -> ReportShareResponse:
    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        share = store.get_document("report_shares", share_id)
        if share is None or share["report_id"] != report_id: raise HTTPException(404, "Report share not found")
        updated = store.update_document("report_shares", share_id, {"revoked_at": datetime.now(timezone.utc)}); assert updated is not None
        return _share_document_response(updated, request)
    assert session is not None
    share = session.get(ReportShare, share_id)
    if share is None or share.report_id != report_id:
        raise HTTPException(404, "Report share not found")
    share.revoked_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(share)
    return _share_response(share, request)


@router.get("/{report_id}/download")
def download(report_id: str, request: Request, session: SessionDependency) -> FileResponse:
    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        report=store.get_document("reports",report_id)
        if report is None: raise HTTPException(404,"Report not found")
        return _report_file_response(type("Report",(),report)(),download=True)
    assert session is not None
    report = _get_report(report_id, session)
    return _report_file_response(report, download=True)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(report_id: str, request: Request, session: SessionDependency) -> Response:
    """Permanently delete a report artifact and its share links."""

    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        report = store.get_document("reports", report_id)
        if report is None:
            raise HTTPException(404, "Report not found")
        if isinstance(report.get("artifact_path"), str):
            delete_report_artifact(request.app.state.settings.data_root, report["artifact_path"])
        share_ids = [str(share["id"]) for share in store.list_documents("report_shares", query={"report_id": report_id})]
        if share_ids:
            store.delete_documents("report_share_password_attempts", {"share_id": {"$in": share_ids}})
        store.delete_documents("report_shares", {"report_id": report_id})
        store.delete_documents("reports", {"id": report_id})
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    assert session is not None
    report = _get_report(report_id, session)
    delete_report_artifact(request.app.state.settings.data_root, report.artifact_path)
    session.execute(delete(ReportShare).where(ReportShare.report_id == report.id))
    session.delete(report)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@public_router.get("/{token}")
def open_shared_report(token: str, request: Request, session: SessionDependency) -> FileResponse:
    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        matches=store.list_documents("report_shares",query={"token_hash":_hash_value(token)})
        share=matches[0] if matches else None; now=datetime.now(timezone.utc)
        if share is None or share.get("revoked_at") is not None or _as_utc(share["expires_at"]) <= now: raise HTTPException(404,"Shared report not found or expired")
        if share.get("password_hash") is not None:
            if _password_attempt_limit_reached_for_document(store, str(share["id"]), request, now):
                raise HTTPException(401, "Shared report access was denied")
            valid, needs_upgrade = _verify_share_password(request.headers.get("X-Report-Password", ""), str(share["password_hash"]))
            if not valid:
                _record_document_password_failure(store, str(share["id"]), request, now)
                raise HTTPException(401, "Shared report access was denied")
            if needs_upgrade:
                upgraded = store.update_document("report_shares", str(share["id"]), {"password_hash": _hash_password(request.headers.get("X-Report-Password", ""))})
                assert upgraded is not None
                share = upgraded
        report=store.get_document("reports",str(share["report_id"]))
        if report is None: raise HTTPException(404,"Report not found")
        return _shared_report_file_response(type("Report",(),report)(),download=bool(share["allow_download"]))
    assert session is not None
    share = session.scalar(select(ReportShare).where(ReportShare.token_hash == _hash_value(token)))
    now = datetime.now(timezone.utc)
    if share is None or share.revoked_at is not None or _as_utc(share.expires_at) <= now:
        raise HTTPException(404, "Shared report not found or expired")
    if share.password_hash is not None:
        supplied = request.headers.get("X-Report-Password", "")
        if _password_attempt_limit_reached(session, share.id, request, now):
            raise HTTPException(401, "Shared report access was denied")
        valid, needs_upgrade = _verify_share_password(supplied, share.password_hash)
        if not valid:
            _record_password_failure(session, share.id, request, now)
            raise HTTPException(401, "Shared report access was denied")
        if needs_upgrade:
            share.password_hash = _hash_password(supplied)
            session.commit()
    report = _get_report(share.report_id, session)
    return _shared_report_file_response(report, download=share.allow_download)


def _get_report(report_id: str, session: Session) -> Report:
    report = session.get(Report, report_id)
    if report is None:
        raise HTTPException(404, "Report not found")
    return report


def _report_file_response(report: Report, *, download: bool) -> FileResponse:
    path = Path(report.artifact_path)
    if not path.is_file():
        raise HTTPException(404, "Report artifact is no longer available")
    media_type = {"json": "application/json", "csv": "text/csv", "html": "text/html", "markdown": "text/markdown"}.get(report.format, "application/octet-stream")
    return FileResponse(path, filename=path.name if download else None, media_type=media_type)


def _shared_report_file_response(report: Report, *, download: bool) -> FileResponse:
    """Prevent an authorized public share response from entering shared caches."""

    response = _report_file_response(report, download=download)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "X-Report-Password"
    return response


def _share_response(share: ReportShare, request: Request, token: str | None = None) -> ReportShareResponse:
    base_url = request.app.state.settings.public_web_url or str(request.base_url).rstrip("/")
    return ReportShareResponse(
        id=share.id,
        report_id=share.report_id,
        expires_at=share.expires_at,
        allow_download=share.allow_download,
        revoked_at=share.revoked_at,
        created_at=share.created_at,
        share_url=f"{base_url}/shared-reports/{token}" if token else None,
    )


def _share_document_response(share: dict, request: Request, token: str | None = None) -> ReportShareResponse:
    base_url=request.app.state.settings.public_web_url or str(request.base_url).rstrip("/")
    return ReportShareResponse(id=str(share["id"]),report_id=str(share["report_id"]),expires_at=share["expires_at"],allow_download=bool(share["allow_download"]),revoked_at=share.get("revoked_at"),created_at=share["created_at"],share_url=f"{base_url}/shared-reports/{token}" if token else None)


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_password(value: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(value.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$16384$8$1$" + base64.b64encode(salt).decode("ascii") + "$" + base64.b64encode(digest).decode("ascii")


def _verify_share_password(supplied: str, encoded: str) -> tuple[bool, bool]:
    """Return (valid, legacy_hash_needing_an_in-place_safe_upgrade)."""

    valid = False
    legacy = not encoded.startswith("scrypt$")
    if encoded.startswith("scrypt$"):
        try:
            _, n, r, p, salt, digest = encoded.split("$", 5)
            computed = hashlib.scrypt(supplied.encode("utf-8"), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=len(base64.b64decode(digest)))
            valid = hmac.compare_digest(computed, base64.b64decode(digest))
        except (ValueError, TypeError):
            valid = False
    else:
        valid = hmac.compare_digest(_hash_value(supplied), encoded)
    return valid, valid and legacy


def _password_attempt_key(share_id: str, request: Request) -> str:
    """Use a privacy-preserving client partition so one client cannot lock out all recipients."""

    client_host = request.client.host if request.client is not None else "unknown"
    # The share id is a separate key in the persistence record.  Keeping this
    # field to the digest alone preserves the fixed-width storage contract.
    del share_id
    return _hash_value(client_host)


def _password_attempt_limit_reached(session: Session, share_id: str, request: Request, now: datetime) -> bool:
    attempt = session.scalar(
        select(ReportSharePasswordAttempt).where(
            ReportSharePasswordAttempt.share_id == share_id,
            ReportSharePasswordAttempt.client_key == _password_attempt_key(share_id, request),
        )
    )
    return bool(
        attempt is not None
        and _as_utc(attempt.expires_at) > now
        and attempt.failure_count >= _PASSWORD_ATTEMPT_LIMIT
    )


def _record_password_failure(session: Session, share_id: str, request: Request, now: datetime) -> bool:
    """Atomically consume a SQL-backed failure allowance for this client partition."""

    client_key = _password_attempt_key(share_id, request)
    expires_at = now + _PASSWORD_WINDOW
    incremented = session.execute(
        update(ReportSharePasswordAttempt)
        .where(
            ReportSharePasswordAttempt.share_id == share_id,
            ReportSharePasswordAttempt.client_key == client_key,
            ReportSharePasswordAttempt.expires_at > now,
            ReportSharePasswordAttempt.failure_count < _PASSWORD_ATTEMPT_LIMIT,
        )
        .values(
            failure_count=ReportSharePasswordAttempt.failure_count + 1,
            updated_at=now,
        )
    )
    if incremented.rowcount == 1:
        session.commit()
        return True
    reset = session.execute(
        update(ReportSharePasswordAttempt)
        .where(
            ReportSharePasswordAttempt.share_id == share_id,
            ReportSharePasswordAttempt.client_key == client_key,
            ReportSharePasswordAttempt.expires_at <= now,
        )
        .values(failure_count=1, expires_at=expires_at, updated_at=now)
    )
    if reset.rowcount == 1:
        session.commit()
        return True
    if _password_attempt_limit_reached(session, share_id, request, now):
        return False
    try:
        session.add(
            ReportSharePasswordAttempt(
                share_id=share_id,
                client_key=client_key,
                failure_count=1,
                expires_at=expires_at,
                updated_at=now,
            )
        )
        session.commit()
        return True
    except IntegrityError:
        session.rollback()
        return _record_password_failure(session, share_id, request, now)


def _password_attempt_limit_reached_for_document(
    store: MongoDocumentStore, share_id: str, request: Request, now: datetime
) -> bool:
    return store.report_share_password_attempt_limit_reached(
        share_id=share_id,
        client_key=_password_attempt_key(share_id, request),
        now=now,
        limit=_PASSWORD_ATTEMPT_LIMIT,
    ) >= _PASSWORD_ATTEMPT_LIMIT


def _record_document_password_failure(
    store: MongoDocumentStore, share_id: str, request: Request, now: datetime
) -> None:
    store.record_report_share_password_failure(
        share_id=share_id,
        client_key=_password_attempt_key(share_id, request),
        now=now,
        window=_PASSWORD_WINDOW,
        limit=_PASSWORD_ATTEMPT_LIMIT,
    )


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
