from __future__ import annotations
from collections.abc import Generator
from datetime import datetime, timezone
import hashlib
import secrets
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db.models import AuditEvent, User, UserRole
from app.db.mongo import MongoDocumentStore

router=APIRouter(prefix="/api/v1",tags=["administration"])
class UserCreate(BaseModel): email:str=Field(min_length=3,max_length=320);display_name:str=Field(min_length=1,max_length=200);role:UserRole=UserRole.VIEWER;max_concurrency:int|None=Field(default=None,ge=1,le=1000)
class UserResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:str;email:str;display_name:str;role:str;status:str;max_concurrency:int|None=None;created_at:datetime
class UserCreateResponse(UserResponse): api_token:str
class AuditResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:str;actor_id:str|None;action:str;entity_type:str;entity_id:str|None;details:dict[str,Any]|None;created_at:datetime
def get_session(request:Request)->Generator[Session|None,None,None]:
    if getattr(request.app.state,"document_store",None) is not None:
        yield None;return
    session=request.app.state.database.get_session()
    try:yield session
    finally:session.close()
SessionDependency=Annotated[Session|None,Depends(get_session)]
@router.post("/users",response_model=UserCreateResponse,status_code=status.HTTP_201_CREATED)
def create_user(payload:UserCreate,request:Request,session:SessionDependency)->UserCreateResponse:
    api_token=f"lle_{secrets.token_urlsafe(32)}"
    store:MongoDocumentStore|None=getattr(request.app.state,"document_store",None)
    if store is not None:
        email=payload.email.lower()
        if store.list_documents("users",query={"email":email}):raise HTTPException(409,"User email already exists")
        user=store.insert_document("users",{"email":email,"display_name":payload.display_name,"role":payload.role.value,"status":"active","max_concurrency":payload.max_concurrency,"api_token_hash":hashlib.sha256(api_token.encode()).hexdigest(),"created_at":datetime.now(timezone.utc)})
        return UserCreateResponse(**user,api_token=api_token)
    assert session is not None
    user=User(email=payload.email.lower(),display_name=payload.display_name,role=payload.role.value,max_concurrency=payload.max_concurrency,api_token_hash=hashlib.sha256(api_token.encode()).hexdigest());session.add(user)
    try:session.flush()
    except IntegrityError as error:session.rollback();raise HTTPException(409,"User email already exists") from error
    session.add(AuditEvent(actor_id=getattr(request.state,"actor_id",None),action="user.created",entity_type="user",entity_id=user.id,details={"email":user.email,"role":user.role}));session.commit();session.refresh(user)
    return UserCreateResponse(**UserResponse.model_validate(user).model_dump(), api_token=api_token)
@router.get("/users",response_model=list[UserResponse])
def list_users(request:Request,session:SessionDependency)->list[User|dict]:
    store:MongoDocumentStore|None=getattr(request.app.state,"document_store",None)
    if store is not None:return store.list_documents("users",sort=[("created_at",1)])
    assert session is not None
    return list(session.scalars(select(User).order_by(User.created_at)))
@router.get("/audit-events",response_model=list[AuditResponse])
def list_audit_events(request:Request,session:SessionDependency,limit:int=100)->list[AuditEvent|dict]:
    store:MongoDocumentStore|None=getattr(request.app.state,"document_store",None)
    if store is not None:return store.list_documents("audit_events",sort=[("created_at",-1)])[:min(max(limit,1),500)]
    assert session is not None
    return list(session.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(min(max(limit,1),500))))
