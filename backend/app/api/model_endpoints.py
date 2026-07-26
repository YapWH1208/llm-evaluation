from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.secrets import SecretCipher, SecretConfigurationError, mask_secret
from app.db import EndpointStatus, ModelEndpoint
from app.db.mongo import MongoDocumentStore
from app.services.connection_tester import ConnectionTestResult, ConnectionTester, PROTECTED_REQUEST_FIELDS
from app.services.model_executor import OpenAIChatCompletionsExecutor
from app.services.provider_headers import validate_custom_headers

router = APIRouter(prefix="/api/v1/model-endpoints", tags=["model endpoints"])
ProtocolProfile = Literal["openai_chat_completions", "openai_responses"]


class EndpointBase(BaseModel):
    display_name: Annotated[str | None, Field(max_length=200)] = None
    base_url: Annotated[str, Field(min_length=1, max_length=2048)]
    model_name: Annotated[str, Field(min_length=1, max_length=255)]
    protocol_profile: ProtocolProfile = "openai_chat_completions"
    custom_headers: dict[str, str] = Field(default_factory=dict)
    default_request_body: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: Annotated[int, Field(ge=1, le=600)] = 60
    max_concurrency: Annotated[int, Field(ge=1, le=1000)] = 1
    requests_per_minute: Annotated[int | None, Field(ge=1)] = None
    tokens_per_minute: Annotated[int | None, Field(ge=1)] = None
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

    @field_validator("custom_headers")
    @classmethod
    def validate_custom_headers(cls, value: dict[str, str]) -> dict[str, str]:
        return validate_custom_headers(value)


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
    requests_per_minute: Annotated[int | None, Field(ge=1)] = None
    tokens_per_minute: Annotated[int | None, Field(ge=1)] = None
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
    requests_per_minute: int | None
    tokens_per_minute: int | None
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


def get_session(request: Request) -> Generator[Session | None, None, None]:
    if getattr(request.app.state, "document_store", None) is not None:
        yield None
        return
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


SessionDependency = Annotated[Session | None, Depends(get_session)]
CipherDependency = Annotated[SecretCipher, Depends(get_cipher)]
ConnectionTesterDependency = Annotated[ConnectionTester, Depends(get_connection_tester)]


def get_endpoint_or_404(session: Session, endpoint_id: str) -> ModelEndpoint:
    endpoint = session.get(ModelEndpoint, endpoint_id)
    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model endpoint not found")
    return endpoint


def get_document_store(request: Request) -> MongoDocumentStore | None:
    return getattr(request.app.state, "document_store", None)


def get_document_endpoint_or_404(store: MongoDocumentStore, endpoint_id: str) -> dict[str, Any]:
    endpoint = store.get_document("model_endpoints", endpoint_id)
    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model endpoint not found")
    return endpoint


def _endpoint_proxy(endpoint: dict[str, Any]) -> Any:
    """Give protocol adapters attribute access without coupling them to a database."""

    return type("DocumentEndpoint", (), endpoint)()


@router.post("", response_model=ModelEndpointResponse, status_code=status.HTTP_201_CREATED)
def create_model_endpoint(
    payload: ModelEndpointCreate,
    request: Request,
    session: SessionDependency,
    cipher: CipherDependency,
) -> ModelEndpoint | dict[str, Any]:
    api_key = payload.api_key.get_secret_value()
    store = get_document_store(request)
    if store is not None:
        now = datetime.now(timezone.utc)
        return store.insert_document(
            "model_endpoints",
            {
                "display_name": payload.display_name or payload.model_name,
                "base_url": payload.base_url,
                "model_name": payload.model_name,
                "protocol_profile": payload.protocol_profile,
                "encrypted_api_key": cipher.encrypt(api_key),
                "api_key_mask": mask_secret(api_key),
                "custom_headers": payload.custom_headers,
                "default_request_body": payload.default_request_body,
                "timeout_seconds": payload.timeout_seconds,
                "max_concurrency": payload.max_concurrency,
                "requests_per_minute": payload.requests_per_minute,
                "tokens_per_minute": payload.tokens_per_minute,
                "input_cost_per_million": payload.input_cost_per_million,
                "output_cost_per_million": payload.output_cost_per_million,
                "currency": payload.currency.upper(),
                "tags": payload.tags,
                "notes": payload.notes,
                "status": EndpointStatus.UNVERIFIED.value,
                "last_tested_at": None,
                "last_connection_error": None,
                "created_at": now,
                "updated_at": now,
            },
        )
    assert session is not None
    endpoint = ModelEndpoint(
        display_name=payload.display_name or payload.model_name,
        base_url=payload.base_url,
        model_name=payload.model_name,
        protocol_profile=payload.protocol_profile,
        encrypted_api_key=cipher.encrypt(api_key),
        api_key_mask=mask_secret(api_key),
        custom_headers=payload.custom_headers,
        default_request_body=payload.default_request_body,
        timeout_seconds=payload.timeout_seconds,
        max_concurrency=payload.max_concurrency,
        requests_per_minute=payload.requests_per_minute,
        tokens_per_minute=payload.tokens_per_minute,
        input_cost_per_million=payload.input_cost_per_million,
        output_cost_per_million=payload.output_cost_per_million,
        currency=payload.currency.upper(),
        tags=payload.tags,
        notes=payload.notes,
    )
    session.add(endpoint)
    session.commit()
    session.refresh(endpoint)
    return endpoint


@router.get("", response_model=list[ModelEndpointResponse])
def list_model_endpoints(
    request: Request,
    session: SessionDependency,
) -> list[ModelEndpoint | dict[str, Any]]:
    store = get_document_store(request)
    if store is not None:
        return store.list_documents("model_endpoints", sort=[("created_at", -1)])
    assert session is not None
    return list(session.scalars(select(ModelEndpoint).order_by(ModelEndpoint.created_at.desc())))


@router.get("/{endpoint_id}", response_model=ModelEndpointResponse)
def get_model_endpoint(
    endpoint_id: str,
    request: Request,
    session: SessionDependency,
) -> ModelEndpoint | dict[str, Any]:
    store = get_document_store(request)
    if store is not None:
        return get_document_endpoint_or_404(store, endpoint_id)
    assert session is not None
    return get_endpoint_or_404(session, endpoint_id)


class ConnectionTestResponse(BaseModel):
    success: bool
    status: str
    message: str
    provider_status_code: int | None
    tested_at: datetime


class RequestPreviewRequest(BaseModel):
    messages: list[dict[str, Any]]


class RequestPreviewResponse(BaseModel):
    protocol_profile: str
    request_body: dict[str, Any]
    protected_fields: list[str]


@router.post("/{endpoint_id}/connection-test", response_model=ConnectionTestResponse)
def test_model_endpoint_connection(
    endpoint_id: str,
    request: Request,
    session: SessionDependency,
    cipher: CipherDependency,
    connection_tester: ConnectionTesterDependency,
) -> ConnectionTestResponse:
    store = get_document_store(request)
    if store is not None:
        endpoint = get_document_endpoint_or_404(store, endpoint_id)
        try:
            api_key = cipher.decrypt(str(endpoint["encrypted_api_key"]))
        except SecretConfigurationError as error:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
        result: ConnectionTestResult = connection_tester.test(_endpoint_proxy(endpoint), api_key)
        tested_at = datetime.now(timezone.utc)
        endpoint_status = EndpointStatus.AVAILABLE.value if result.success else EndpointStatus.UNAVAILABLE.value
        store.update_document(
            "model_endpoints",
            endpoint_id,
            {
                "last_tested_at": tested_at,
                "status": endpoint_status,
                "last_connection_error": None if result.success else result.message,
            },
        )
        return ConnectionTestResponse(
            success=result.success,
            status=endpoint_status,
            message=result.message,
            provider_status_code=result.provider_status_code,
            tested_at=tested_at,
        )
    assert session is not None
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


@router.post("/{endpoint_id}/request-preview", response_model=RequestPreviewResponse)
def preview_model_request(
    endpoint_id: str,
    payload: RequestPreviewRequest,
    request: Request,
    session: SessionDependency,
) -> RequestPreviewResponse:
    store = get_document_store(request)
    endpoint: Any = _endpoint_proxy(get_document_endpoint_or_404(store, endpoint_id)) if store is not None else get_endpoint_or_404(session, endpoint_id)  # type: ignore[arg-type]
    try:
        request_body = OpenAIChatCompletionsExecutor._build_request(endpoint, {"messages": payload.messages})
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    return RequestPreviewResponse(protocol_profile=str(endpoint.protocol_profile), request_body=request_body, protected_fields=sorted(PROTECTED_REQUEST_FIELDS))


@router.patch("/{endpoint_id}", response_model=ModelEndpointResponse)
def update_model_endpoint(
    endpoint_id: str,
    payload: ModelEndpointUpdate,
    request: Request,
    session: SessionDependency,
    cipher: CipherDependency,
) -> ModelEndpoint | dict[str, Any]:
    store = get_document_store(request)
    if store is not None:
        get_document_endpoint_or_404(store, endpoint_id)
        update_values = payload.model_dump(exclude_unset=True, exclude={"api_key"})
        update_values = {key: value for key, value in update_values.items() if value is not None}
        if "currency" in update_values:
            update_values["currency"] = str(update_values["currency"]).upper()
        if "api_key" in payload.model_fields_set and payload.api_key is not None:
            api_key = payload.api_key.get_secret_value()
            update_values["encrypted_api_key"] = cipher.encrypt(api_key)
            update_values["api_key_mask"] = mask_secret(api_key)
        updated = store.update_document("model_endpoints", endpoint_id, update_values)
        assert updated is not None
        return updated
    assert session is not None
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
def delete_model_endpoint(endpoint_id: str, request: Request, session: SessionDependency) -> Response:
    store = get_document_store(request)
    if store is not None:
        if not store.delete_document("model_endpoints", endpoint_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model endpoint not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    assert session is not None
    endpoint = get_endpoint_or_404(session, endpoint_id)
    session.delete(endpoint)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
