from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from app.core.secrets import SecretCipher, SecretConfigurationError
from app.infrastructure.providers.common import PROTECTED_REQUEST_FIELDS, validate_custom_headers
from app.infrastructure.providers.connection import ProviderConnectionTester
from app.infrastructure.providers.contracts import ConnectionTestResult
from app.infrastructure.network.outbound import OutboundNetworkError, validate_outbound_url
from app.modules.endpoints.service import EndpointService

router = APIRouter(prefix="/api/v1/model-endpoints", tags=["model endpoints"])
ProtocolProfile = Literal[
    "openai_chat_completions",
    "openai_responses",
    "anthropic_messages",
    "gemini_generate_content",
    "azure_openai_chat_completions",
    "ollama_chat",
    "custom_http_json",
]


def _validate_loopback_profile(base_url: str, protocol_profile: str) -> None:
    hostname = urlparse(base_url).hostname
    if hostname is None:
        return
    try:
        is_loopback = ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        is_loopback = hostname.lower() == "localhost"
    if is_loopback and protocol_profile != "ollama_chat":
        raise ValueError("Loopback model endpoints are allowed only for the local Ollama adapter.")


class EndpointBase(BaseModel):
    display_name: Annotated[str | None, Field(max_length=200)] = None
    base_url: Annotated[str, Field(min_length=1, max_length=2048)]
    model_name: Annotated[str, Field(min_length=1, max_length=255)]
    protocol_profile: ProtocolProfile = "openai_chat_completions"
    custom_headers: dict[str, str] = Field(default_factory=dict)
    default_request_body: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: Annotated[int, Field(ge=1, le=600)] = 60
    max_concurrency: Annotated[int, Field(ge=1, le=1000)] = 1
    api_key_max_concurrency: Annotated[int | None, Field(ge=1, le=1000)] = None
    requests_per_second: Annotated[int | None, Field(ge=1)] = None
    requests_per_minute: Annotated[int | None, Field(ge=1)] = None
    tokens_per_minute: Annotated[int | None, Field(ge=1)] = None
    input_tokens_per_minute: Annotated[int | None, Field(ge=1)] = None
    output_tokens_per_minute: Annotated[int | None, Field(ge=1)] = None
    input_cost_per_million: Annotated[float | None, Field(ge=0)] = None
    output_cost_per_million: Annotated[float | None, Field(ge=0)] = None
    currency: Annotated[str, Field(min_length=3, max_length=8)] = "USD"
    tags: list[Annotated[str, Field(min_length=1, max_length=64)]] = Field(default_factory=list, max_length=32)
    notes: Annotated[str | None, Field(max_length=4000)] = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTP or HTTPS URL")
        if parsed.username or parsed.password:
            raise ValueError("base_url must not include credentials")
        try:
            validate_outbound_url(value, allow_loopback=True, resolve_hostname=False)
        except OutboundNetworkError as error:
            raise ValueError(str(error)) from error
        return value.rstrip("/")

    @field_validator("default_request_body")
    @classmethod
    def validate_default_request_body(cls, value: dict[str, Any]) -> dict[str, Any]:
        protected_fields = sorted(set(value).intersection(PROTECTED_REQUEST_FIELDS))
        if protected_fields:
            raise ValueError("default_request_body cannot override protected fields: " + ", ".join(protected_fields))
        return value

    @field_validator("custom_headers")
    @classmethod
    def validate_custom_headers(cls, value: dict[str, str]) -> dict[str, str]:
        return validate_custom_headers(value)

    @model_validator(mode="after")
    def restrict_loopback_to_local_ollama(self) -> "EndpointBase":
        _validate_loopback_profile(self.base_url, self.protocol_profile)
        return self


class ModelEndpointCreate(EndpointBase):
    api_key: SecretStr


class ModelEndpointUpdate(BaseModel):
    display_name: Annotated[str | None, Field(max_length=200)] = None
    base_url: Annotated[str | None, Field(min_length=1, max_length=2048)] = None
    model_name: Annotated[str | None, Field(min_length=1, max_length=255)] = None
    protocol_profile: ProtocolProfile | None = None
    custom_headers: dict[str, str] | None = None
    default_request_body: dict[str, Any] | None = None
    timeout_seconds: Annotated[int | None, Field(ge=1, le=600)] = None
    max_concurrency: Annotated[int | None, Field(ge=1, le=1000)] = None
    api_key_max_concurrency: Annotated[int | None, Field(ge=1, le=1000)] = None
    requests_per_second: Annotated[int | None, Field(ge=1)] = None
    requests_per_minute: Annotated[int | None, Field(ge=1)] = None
    tokens_per_minute: Annotated[int | None, Field(ge=1)] = None
    input_tokens_per_minute: Annotated[int | None, Field(ge=1)] = None
    output_tokens_per_minute: Annotated[int | None, Field(ge=1)] = None
    input_cost_per_million: Annotated[float | None, Field(ge=0)] = None
    output_cost_per_million: Annotated[float | None, Field(ge=0)] = None
    currency: Annotated[str | None, Field(min_length=3, max_length=8)] = None
    tags: list[Annotated[str, Field(min_length=1, max_length=64)]] | None = Field(default=None, max_length=32)
    notes: Annotated[str | None, Field(max_length=4000)] = None
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

    @field_validator("custom_headers")
    @classmethod
    def validate_custom_headers(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        return None if value is None else validate_custom_headers(value)


class ModelEndpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    base_url: str
    model_name: str
    protocol_profile: str
    api_key_mask: str
    custom_headers: dict[str, str]
    default_request_body: dict[str, Any]
    timeout_seconds: int
    max_concurrency: int
    api_key_max_concurrency: int | None
    requests_per_second: int | None
    requests_per_minute: int | None
    tokens_per_minute: int | None
    input_tokens_per_minute: int | None
    output_tokens_per_minute: int | None
    input_cost_per_million: float | None
    output_cost_per_million: float | None
    currency: str
    tags: list[str]
    notes: str | None
    status: str
    last_tested_at: datetime | None
    last_connection_error: str | None
    created_at: datetime
    updated_at: datetime


def get_cipher(request: Request) -> SecretCipher:
    try:
        return SecretCipher(request.app.state.settings.secret_encryption_key)
    except SecretConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


def get_connection_tester(request: Request) -> ProviderConnectionTester:
    return request.app.state.connection_tester


def get_endpoint_service(request: Request) -> EndpointService:
    return request.app.state.endpoint_service


EndpointServiceDependency = Annotated[EndpointService, Depends(get_endpoint_service)]
CipherDependency = Annotated[SecretCipher, Depends(get_cipher)]
ConnectionTesterDependency = Annotated[ProviderConnectionTester, Depends(get_connection_tester)]


@router.post("", response_model=ModelEndpointResponse, status_code=status.HTTP_201_CREATED)
def create_model_endpoint(
    payload: ModelEndpointCreate,
    service: EndpointServiceDependency,
    cipher: CipherDependency,
) -> Any:
    return service.create(payload, cipher)


@router.get("", response_model=list[ModelEndpointResponse])
def list_model_endpoints(
    service: EndpointServiceDependency,
) -> list[Any]:
    return service.list()


@router.get("/{endpoint_id}", response_model=ModelEndpointResponse)
def get_model_endpoint(
    endpoint_id: str,
    service: EndpointServiceDependency,
) -> Any:
    return service.get(endpoint_id)


class ConnectionTestResponse(BaseModel):
    success: bool
    status: str
    message: str
    provider_status_code: int | None
    tested_at: datetime
    request: "ConnectionTestRequestResponse"


class ConnectionTestRequestResponse(BaseModel):
    method: Literal["POST"]
    url: str
    body: dict[str, Any]


class RequestPreviewRequest(BaseModel):
    messages: list[dict[str, Any]]


class RequestPreviewResponse(BaseModel):
    protocol_profile: str
    request_body: dict[str, Any]
    protected_fields: list[str]


@router.post("/{endpoint_id}/connection-test", response_model=ConnectionTestResponse)
def test_model_endpoint_connection(
    endpoint_id: str,
    service: EndpointServiceDependency,
    cipher: CipherDependency,
    connection_tester: ConnectionTesterDependency,
) -> ConnectionTestResponse:
    endpoint, test_request = service.connection_request(endpoint_id)
    try:
        encrypted_key = endpoint["encrypted_api_key"] if isinstance(endpoint, dict) else endpoint.encrypted_api_key
        api_key = cipher.decrypt(str(encrypted_key))
    except SecretConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    result: ConnectionTestResult = connection_tester.test(endpoint, api_key)
    tested_at = datetime.now(timezone.utc)
    updated = service.record_connection_test(
        endpoint_id, success=result.success, message=result.message, tested_at=tested_at
    )
    endpoint_status = updated["status"] if isinstance(updated, dict) else updated.status

    return ConnectionTestResponse(
        success=result.success,
        status=endpoint_status,
        message=result.message,
        provider_status_code=result.provider_status_code,
        tested_at=tested_at,
        request=ConnectionTestRequestResponse(
            method="POST",
            url=test_request.url,
            body=test_request.body,
        ),
    )


@router.post("/{endpoint_id}/request-preview", response_model=RequestPreviewResponse)
def preview_model_request(
    endpoint_id: str,
    payload: RequestPreviewRequest,
    service: EndpointServiceDependency,
) -> RequestPreviewResponse:
    profile, request_body = service.preview_request(endpoint_id, payload.messages)
    return RequestPreviewResponse(
        protocol_profile=profile, request_body=request_body, protected_fields=sorted(PROTECTED_REQUEST_FIELDS)
    )


@router.patch("/{endpoint_id}", response_model=ModelEndpointResponse)
def update_model_endpoint(
    endpoint_id: str,
    payload: ModelEndpointUpdate,
    service: EndpointServiceDependency,
    cipher: CipherDependency,
) -> Any:
    return service.update(endpoint_id, payload, cipher)


@router.delete("/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model_endpoint(endpoint_id: str, service: EndpointServiceDependency) -> Response:
    service.delete(endpoint_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
