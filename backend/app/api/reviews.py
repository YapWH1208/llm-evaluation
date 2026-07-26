from __future__ import annotations
from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import HumanReview,SampleAttempt
from app.db.mongo import MongoDocumentStore
router=APIRouter(prefix="/api/v1/reviews",tags=["human review"])
class ReviewCreate(BaseModel):
    sample_attempt_id:str;reviewer_id:str=Field(min_length=1,max_length=128);rubric:dict[str,Any]|None=None;score:float|None=None;labels:list[Any]=Field(default_factory=list);notes:str|None=None
class ReviewResponse(ReviewCreate):
    model_config=ConfigDict(from_attributes=True)
    id:str;created_at:datetime
def get_session(request:Request)->Generator[Session|None,None,None]:
    if getattr(request.app.state,"document_store",None) is not None:
        yield None;return
    session=request.app.state.database.get_session()
    try:yield session
    finally:session.close()
SessionDependency=Annotated[Session|None,Depends(get_session)]
@router.post("",response_model=ReviewResponse)
def create(payload:ReviewCreate,request:Request,session:SessionDependency)->HumanReview|dict:
    store:MongoDocumentStore|None=getattr(request.app.state,"document_store",None)
    if store is not None:
        if store.get_document("sample_attempts",payload.sample_attempt_id) is None:raise HTTPException(404,"Sample attempt not found")
        return store.insert_document("human_reviews",{**payload.model_dump(),"created_at":datetime.now()})
    assert session is not None
    if session.get(SampleAttempt,payload.sample_attempt_id) is None:raise HTTPException(404,"Sample attempt not found")
    item=HumanReview(**payload.model_dump());session.add(item);session.commit();session.refresh(item);return item
@router.get("/sample/{sample_attempt_id}",response_model=list[ReviewResponse])
def list_for_sample(sample_attempt_id:str,request:Request,session:SessionDependency)->list[HumanReview|dict]:
    store:MongoDocumentStore|None=getattr(request.app.state,"document_store",None)
    if store is not None:return store.list_documents("human_reviews",query={"sample_attempt_id":sample_attempt_id},sort=[("created_at",1)])
    assert session is not None
    return list(session.scalars(select(HumanReview).where(HumanReview.sample_attempt_id==sample_attempt_id).order_by(HumanReview.created_at)))
