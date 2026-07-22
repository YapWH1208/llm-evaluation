from __future__ import annotations
from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import HumanReview,SampleAttempt
router=APIRouter(prefix="/api/v1/reviews",tags=["human review"])
class ReviewCreate(BaseModel):
    sample_attempt_id:str;reviewer_id:str=Field(min_length=1,max_length=128);rubric:dict[str,Any]|None=None;score:float|None=None;labels:list[Any]=Field(default_factory=list);notes:str|None=None
class ReviewResponse(ReviewCreate):
    model_config=ConfigDict(from_attributes=True)
    id:str;created_at:datetime
def get_session(request:Request)->Generator[Session,None,None]:
    session=request.app.state.database.get_session()
    try:yield session
    finally:session.close()
SessionDependency=Annotated[Session,Depends(get_session)]
@router.post("",response_model=ReviewResponse)
def create(payload:ReviewCreate,session:SessionDependency)->HumanReview:
    if session.get(SampleAttempt,payload.sample_attempt_id) is None:raise HTTPException(404,"Sample attempt not found")
    item=HumanReview(**payload.model_dump());session.add(item);session.commit();session.refresh(item);return item
@router.get("/sample/{sample_attempt_id}",response_model=list[ReviewResponse])
def list_for_sample(sample_attempt_id:str,session:SessionDependency)->list[HumanReview]:return list(session.scalars(select(HumanReview).where(HumanReview.sample_attempt_id==sample_attempt_id).order_by(HumanReview.created_at)))
