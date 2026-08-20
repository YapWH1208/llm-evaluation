from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.core.secrets import SecretCipher, SecretConfigurationError
from app.infrastructure.providers.contracts import ModelExecutor
from app.modules.evaluations.execution import ExecutionService


router = APIRouter(prefix="/api/v1/workers", tags=["workers"])


class ClaimRequest(BaseModel):
    worker_id: str = Field(min_length=1, max_length=128)
    lease_seconds: int = Field(default=60, ge=10, le=3600)


class HeartbeatRequest(BaseModel):
    lease_token: str
    lease_seconds: int = Field(default=60, ge=10, le=3600)


class ExecuteRequest(BaseModel):
    lease_token: str = Field(min_length=1)


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    parent_task_id: str | None = None
    task_type: str
    payload: dict[str, Any]
    status: str
    priority: int
    attempt_count: int
    leased_by: str | None
    lease_token: str | None
    lease_version: int
    lease_expires_at: datetime | None
    next_retry_at: datetime | None
    heartbeat_at: datetime | None


def get_cipher(request: Request) -> SecretCipher:
    try:
        return SecretCipher(request.app.state.settings.secret_encryption_key)
    except SecretConfigurationError as error:
        raise HTTPException(503, str(error)) from error


def get_model_executor(request: Request) -> ModelExecutor:
    return request.app.state.model_executor


def get_execution_service(request: Request) -> ExecutionService:
    return request.app.state.execution_service


CipherDependency = Annotated[SecretCipher, Depends(get_cipher)]
ModelExecutorDependency = Annotated[ModelExecutor, Depends(get_model_executor)]
ExecutionServiceDependency = Annotated[ExecutionService, Depends(get_execution_service)]


@router.post("/claim", response_model=TaskResponse | None)
def claim(payload: ClaimRequest, service: ExecutionServiceDependency) -> dict[str, Any] | None:
    return service.claim(payload.worker_id, payload.lease_seconds)


@router.post("/tasks/{task_id}/heartbeat", response_model=TaskResponse)
def heartbeat(
    task_id: str,
    payload: HeartbeatRequest,
    service: ExecutionServiceDependency,
) -> dict[str, Any]:
    return service.heartbeat(task_id, payload.lease_token, payload.lease_seconds)


@router.post("/tasks/{task_id}/execute", response_model=TaskResponse)
def execute(
    task_id: str,
    payload: ExecuteRequest,
    service: ExecutionServiceDependency,
    cipher: CipherDependency,
    model_executor: ModelExecutorDependency,
) -> dict[str, Any]:
    _, task = service.execute_task(
        task_id,
        payload.lease_token,
        cipher=cipher,
        model_executor=model_executor,
    )
    return task


@router.post("/reclaim-expired")
def reclaim(service: ExecutionServiceDependency) -> dict[str, int]:
    return {"reclaimed": service.reclaim_expired()}


@router.get("/events")
async def worker_events(
    service: ExecutionServiceDependency,
    once: bool = False,
) -> StreamingResponse:
    """Stream task progress, active workers, and retry-exhaustion notices."""

    async def event_stream():
        while True:
            yield f"event: worker\ndata: {json.dumps(service.queue_snapshot(), default=str)}\n\n"
            if once:
                return
            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
