from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CapabilityDeclaration, CapabilityDetection, ModelCapability, ModelEndpoint

router = APIRouter(prefix="/api/v1/model-endpoints/{endpoint_id}/capabilities", tags=["capabilities"])

class CapabilityUpdate(BaseModel):
    capability_key: str = Field(min_length=1, max_length=128)
    user_declared_status: CapabilityDeclaration

class CapabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; capability_key: str; user_declared_status: str; auto_detection_status: str; effective_status: str
    detection_evidence: dict[str, Any] | None; detector_version: str | None; last_detected_at: datetime | None

def session_for_request(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.database.get_session()
    try: yield session
    finally: session.close()

SessionDependency = Annotated[Session, Depends(session_for_request)]

def effective(user: CapabilityDeclaration, detected: str) -> str:
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
