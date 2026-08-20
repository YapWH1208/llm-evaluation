from __future__ import annotations
from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db.models import EvaluationRun, EvaluationSuite, PromptPackage
from app.db.mongo import MongoDocumentStore
from app.modules.benchmarks.prompts import PromptTemplateError, validate_template
from app.modules.benchmarks.scoring import ScoringError, validate_scoring_rule

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

    @field_validator("scoring_rule")
    @classmethod
    def validate_scoring_rule_config(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return value
        try:
            validate_scoring_rule(value)
        except ScoringError as error:
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


@router.put("/{prompt_package_id}", response_model=PromptPackageResponse)
def update_prompt_package(
    prompt_package_id: str,
    payload: PromptPackageCreate,
    request: Request,
    session: SessionDependency,
) -> PromptPackage | dict[str, Any]:
    store = get_document_store(request)
    if store is not None:
        if store.get_document("prompt_packages", prompt_package_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Prompt package not found")
        duplicates = store.list_documents(
            "prompt_packages",
            query={"name": payload.name, "version": payload.version},
        )
        if any(str(item["id"]) != prompt_package_id for item in duplicates):
            raise HTTPException(status.HTTP_409_CONFLICT, "Prompt package name and version already exist")
        updated = store.update_document("prompt_packages", prompt_package_id, payload.model_dump())
        assert updated is not None
        return updated

    assert session is not None
    prompt_package = session.get(PromptPackage, prompt_package_id)
    if prompt_package is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prompt package not found")
    existing = session.scalar(
        select(PromptPackage).where(
            PromptPackage.name == payload.name,
            PromptPackage.version == payload.version,
        )
    )
    if existing is not None and existing.id != prompt_package_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Prompt package name and version already exist")
    for field, value in payload.model_dump().items():
        setattr(prompt_package, field, value)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Prompt package name and version already exist") from error
    session.refresh(prompt_package)
    return prompt_package


@router.delete("/{prompt_package_id}", response_model=PromptPackageResponse)
def delete_prompt_package(
    prompt_package_id: str,
    request: Request,
    session: SessionDependency,
) -> PromptPackage | dict[str, Any]:
    store = get_document_store(request)
    if store is not None:
        prompt_package = store.get_document("prompt_packages", prompt_package_id)
        if prompt_package is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Prompt package not found")
        _ensure_mongo_prompt_package_is_unreferenced(store, prompt_package_id)
        store.delete_document("prompt_packages", prompt_package_id)
        return prompt_package

    assert session is not None
    prompt_package = session.get(PromptPackage, prompt_package_id)
    if prompt_package is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prompt package not found")
    _ensure_prompt_package_is_unreferenced(session, prompt_package_id)
    session.delete(prompt_package)
    session.commit()
    return prompt_package


def _ensure_prompt_package_is_unreferenced(session: Session, prompt_package_id: str) -> None:
    if session.scalar(
        select(EvaluationRun.id)
        .where(EvaluationRun.prompt_package_id == prompt_package_id)
        .limit(1)
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "Prompt package is referenced by an evaluation run")
    if any(_suite_references_prompt_package(suite, prompt_package_id) for suite in session.scalars(select(EvaluationSuite))):
        raise HTTPException(status.HTTP_409_CONFLICT, "Prompt package is referenced by an evaluation suite")


def _ensure_mongo_prompt_package_is_unreferenced(store: MongoDocumentStore, prompt_package_id: str) -> None:
    if store.list_documents("evaluation_runs", query={"prompt_package_id": prompt_package_id}, limit=1):
        raise HTTPException(status.HTTP_409_CONFLICT, "Prompt package is referenced by an evaluation run")
    if any(
        _suite_references_prompt_package(suite, prompt_package_id)
        for suite in store.list_documents("evaluation_suites")
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "Prompt package is referenced by an evaluation suite")


def _suite_references_prompt_package(suite: EvaluationSuite | dict[str, Any], prompt_package_id: str) -> bool:
    default_overrides = (
        suite.get("default_prompt_overrides")
        if isinstance(suite, dict)
        else suite.default_prompt_overrides
    )
    if isinstance(default_overrides, dict) and any(value == prompt_package_id for value in default_overrides.values()):
        return True
    benchmark_list = suite.get("benchmark_list") if isinstance(suite, dict) else suite.benchmark_list
    return isinstance(benchmark_list, list) and any(
        isinstance(selection, dict) and selection.get("prompt_package_id") == prompt_package_id
        for selection in benchmark_list
    )
