from __future__ import annotations
from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db.models import PromptPackage
from app.db.mongo import MongoDocumentStore
from app.services.prompt_templates import PromptTemplateError, validate_template

router = APIRouter(prefix="/api/v1/prompt-packages", tags=["prompt packages"])
class PromptPackageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200); version: str = Field(min_length=1, max_length=64)
    prompt_type: Literal["official", "platform_default", "user_custom", "benchmark_variant", "language_specific"] = "user_custom"; system_message: str | None = None; user_template: str = Field(min_length=1)
    few_shot_examples: list[Any] = Field(default_factory=list); output_format: dict[str, Any] | None = None
    response_parser: dict[str, Any] | None = None; scoring_rule: dict[str, Any] | None = None; change_log: str | None = None

    @field_validator("user_template")
    @classmethod
    def validate_user_template(cls, value: str) -> str:
        try:
            validate_template(value)
        except PromptTemplateError as error:
            raise ValueError(str(error)) from error
        return value
class PromptPackageResponse(PromptPackageCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str; created_at: datetime
def get_session(request: Request) -> Generator[Session | None, None, None]:
    if getattr(request.app.state, "document_store", None) is not None:
        yield None
        return
    session = request.app.state.database.get_session()
    try: yield session
    finally: session.close()
SessionDependency = Annotated[Session | None, Depends(get_session)]

def get_document_store(request: Request) -> MongoDocumentStore | None:
    return getattr(request.app.state, "document_store", None)
@router.post("", response_model=PromptPackageResponse, status_code=status.HTTP_201_CREATED)
def create_prompt_package(payload: PromptPackageCreate, request: Request, session: SessionDependency) -> PromptPackage | dict[str, Any]:
    store = get_document_store(request)
    if store is not None:
        if store.list_documents("prompt_packages", query={"name": payload.name, "version": payload.version}):
            raise HTTPException(409, "Prompt package name and version already exist")
        return store.insert_document("prompt_packages", {**payload.model_dump(), "created_at": datetime.now()})
    assert session is not None
    item = PromptPackage(**payload.model_dump()); session.add(item)
    try: session.commit()
    except IntegrityError as error:
        session.rollback(); raise HTTPException(409, "Prompt package name and version already exist") from error
    session.refresh(item); return item
@router.get("", response_model=list[PromptPackageResponse])
def list_prompt_packages(request: Request, session: SessionDependency) -> list[PromptPackage | dict[str, Any]]:
    store = get_document_store(request)
    if store is not None:
        return store.list_documents("prompt_packages", sort=[("created_at", -1)])
    assert session is not None
    return list(session.scalars(select(PromptPackage).order_by(PromptPackage.created_at.desc())))
