from __future__ import annotations
from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db.models import AuditEvent, User, UserRole

router=APIRouter(prefix="/api/v1",tags=["administration"])
class UserCreate(BaseModel): email:str=Field(min_length=3,max_length=320);display_name:str=Field(min_length=1,max_length=200);role:UserRole=UserRole.VIEWER
class UserResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:str;email:str;display_name:str;role:str;status:str;created_at:datetime
class AuditResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:str;actor_id:str|None;action:str;entity_type:str;entity_id:str|None;details:dict[str,Any]|None;created_at:datetime
def get_session(request:Request)->Generator[Session,None,None]:
    session=request.app.state.database.get_session()
    try:yield session
    finally:session.close()
SessionDependency=Annotated[Session,Depends(get_session)]
@router.post("/users",response_model=UserResponse,status_code=status.HTTP_201_CREATED)
def create_user(payload:UserCreate,session:SessionDependency)->User:
    user=User(email=payload.email.lower(),display_name=payload.display_name,role=payload.role.value);session.add(user)
    try:session.flush()
    except IntegrityError as error:session.rollback();raise HTTPException(409,"User email already exists") from error
    session.add(AuditEvent(action="user.created",entity_type="user",entity_id=user.id,details={"email":user.email,"role":user.role}));session.commit();session.refresh(user);return user
@router.get("/users",response_model=list[UserResponse])
def list_users(session:SessionDependency)->list[User]:return list(session.scalars(select(User).order_by(User.created_at)))
@router.get("/audit-events",response_model=list[AuditResponse])
def list_audit_events(session:SessionDependency,limit:int=100)->list[AuditEvent]:return list(session.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(min(max(limit,1),500))))
