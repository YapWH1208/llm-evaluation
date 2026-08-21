from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from app.modules.evaluations.queue_service import QueueService


router = APIRouter(prefix="/api/v1/tasks", tags=["task queue"])


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
    lease_expires_at: datetime | None
    next_retry_at: datetime | None
    heartbeat_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskPriorityUpdate(BaseModel):
    priority: Annotated[int, Field(ge=-1000, le=1000)]


def get_queue_service(request: Request) -> QueueService:
    return request.app.state.queue_service


QueueServiceDependency = Annotated[QueueService, Depends(get_queue_service)]


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    service: QueueServiceDependency,
    run_id: str | None = None,
    task_status: str | None = None,
    offset: int = 0,
    limit: int = 200,
) -> list[dict[str, Any]]:
    return service.list_tasks(
        run_id=run_id,
        status=task_status,
        offset=offset,
        limit=limit,
    )


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task_priority(
    task_id: str,
    payload: TaskPriorityUpdate,
    service: QueueServiceDependency,
) -> dict[str, Any]:
    return service.update_priority(task_id, payload.priority)
