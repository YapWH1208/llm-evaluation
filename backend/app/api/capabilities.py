from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CapabilityDeclaration, CapabilityDetection, ModelCapability, ModelEndpoint
from app.db.mongo import MongoDocumentStore
from app.core.secrets import SecretCipher, SecretConfigurationError
from app.services.capability_detector import CapabilityDetector, CapabilityDetectionResult, DEFAULT_CAPABILITY_KEYS

router = APIRouter(prefix="/api/v1/model-endpoints/{endpoint_id}/capabilities", tags=["capabilities"])

class CapabilityUpdate(BaseModel):
    capability_key: str = Field(min_length=1, max_length=128)
    user_declared_status: CapabilityDeclaration


class CapabilityDetectionRequest(BaseModel):
    capability_keys: list[str] = Field(default_factory=lambda: list(DEFAULT_CAPABILITY_KEYS), min_length=1, max_length=32)

    def normalized_keys(self) -> list[str]:
        return list(dict.fromkeys(key.strip() for key in self.capability_keys if key.strip()))

class CapabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; capability_key: str; user_declared_status: str; auto_detection_status: str; effective_status: str
    detection_evidence: dict[str, Any] | None; detector_version: str | None; last_detected_at: datetime | None


class CapabilityConflictResponse(CapabilityResponse):
    resolution_options: list[str]

def session_for_request(request: Request) -> Generator[Session | None, None, None]:
    if getattr(request.app.state, "document_store", None) is not None:
        yield None
        return
    session = request.app.state.database.get_session()
    try: yield session
    finally: session.close()

SessionDependency = Annotated[Session | None, Depends(session_for_request)]


def get_cipher(request: Request) -> SecretCipher:
    try:
        return SecretCipher(request.app.state.settings.secret_encryption_key)
    except SecretConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


def get_capability_detector(request: Request) -> CapabilityDetector:
    return request.app.state.capability_detector


CipherDependency = Annotated[SecretCipher, Depends(get_cipher)]
CapabilityDetectorDependency = Annotated[CapabilityDetector, Depends(get_capability_detector)]


def get_document_store(request: Request) -> MongoDocumentStore | None:
    return getattr(request.app.state, "document_store", None)


def get_document_endpoint_or_404(store: MongoDocumentStore, endpoint_id: str) -> dict[str, Any]:
    endpoint = store.get_document("model_endpoints", endpoint_id)
    if endpoint is None:
        raise HTTPException(404, "Model endpoint not found")
    return endpoint


def _endpoint_proxy(endpoint: dict[str, Any]) -> Any:
    return type("DocumentEndpoint", (), endpoint)()

def effective(user: CapabilityDeclaration, detected: str) -> str:
    if user is CapabilityDeclaration.UNSUPPORTED and detected == CapabilityDetection.PASSED.value: return "detected_user_unsupported"
    if user is CapabilityDeclaration.UNSUPPORTED: return "unsupported"
    if user is CapabilityDeclaration.SUPPORTED and detected == CapabilityDetection.PASSED.value: return "verified_by_both"
    if user is CapabilityDeclaration.SUPPORTED and detected == CapabilityDetection.FAILED.value: return "user_declared_detection_failed"
    if user is CapabilityDeclaration.SUPPORTED: return "user_verified"
    if detected == CapabilityDetection.PASSED.value: return "auto_detected"
    return "unverified"

@router.get("", response_model=list[CapabilityResponse])
def list_capabilities(
    endpoint_id: str,
    request: Request,
    session: SessionDependency,
) -> list[ModelCapability | dict[str, Any]]:
    store = get_document_store(request)
    if store is not None:
        get_document_endpoint_or_404(store, endpoint_id)
        return store.list_documents(
            "model_capabilities",
            query={"model_endpoint_id": endpoint_id},
            sort=[("capability_key", 1)],
        )
    assert session is not None
    if session.get(ModelEndpoint, endpoint_id) is None: raise HTTPException(404, "Model endpoint not found")
    return list(session.scalars(select(ModelCapability).where(ModelCapability.model_endpoint_id == endpoint_id).order_by(ModelCapability.capability_key)))


@router.get("/conflicts", response_model=list[CapabilityConflictResponse])
def list_capability_conflicts(
    endpoint_id: str,
    request: Request,
    session: SessionDependency,
) -> list[dict[str, Any]]:
    """Return actionable conflicts without overwriting either source of truth."""

    store = get_document_store(request)
    if store is not None:
        get_document_endpoint_or_404(store, endpoint_id)
        capabilities: list[ModelCapability | dict[str, Any]] = store.list_documents("model_capabilities", query={"model_endpoint_id": endpoint_id})
    else:
        assert session is not None
        if session.get(ModelEndpoint, endpoint_id) is None:
            raise HTTPException(404, "Model endpoint not found")
        capabilities = list(session.scalars(select(ModelCapability).where(ModelCapability.model_endpoint_id == endpoint_id)))
    conflicts: list[dict[str, Any]] = []
    for capability in capabilities:
        values = _capability_values(capability)
        if values["effective_status"] not in {"user_declared_detection_failed", "detected_user_unsupported"}:
            continue
        conflicts.append({**values, "resolution_options": ["keep_disabled", "force_enable", "redetect"]})
    return conflicts


def _capability_values(capability: ModelCapability | dict[str, Any]) -> dict[str, Any]:
    if isinstance(capability, dict):
        return {
            "id": str(capability["id"]), "capability_key": str(capability["capability_key"]),
            "user_declared_status": str(capability["user_declared_status"]), "auto_detection_status": str(capability["auto_detection_status"]),
            "effective_status": str(capability["effective_status"]), "detection_evidence": capability.get("detection_evidence"),
            "detector_version": capability.get("detector_version"), "last_detected_at": capability.get("last_detected_at"),
        }
    return {
        "id": capability.id, "capability_key": capability.capability_key,
        "user_declared_status": capability.user_declared_status, "auto_detection_status": capability.auto_detection_status,
        "effective_status": capability.effective_status, "detection_evidence": capability.detection_evidence,
        "detector_version": capability.detector_version, "last_detected_at": capability.last_detected_at,
    }

@router.put("", response_model=CapabilityResponse)
def declare_capability(
    endpoint_id: str,
    payload: CapabilityUpdate,
    request: Request,
    session: SessionDependency,
) -> ModelCapability | dict[str, Any]:
    store = get_document_store(request)
    if store is not None:
        get_document_endpoint_or_404(store, endpoint_id)
        existing = store.list_documents(
            "model_capabilities",
            query={"model_endpoint_id": endpoint_id, "capability_key": payload.capability_key},
        )
        detected = str(existing[0]["auto_detection_status"]) if existing else CapabilityDetection.NOT_TESTED.value
        values = {
            "model_endpoint_id": endpoint_id,
            "capability_key": payload.capability_key,
            "user_declared_status": payload.user_declared_status.value,
            "auto_detection_status": detected,
            "effective_status": effective(payload.user_declared_status, detected),
            "detection_evidence": existing[0].get("detection_evidence") if existing else None,
            "detector_version": existing[0].get("detector_version") if existing else None,
            "last_detected_at": existing[0].get("last_detected_at") if existing else None,
        }
        if existing:
            updated = store.update_document("model_capabilities", str(existing[0]["id"]), values)
            assert updated is not None
            return updated
        return store.insert_document("model_capabilities", values)
    assert session is not None
    if session.get(ModelEndpoint, endpoint_id) is None: raise HTTPException(404, "Model endpoint not found")
    item = session.scalar(select(ModelCapability).where(ModelCapability.model_endpoint_id == endpoint_id, ModelCapability.capability_key == payload.capability_key))
    if item is None:
        item = ModelCapability(model_endpoint_id=endpoint_id, capability_key=payload.capability_key)
        session.add(item)
    item.user_declared_status = payload.user_declared_status.value
    item.effective_status = effective(payload.user_declared_status, item.auto_detection_status)
    session.commit(); session.refresh(item)
    return item


@router.post("/detect", response_model=list[CapabilityResponse])
def detect_capabilities(
    endpoint_id: str,
    payload: CapabilityDetectionRequest,
    request: Request,
    session: SessionDependency,
    cipher: CipherDependency,
    detector: CapabilityDetectorDependency,
) -> list[ModelCapability | dict[str, Any]]:
    store = get_document_store(request)
    if store is not None:
        endpoint = get_document_endpoint_or_404(store, endpoint_id)
        capability_keys = payload.normalized_keys()
        if not capability_keys:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "At least one capability key is required")
        results = detector.detect(
            _endpoint_proxy(endpoint),
            cipher.decrypt(str(endpoint["encrypted_api_key"])),
            capability_keys,
        )
        by_key = {result.capability_key: result for result in results}
        now = datetime.now(timezone.utc)
        updated: list[dict[str, Any]] = []
        for key in capability_keys:
            result = by_key.get(key)
            if result is None:
                continue
            existing = store.list_documents(
                "model_capabilities",
                query={"model_endpoint_id": endpoint_id, "capability_key": key},
            )
            user_status = str(existing[0]["user_declared_status"]) if existing else CapabilityDeclaration.UNKNOWN.value
            values = {
                "model_endpoint_id": endpoint_id,
                "capability_key": key,
                "user_declared_status": user_status,
                "auto_detection_status": result.status.value,
                "effective_status": effective(CapabilityDeclaration(user_status), result.status.value),
                "detection_evidence": result.evidence,
                "detector_version": str(result.evidence.get("adapter_version", "unknown")),
                "last_detected_at": now,
            }
            if existing:
                item = store.update_document("model_capabilities", str(existing[0]["id"]), values)
                assert item is not None
            else:
                item = store.insert_document("model_capabilities", values)
            updated.append(item)
        return updated
    assert session is not None
    endpoint = session.get(ModelEndpoint, endpoint_id)
    if endpoint is None:
        raise HTTPException(404, "Model endpoint not found")
    capability_keys = payload.normalized_keys()
    if not capability_keys:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "At least one capability key is required")

    results: list[CapabilityDetectionResult] = detector.detect(
        endpoint,
        cipher.decrypt(endpoint.encrypted_api_key),
        capability_keys,
    )
    by_key = {result.capability_key: result for result in results}
    now = datetime.now(timezone.utc)
    updated: list[ModelCapability] = []
    for key in capability_keys:
        result = by_key.get(key)
        if result is None:
            continue
        item = session.scalar(select(ModelCapability).where(ModelCapability.model_endpoint_id == endpoint_id, ModelCapability.capability_key == key))
        if item is None:
            item = ModelCapability(
                model_endpoint_id=endpoint_id,
                capability_key=key,
                user_declared_status=CapabilityDeclaration.UNKNOWN.value,
                auto_detection_status=CapabilityDetection.NOT_TESTED.value,
            )
            session.add(item)
        item.auto_detection_status = result.status.value
        item.detection_evidence = result.evidence
        item.detector_version = str(result.evidence.get("adapter_version", "unknown"))
        item.last_detected_at = now
        item.effective_status = effective(CapabilityDeclaration(item.user_declared_status), item.auto_detection_status)
        updated.append(item)
    session.commit()
    for item in updated:
        session.refresh(item)
    return updated
