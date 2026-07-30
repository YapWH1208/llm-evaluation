from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import TaskStatus, TaskUnit
from app.db.mongo import MongoDocumentStore


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


def get_session(request: Request) -> Generator[Session | None, None, None]:
    if getattr(request.app.state,"document_store",None) is not None:
        yield None
        return
    session = request.app.state.database.get_session()
    try:
        yield session
    finally:
        session.close()


SessionDependency = Annotated[Session | None, Depends(get_session)]


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    request: Request,
    session: SessionDependency,
    run_id: str | None = None,
    task_status: str | None = None,
    offset: int = 0,
    limit: int = 200,
) -> list[TaskUnit | dict[str, Any]]:
    store: MongoDocumentStore | None=getattr(request.app.state,"document_store",None)
    if store is not None:
        query={}
        if run_id:query["run_id"]=run_id
        if task_status:query["status"]=task_status
        return store.list_documents(
            "task_units",
            query=query,
            sort=[("priority", -1), ("created_at", 1)],
            offset=max(0, offset),
            limit=min(max(1, limit), 1000),
        )
    assert session is not None
    query = select(TaskUnit)
    if run_id:
        query = query.where(TaskUnit.run_id == run_id)
    if task_status:
        query = query.where(TaskUnit.status == task_status)
    return list(
        session.scalars(
            query.order_by(TaskUnit.priority.desc(), TaskUnit.created_at).offset(max(0, offset)).limit(min(max(1, limit), 1000))
        )
    )


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task_priority(
    task_id: str,
    payload: TaskPriorityUpdate,
    request: Request,
    session: SessionDependency,
) -> TaskUnit | dict[str, Any]:
    store: MongoDocumentStore | None=getattr(request.app.state,"document_store",None)
    if store is not None:
        task=store.get_document("task_units",task_id)
        if task is None:raise HTTPException(404,"Task not found")
        if task["status"] not in {TaskStatus.PENDING.value,TaskStatus.RETRY_SCHEDULED.value}:raise HTTPException(409,"Only queued tasks can have their priority adjusted")
        updated=store.update_document("task_units",task_id,{"priority":payload.priority});assert updated is not None;return updated
    assert session is not None
    task = session.get(TaskUnit, task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    if task.status not in {TaskStatus.PENDING.value, TaskStatus.RETRY_SCHEDULED.value}:
        raise HTTPException(409, "Only queued tasks can have their priority adjusted")
    task.priority = payload.priority
    session.commit()
    session.refresh(task)
    return task
