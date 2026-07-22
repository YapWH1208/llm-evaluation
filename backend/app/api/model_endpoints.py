from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from typing import Annotated, Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.secrets import SecretCipher, SecretConfigurationError, mask_secret
from app.db import EndpointStatus, ModelEndpoint
from app.services.connection_tester import ConnectionTestResult, ConnectionTester, PROTECTED_REQUEST_FIELDS

router = APIRouter(prefix="/api/v1/model-endpoints", tags=["model endpoints"])


class EndpointBase(BaseModel):
    display_name: Annotated[str | None, Field(max_length=200)] = None
    base_url: Annotated[str, Field(min_length=1, max_length=2048)]
    model_name: Annotated[str, Field(min_length=1, max_length=255)]
    default_request_body: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: Annotated[int, Field(ge=1, le=600)] = 60
    max_concurrency: Annotated[int, Field(ge=1, le=1000)] = 1
    requests_per_minute: Annotated[int | None, Field(ge=1)] = None
    tokens_per_minute: Annotated[int | None, Field(ge=1)] = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTP or HTTPS URL")
        if parsed.username or parsed.password:
            raise ValueError("base_url must not include credentials")
        return value.rstrip("/")

    @field_validator("default_request_body")
    @classmethod
    def validate_default_request_body(cls, value: dict[str, Any]) -> dict[str, Any]:
        protected_fields = sorted(set(value).intersection(PROTECTED_REQUEST_FIELDS))
        if protected_fields:
            raise ValueError(
                "default_request_body cannot override protected fields: "
                + ", ".join(protected_fields)
            )
        return value


class ModelEndpointCreate(EndpointBase):
    api_key: SecretStr


class ModelEndpointUpdate(BaseModel):
    display_name: Annotated[str | None, Field(max_length=200)] = None
    base_url: Annotated[str | None, Field(min_length=1, max_length=2048)] = None
    model_name: Annotated[str | None, Field(min_length=1, max_length=255)] = None
    default_request_body: dict[str, Any] | None = None
    timeout_seconds: Annotated[int | None, Field(ge=1, le=600)] = None
    max_concurrency: Annotated[int | None, Field(ge=1, le=1000)] = None
    requests_per_minute: Annotated[int | None, Field(ge=1)] = None
    tokens_per_minute: Annotated[int | None, Field(ge=1)] = None
    api_key: SecretStr | None = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return EndpointBase.validate_base_url(value)

    @field_validator("default_request_body")
    @classmethod
    def validate_default_request_body(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return value
        return EndpointBase.validate_default_request_body(value)


class ModelEndpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    base_url: str
    model_name: str
    protocol_profile: str
    api_key_mask: str
    default_request_body: dict[str, Any]
    timeout_seconds: int
    max_concurrency: int
    requests_per_minute: int | None
    tokens_per_minute: int | None
    status: str
    last_tested_at: datetime | None
    last_connection_error: str | None
    created_at: datetime
    updated_at: datetime


def get_session(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.database.get_session()
    try:
        yield session
    finally:
        session.close()


def get_cipher(request: Request) -> SecretCipher:
    try:
        return SecretCipher(request.app.state.settings.secret_encryption_key)
    except SecretConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


def get_connection_tester(request: Request) -> ConnectionTester:
    return request.app.state.connection_tester


SessionDependency = Annotated[Session, Depends(get_session)]
CipherDependency = Annotated[SecretCipher, Depends(get_cipher)]
ConnectionTesterDependency = Annotated[ConnectionTester, Depends(get_connection_tester)]


def get_endpoint_or_404(session: Session, endpoint_id: str) -> ModelEndpoint:
    endpoint = session.get(ModelEndpoint, endpoint_id)
    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model endpoint not found")
    return endpoint


@router.post("", response_model=ModelEndpointResponse, status_code=status.HTTP_201_CREATED)
def create_model_endpoint(
    payload: ModelEndpointCreate,
    session: SessionDependency,
    cipher: CipherDependency,
) -> ModelEndpoint:
    api_key = payload.api_key.get_secret_value()
    endpoint = ModelEndpoint(
        display_name=payload.display_name or payload.model_name,
        base_url=payload.base_url,
        model_name=payload.model_name,
        encrypted_api_key=cipher.encrypt(api_key),
        api_key_mask=mask_secret(api_key),
        default_request_body=payload.default_request_body,
        timeout_seconds=payload.timeout_seconds,
        max_concurrency=payload.max_concurrency,
        requests_per_minute=payload.requests_per_minute,
        tokens_per_minute=payload.tokens_per_minute,
    )
    session.add(endpoint)
    session.commit()
    session.refresh(endpoint)
    return endpoint


@router.get("", response_model=list[ModelEndpointResponse])
def list_model_endpoints(session: SessionDependency) -> list[ModelEndpoint]:
    return list(session.scalars(select(ModelEndpoint).order_by(ModelEndpoint.created_at.desc())))


@router.get("/{endpoint_id}", response_model=ModelEndpointResponse)
def get_model_endpoint(endpoint_id: str, session: SessionDependency) -> ModelEndpoint:
    return get_endpoint_or_404(session, endpoint_id)


class ConnectionTestResponse(BaseModel):
    success: bool
    status: str
    message: str
    provider_status_code: int | None
    tested_at: datetime


@router.post("/{endpoint_id}/connection-test", response_model=ConnectionTestResponse)
def test_model_endpoint_connection(
    endpoint_id: str,
    session: SessionDependency,
    cipher: CipherDependency,
    connection_tester: ConnectionTesterDependency,
) -> ConnectionTestResponse:
    endpoint = get_endpoint_or_404(session, endpoint_id)
    try:
        api_key = cipher.decrypt(endpoint.encrypted_api_key)
    except SecretConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error

    result: ConnectionTestResult = connection_tester.test(endpoint, api_key)
    tested_at = datetime.now(timezone.utc)
    endpoint.last_tested_at = tested_at
    endpoint.status = (
        EndpointStatus.AVAILABLE.value if result.success else EndpointStatus.UNAVAILABLE.value
    )
    endpoint.last_connection_error = None if result.success else result.message
    session.commit()

    return ConnectionTestResponse(
        success=result.success,
        status=endpoint.status,
        message=result.message,
        provider_status_code=result.provider_status_code,
        tested_at=tested_at,
    )


@router.patch("/{endpoint_id}", response_model=ModelEndpointResponse)
def update_model_endpoint(
    endpoint_id: str,
    payload: ModelEndpointUpdate,
    session: SessionDependency,
    cipher: CipherDependency,
) -> ModelEndpoint:
    endpoint = get_endpoint_or_404(session, endpoint_id)
    update_values = payload.model_dump(exclude_unset=True, exclude={"api_key"})

    for field, value in update_values.items():
        if value is not None:
            setattr(endpoint, field, value)

    if "api_key" in payload.model_fields_set and payload.api_key is not None:
        api_key = payload.api_key.get_secret_value()
        endpoint.encrypted_api_key = cipher.encrypt(api_key)
        endpoint.api_key_mask = mask_secret(api_key)

    session.commit()
    session.refresh(endpoint)
    return endpoint


@router.delete("/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model_endpoint(endpoint_id: str, session: SessionDependency) -> Response:
    endpoint = get_endpoint_or_404(session, endpoint_id)
    session.delete(endpoint)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
