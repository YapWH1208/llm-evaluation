from __future__ import annotations
from collections.abc import Generator
import asyncio
import json
from datetime import datetime
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import TaskUnit
from app.db.mongo import MongoDocumentStore
from app.core.secrets import SecretCipher, SecretConfigurationError
from app.services.model_executor import ModelExecutor
from app.services.run_executor import RunExecutionError, execute_leased_text_task
from app.services.mongo_run_executor import MongoRunExecutionError, execute_mongo_leased_task
from app.services.task_queue import claim_task, heartbeat_task, reclaim_expired_leases
router=APIRouter(prefix="/api/v1/workers",tags=["workers"])
class ClaimRequest(BaseModel): worker_id:str=Field(min_length=1,max_length=128);lease_seconds:int=Field(default=60,ge=10,le=3600)
class HeartbeatRequest(BaseModel): lease_token:str;lease_seconds:int=Field(default=60,ge=10,le=3600)
class ExecuteRequest(BaseModel): lease_token:str=Field(min_length=1)
class TaskResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:str;run_id:str;task_type:str;payload:dict[str,Any];status:str;priority:int;attempt_count:int;leased_by:str|None;lease_token:str|None;lease_expires_at:datetime|None;next_retry_at:datetime|None;heartbeat_at:datetime|None
def get_session(request:Request)->Generator[Session|None,None,None]:
    if getattr(request.app.state,"document_store",None) is not None:
        yield None
        return
    session=request.app.state.database.get_session()
    try:yield session
    finally:session.close()
SessionDependency=Annotated[Session|None,Depends(get_session)]
def get_cipher(request:Request)->SecretCipher:
    try:return SecretCipher(request.app.state.settings.secret_encryption_key)
    except SecretConfigurationError as error:raise HTTPException(503,str(error)) from error
def get_model_executor(request:Request)->ModelExecutor:return request.app.state.model_executor
CipherDependency=Annotated[SecretCipher,Depends(get_cipher)]
ModelExecutorDependency=Annotated[ModelExecutor,Depends(get_model_executor)]

def get_document_store(request:Request)->MongoDocumentStore|None:return getattr(request.app.state,"document_store",None)
@router.post("/claim",response_model=TaskResponse|None)
def claim(payload:ClaimRequest,request:Request,session:SessionDependency)->TaskUnit|dict[str,Any]|None:
    store=get_document_store(request)
    if store is not None:return store.claim_task(worker_id=payload.worker_id,lease_seconds=payload.lease_seconds)
    assert session is not None
    settings = request.app.state.settings
    return claim_task(session,payload.worker_id,payload.lease_seconds,system_max_concurrency=settings.system_max_concurrency,worker_max_concurrency=settings.worker_max_concurrency)
@router.post("/tasks/{task_id}/heartbeat",response_model=TaskResponse)
def heartbeat(task_id:str,payload:HeartbeatRequest,request:Request,session:SessionDependency)->TaskUnit|dict[str,Any]:
    store=get_document_store(request)
    if store is not None:
        task=store.heartbeat_task(task_id=task_id,lease_token=payload.lease_token,lease_seconds=payload.lease_seconds)
        if task is None:raise HTTPException(409,"Task lease is no longer valid")
        return task
    assert session is not None
    task=heartbeat_task(session,task_id,payload.lease_token,payload.lease_seconds)
    if task is None:raise HTTPException(409,"Task lease is no longer valid")
    return task
@router.post("/tasks/{task_id}/execute",response_model=TaskResponse)
def execute(task_id:str,payload:ExecuteRequest,request:Request,session:SessionDependency,cipher:CipherDependency,model_executor:ModelExecutorDependency)->TaskUnit|dict[str,Any]:
    store=get_document_store(request)
    try:
        if store is not None:
            _,task=execute_mongo_leased_task(store,task_id=task_id,lease_token=payload.lease_token,cipher=cipher,model_executor=model_executor)
            return task
        assert session is not None
        _, task=execute_leased_text_task(session,task_id=task_id,lease_token=payload.lease_token,cipher=cipher,model_executor=model_executor)
        return task
    except (RunExecutionError,MongoRunExecutionError) as error:
        status_code=404 if str(error)=="Task not found." else 409
        raise HTTPException(status_code,str(error)) from error
    except SecretConfigurationError as error:
        raise HTTPException(503,str(error)) from error
@router.post("/reclaim-expired")
def reclaim(request:Request,session:SessionDependency)->dict[str,int]:
    store=get_document_store(request)
    if store is not None:return {"reclaimed":store.reclaim_expired_leases()}
    assert session is not None
    return {"reclaimed":reclaim_expired_leases(session)}


@router.get("/events")
async def worker_events(request: Request, once: bool = False) -> StreamingResponse:
    """Stream task progress, active workers, and retry-exhaustion notices."""

    async def event_stream():
        while True:
            yield f"event: worker\ndata: {json.dumps(_worker_event_payload(request), default=str)}\n\n"
            if once:
                return
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


def _worker_event_payload(request: Request) -> dict[str, Any]:
    store = get_document_store(request)
    if store is not None:
        tasks = store.list_documents("task_units", sort=[("updated_at", -1)])
        active = [task for task in tasks if task.get("status") in {"leased", "running"}]
        return {
            "queue": {"pending": sum(task.get("status") in {"pending", "retry_scheduled"} for task in tasks), "active": len(active)},
            "workers": sorted({str(task["leased_by"]) for task in active if task.get("leased_by")}),
            "errors": [{"task_id": task["id"], "run_id": task["run_id"], "retry_exhausted_reason": (task.get("payload") or {}).get("retry_exhausted_reason")} for task in tasks if task.get("status") == "failed"][:20],
        }
    with request.app.state.database.get_session() as session:
        tasks = list(session.scalars(select(TaskUnit).order_by(TaskUnit.updated_at.desc())))
        active = [task for task in tasks if task.status in {"leased", "running"}]
        return {
            "queue": {"pending": sum(task.status in {"pending", "retry_scheduled"} for task in tasks), "active": len(active)},
            "workers": sorted({str(task.leased_by) for task in active if task.leased_by}),
            "errors": [{"task_id": task.id, "run_id": task.run_id, "retry_exhausted_reason": (task.payload or {}).get("retry_exhausted_reason")} for task in tasks if task.status == "failed"][:20],
        }
