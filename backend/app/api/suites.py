from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import EvaluationSuite
from app.db.mongo import MongoDocumentStore
from app.services.evaluation_runs import RunCreationError, create_benchmark_run
from app.services.mongo_run_executor import MongoRunExecutionError, create_mongo_benchmark_run


router = APIRouter(prefix="/api/v1/evaluation-suites", tags=["evaluation suites"])


class EvaluationSuiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    benchmark_list: list[dict[str, Any]] = Field(min_length=1)
    default_prompt_overrides: dict[str, Any] = Field(default_factory=dict)
    default_request_body: dict[str, Any] = Field(default_factory=dict)
    weight_configuration: dict[str, Any] = Field(default_factory=dict)
    version: str = Field(default="1", min_length=1, max_length=64)


class EvaluationSuiteUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=4000)
    benchmark_list: list[dict[str, Any]] | None = Field(default=None, min_length=1)
    default_prompt_overrides: dict[str, Any] | None = None
    default_request_body: dict[str, Any] | None = None
    weight_configuration: dict[str, Any] | None = None


class EvaluationSuiteResponse(EvaluationSuiteCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_by: str | None
    created_at: datetime


class SuiteRunCreate(BaseModel):
    model_endpoint_id: str
    sample_limit: int | None = Field(default=None, ge=1, le=3)


def get_session(request: Request) -> Generator[Session | None, None, None]:
    if getattr(request.app.state, "document_store", None) is not None:
        yield None
        return
    session = request.app.state.database.get_session()
    try:
        yield session
    finally:
        session.close()


SessionDependency = Annotated[Session | None, Depends(get_session)]


@router.post("", response_model=EvaluationSuiteResponse, status_code=status.HTTP_201_CREATED)
def create_suite(payload: EvaluationSuiteCreate, request: Request, session: SessionDependency) -> EvaluationSuite | dict[str, Any]:
    created_by = getattr(request.state, "actor_id", None)
    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        if store.list_documents("evaluation_suites", query={"name": payload.name, "version": payload.version}):
            raise HTTPException(status.HTTP_409_CONFLICT, "Suite name and version already exist")
        return store.insert_document("evaluation_suites", {**payload.model_dump(), "created_by": created_by, "created_at": datetime.now(timezone.utc)})
    assert session is not None
    suite = EvaluationSuite(**payload.model_dump(), created_by=created_by)
    session.add(suite)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Suite name and version already exist") from error
    session.refresh(suite)
    return suite


@router.get("", response_model=list[EvaluationSuiteResponse])
def list_suites(request: Request, session: SessionDependency) -> list[EvaluationSuite | dict[str, Any]]:
    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        return store.list_documents("evaluation_suites", sort=[("created_at", -1)])
    assert session is not None
    return list(session.scalars(select(EvaluationSuite).order_by(EvaluationSuite.created_at.desc())))


@router.get("/{suite_id}", response_model=EvaluationSuiteResponse)
def get_suite(suite_id: str, request: Request, session: SessionDependency) -> EvaluationSuite | dict[str, Any]:
    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        suite = store.get_document("evaluation_suites", suite_id)
    else:
        assert session is not None
        suite = session.get(EvaluationSuite, suite_id)
    if suite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evaluation suite not found")
    return suite


@router.patch("/{suite_id}", response_model=EvaluationSuiteResponse)
def update_suite(suite_id: str, payload: EvaluationSuiteUpdate, request: Request, session: SessionDependency) -> EvaluationSuite | dict[str, Any]:
    values = payload.model_dump(exclude_unset=True)
    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    if store is not None:
        if store.get_document("evaluation_suites", suite_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Evaluation suite not found")
        updated = store.update_document("evaluation_suites", suite_id, values)
        assert updated is not None
        return updated
    assert session is not None
    suite = session.get(EvaluationSuite, suite_id)
    if suite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evaluation suite not found")
    for field, value in values.items():
        setattr(suite, field, value)
    session.commit()
    session.refresh(suite)
    return suite


@router.post("/{suite_id}/runs", status_code=status.HTTP_201_CREATED)
def create_suite_runs(suite_id: str, payload: SuiteRunCreate, request: Request, session: SessionDependency) -> list[dict[str, Any]]:
    store: MongoDocumentStore | None = getattr(request.app.state, "document_store", None)
    suite: EvaluationSuite | dict[str, Any] | None = store.get_document("evaluation_suites", suite_id) if store is not None else session.get(EvaluationSuite, suite_id)  # type: ignore[union-attr]
    if suite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evaluation suite not found")
    values = suite if isinstance(suite, dict) else {
        "id": suite.id, "name": suite.name, "version": suite.version, "benchmark_list": suite.benchmark_list,
        "default_prompt_overrides": suite.default_prompt_overrides, "default_request_body": suite.default_request_body,
        "weight_configuration": suite.weight_configuration,
    }
    results: list[dict[str, Any]] = []
    try:
        for selection in values["benchmark_list"]:
            if not isinstance(selection, dict) or not isinstance(selection.get("benchmark_id"), str):
                raise RunCreationError("Suite benchmarks require benchmark_id entries.")
            benchmark_id = selection["benchmark_id"]
            benchmark_version = str(selection.get("version", "1.0.0"))
            prompt_package_id = selection.get("prompt_package_id")
            if prompt_package_id is not None and not isinstance(prompt_package_id, str):
                raise RunCreationError("Suite prompt_package_id must be a string.")
            snapshot = {"id": values["id"], "name": values["name"], "version": values["version"], "default_request_body": values["default_request_body"], "weight_configuration": values["weight_configuration"], "selection": selection}
            if store is not None:
                run = create_mongo_benchmark_run(store, model_endpoint_id=payload.model_endpoint_id, sample_limit=payload.sample_limit, prompt_package_id=prompt_package_id, benchmark_id=benchmark_id, benchmark_version=benchmark_version, suite_id=str(values["id"]), suite_snapshot=snapshot)
            else:
                assert session is not None
                run = create_benchmark_run(session, model_endpoint_id=payload.model_endpoint_id, sample_limit=payload.sample_limit, prompt_package_id=prompt_package_id, benchmark_id=benchmark_id, benchmark_version=benchmark_version, suite_id=str(values["id"]), suite_snapshot=snapshot)
            results.append(run if isinstance(run, dict) else {"id": run.id, "suite_id": run.suite_id, "benchmark_id": run.benchmark_id, "benchmark_version": run.benchmark_version, "status": run.status})
    except (RunCreationError, MongoRunExecutionError) as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    return results
