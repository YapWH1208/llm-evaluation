from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from app.db.models import CapabilityDeclaration
from app.infrastructure.providers.capabilities import CapabilityDetector, DEFAULT_CAPABILITY_KEYS
from app.modules.endpoints.api import get_cipher
from app.modules.endpoints.service import EndpointService


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

    id: str
    capability_key: str
    user_declared_status: str
    auto_detection_status: str
    effective_status: str
    detection_evidence: dict[str, Any] | None
    detector_version: str | None
    last_detected_at: datetime | None


class CapabilityConflictResponse(CapabilityResponse):
    resolution_options: list[str]


def get_endpoint_service(request: Request) -> EndpointService:
    return request.app.state.endpoint_service


def get_capability_detector(request: Request) -> CapabilityDetector:
    return request.app.state.capability_detector


EndpointServiceDependency = Annotated[EndpointService, Depends(get_endpoint_service)]
CipherDependency = Annotated[Any, Depends(get_cipher)]
CapabilityDetectorDependency = Annotated[CapabilityDetector, Depends(get_capability_detector)]


@router.get("", response_model=list[CapabilityResponse])
def list_capabilities(endpoint_id: str, service: EndpointServiceDependency) -> list[Any]:
    return service.list_capabilities(endpoint_id)


@router.get("/conflicts", response_model=list[CapabilityConflictResponse])
def list_capability_conflicts(endpoint_id: str, service: EndpointServiceDependency) -> list[dict[str, Any]]:
    return service.list_capability_conflicts(endpoint_id)


@router.put("", response_model=CapabilityResponse)
def declare_capability(endpoint_id: str, payload: CapabilityUpdate, service: EndpointServiceDependency) -> Any:
    return service.declare_capability(endpoint_id, payload.capability_key, payload.user_declared_status)


@router.post("/detect", response_model=list[CapabilityResponse])
def detect_capabilities(
    endpoint_id: str,
    payload: CapabilityDetectionRequest,
    service: EndpointServiceDependency,
    cipher: CipherDependency,
    detector: CapabilityDetectorDependency,
) -> list[Any]:
    return service.detect_capabilities(endpoint_id, payload.normalized_keys(), cipher, detector)
