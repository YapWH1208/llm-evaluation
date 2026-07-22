from __future__ import annotations
from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.db.models import TaskUnit
from app.core.secrets import SecretCipher, SecretConfigurationError
from app.services.model_executor import ModelExecutor
from app.services.run_executor import RunExecutionError, execute_leased_text_task
from app.services.task_queue import claim_task, heartbeat_task, reclaim_expired_leases
router=APIRouter(prefix="/api/v1/workers",tags=["workers"])
class ClaimRequest(BaseModel): worker_id:str=Field(min_length=1,max_length=128);lease_seconds:int=Field(default=60,ge=10,le=3600)
class HeartbeatRequest(BaseModel): lease_token:str;lease_seconds:int=Field(default=60,ge=10,le=3600)
class ExecuteRequest(BaseModel): lease_token:str=Field(min_length=1)
class TaskResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:str;run_id:str;task_type:str;payload:dict[str,Any];status:str;priority:int;attempt_count:int;leased_by:str|None;lease_token:str|None;lease_expires_at:datetime|None;next_retry_at:datetime|None;heartbeat_at:datetime|None
def get_session(request:Request)->Generator[Session,None,None]:
    session=request.app.state.database.get_session()
    try:yield session
    finally:session.close()
SessionDependency=Annotated[Session,Depends(get_session)]
def get_cipher(request:Request)->SecretCipher:
    try:return SecretCipher(request.app.state.settings.secret_encryption_key)
    except SecretConfigurationError as error:raise HTTPException(503,str(error)) from error
def get_model_executor(request:Request)->ModelExecutor:return request.app.state.model_executor
CipherDependency=Annotated[SecretCipher,Depends(get_cipher)]
ModelExecutorDependency=Annotated[ModelExecutor,Depends(get_model_executor)]
@router.post("/claim",response_model=TaskResponse|None)
def claim(payload:ClaimRequest,session:SessionDependency)->TaskUnit|None:return claim_task(session,payload.worker_id,payload.lease_seconds)
@router.post("/tasks/{task_id}/heartbeat",response_model=TaskResponse)
def heartbeat(task_id:str,payload:HeartbeatRequest,session:SessionDependency)->TaskUnit:
    task=heartbeat_task(session,task_id,payload.lease_token,payload.lease_seconds)
    if task is None:raise HTTPException(409,"Task lease is no longer valid")
    return task
@router.post("/tasks/{task_id}/execute",response_model=TaskResponse)
def execute(task_id:str,payload:ExecuteRequest,session:SessionDependency,cipher:CipherDependency,model_executor:ModelExecutorDependency)->TaskUnit:
    try:
        _, task=execute_leased_text_task(session,task_id=task_id,lease_token=payload.lease_token,cipher=cipher,model_executor=model_executor)
        return task
    except RunExecutionError as error:
        status_code=404 if str(error)=="Task not found." else 409
        raise HTTPException(status_code,str(error)) from error
    except SecretConfigurationError as error:
        raise HTTPException(503,str(error)) from error
@router.post("/reclaim-expired")
def reclaim(session:SessionDependency)->dict[str,int]:return {"reclaimed":reclaim_expired_leases(session)}
