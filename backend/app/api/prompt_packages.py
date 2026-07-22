from __future__ import annotations
from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db.models import PromptPackage

router = APIRouter(prefix="/api/v1/prompt-packages", tags=["prompt packages"])
class PromptPackageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200); version: str = Field(min_length=1, max_length=64)
    prompt_type: str = "user_custom"; system_message: str | None = None; user_template: str = Field(min_length=1)
    few_shot_examples: list[Any] = Field(default_factory=list); output_format: dict[str, Any] | None = None
    response_parser: dict[str, Any] | None = None; scoring_rule: dict[str, Any] | None = None; change_log: str | None = None
class PromptPackageResponse(PromptPackageCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str; created_at: datetime
def get_session(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.database.get_session()
    try: yield session
    finally: session.close()
SessionDependency = Annotated[Session, Depends(get_session)]
@router.post("", response_model=PromptPackageResponse, status_code=status.HTTP_201_CREATED)
def create_prompt_package(payload: PromptPackageCreate, session: SessionDependency) -> PromptPackage:
    item = PromptPackage(**payload.model_dump()); session.add(item)
    try: session.commit()
    except IntegrityError as error:
        session.rollback(); raise HTTPException(409, "Prompt package name and version already exist") from error
    session.refresh(item); return item
@router.get("", response_model=list[PromptPackageResponse])
def list_prompt_packages(session: SessionDependency) -> list[PromptPackage]:
    return list(session.scalars(select(PromptPackage).order_by(PromptPackage.created_at.desc())))
