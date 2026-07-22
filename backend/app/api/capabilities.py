from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CapabilityDeclaration, CapabilityDetection, ModelCapability, ModelEndpoint
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

def session_for_request(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.database.get_session()
    try: yield session
    finally: session.close()

SessionDependency = Annotated[Session, Depends(session_for_request)]


def get_cipher(request: Request) -> SecretCipher:
    try:
        return SecretCipher(request.app.state.settings.secret_encryption_key)
    except SecretConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


def get_capability_detector(request: Request) -> CapabilityDetector:
    return request.app.state.capability_detector


CipherDependency = Annotated[SecretCipher, Depends(get_cipher)]
CapabilityDetectorDependency = Annotated[CapabilityDetector, Depends(get_capability_detector)]

def effective(user: CapabilityDeclaration, detected: str) -> str:
    if user is CapabilityDeclaration.UNSUPPORTED and detected == CapabilityDetection.PASSED.value: return "detected_user_unsupported"
    if user is CapabilityDeclaration.UNSUPPORTED: return "unsupported"
    if user is CapabilityDeclaration.SUPPORTED and detected == CapabilityDetection.PASSED.value: return "verified_by_both"
    if user is CapabilityDeclaration.SUPPORTED and detected == CapabilityDetection.FAILED.value: return "user_declared_detection_failed"
    if user is CapabilityDeclaration.SUPPORTED: return "user_verified"
    if detected == CapabilityDetection.PASSED.value: return "auto_detected"
    return "unverified"

@router.get("", response_model=list[CapabilityResponse])
def list_capabilities(endpoint_id: str, session: SessionDependency) -> list[ModelCapability]:
    if session.get(ModelEndpoint, endpoint_id) is None: raise HTTPException(404, "Model endpoint not found")
    return list(session.scalars(select(ModelCapability).where(ModelCapability.model_endpoint_id == endpoint_id).order_by(ModelCapability.capability_key)))

@router.put("", response_model=CapabilityResponse)
def declare_capability(endpoint_id: str, payload: CapabilityUpdate, session: SessionDependency) -> ModelCapability:
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
    session: SessionDependency,
    cipher: CipherDependency,
    detector: CapabilityDetectorDependency,
) -> list[ModelCapability]:
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
