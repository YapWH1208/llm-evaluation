from __future__ import annotations

import asyncio
import json
from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.secrets import SecretCipher, SecretConfigurationError
from app.db import EvaluationRun, SampleAttempt, RunStatus, SampleAttemptStatus, TaskStatus, TaskUnit
from app.db.mongo import MongoDocumentStore
from app.services.evaluation_runs import RunCreationError, create_benchmark_run
from app.services.custom_runs import CustomRunError, create_custom_multimodal_run
from app.services.model_executor import ModelExecutor
from app.services.run_analysis import build_run_summary
from app.services.run_executor import RunExecutionError, execute_queued_text_run
from app.services.run_operations import RunOperationError, clone_run, retry_failed_samples
from app.services.mongo_run_executor import (
    MongoRunExecutionError,
    build_mongo_run_summary,
    clone_mongo_run,
    create_mongo_custom_multimodal_run,
    create_mongo_benchmark_run,
    execute_mongo_queued_run,
    retry_failed_mongo_samples,
)

router = APIRouter(prefix="/api/v1/evaluation-runs", tags=["evaluation runs"])


class EvaluationRunCreate(BaseModel):
    model_endpoint_id: str
    sample_limit: Annotated[int | None, Field(ge=1, le=3)] = None
    prompt_package_id: str | None = None
    benchmark_id: str = "text-quick-check"
    benchmark_version: str = "1.0.0"
    request_body_override: dict[str, Any] = Field(default_factory=dict)
    max_concurrency: Annotated[int | None, Field(ge=1, le=1000)] = None


class CustomMultimodalRunCreate(BaseModel):
    model_endpoint_id: str
    sample_id: Annotated[str, Field(min_length=1, max_length=255)] = "custom-sample"
    messages: list[dict[str, Any]]
    reference_answer: Annotated[str, Field(min_length=1, max_length=10000)]
    max_concurrency: Annotated[int | None, Field(ge=1, le=1000)] = None


class EvaluationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    model_endpoint_id: str
    prompt_package_id: str | None
    suite_id: str | None = None
    created_by: str | None = None
    max_concurrency: int | None = None
    benchmark_id: str
    benchmark_version: str
    configuration_snapshot: dict[str, Any]
    status: str
    total_samples: int
    completed_samples: int
    successful_samples: int
    failed_samples: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class SampleAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sample_id: str
    attempt_number: int
    input_snapshot: dict[str, Any]
    reference_snapshot: dict[str, Any]
    request_snapshot: dict[str, Any] | None
    raw_response: str | None
    parsed_prediction: str | None
    score: float | None
    latency_ms: float | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: float | None
    error_type: str | None
    error_message: str | None
    status: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


def get_session(request: Request) -> Generator[Session | None, None, None]:
    if getattr(request.app.state, "document_store", None) is not None:
        yield None
        return
    session = request.app.state.database.get_session()
    try:
        yield session
    finally:
        session.close()


def get_cipher(request: Request) -> SecretCipher:
    try:
        return SecretCipher(request.app.state.settings.secret_encryption_key)
    except SecretConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


def get_model_executor(request: Request) -> ModelExecutor:
    return request.app.state.model_executor


SessionDependency = Annotated[Session | None, Depends(get_session)]
CipherDependency = Annotated[SecretCipher, Depends(get_cipher)]
ModelExecutorDependency = Annotated[ModelExecutor, Depends(get_model_executor)]


def get_document_store(request: Request) -> MongoDocumentStore | None:
    return getattr(request.app.state, "document_store", None)


@router.post("", response_model=EvaluationRunResponse, status_code=status.HTTP_201_CREATED)
def create_evaluation_run(
    payload: EvaluationRunCreate,
    request: Request,
    session: SessionDependency,
) -> EvaluationRun | dict[str, Any]:
    store = get_document_store(request)
    try:
        if store is not None:
            return create_mongo_benchmark_run(
                store,
                model_endpoint_id=payload.model_endpoint_id,
                sample_limit=payload.sample_limit,
                prompt_package_id=payload.prompt_package_id,
                benchmark_id=payload.benchmark_id,
                benchmark_version=payload.benchmark_version,
                request_body_override=payload.request_body_override,
                created_by=getattr(request.state, "actor_id", None),
                max_concurrency=payload.max_concurrency,
            )
        assert session is not None
        return create_benchmark_run(
            session,
            model_endpoint_id=payload.model_endpoint_id,
            sample_limit=payload.sample_limit,
            prompt_package_id=payload.prompt_package_id,
            benchmark_id=payload.benchmark_id,
            benchmark_version=payload.benchmark_version,
            request_body_override=payload.request_body_override,
            created_by=getattr(request.state, "actor_id", None),
            max_concurrency=payload.max_concurrency,
        )
    except (RunCreationError, MongoRunExecutionError) as error:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if str(error) == "Model endpoint not found."
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=status_code, detail=str(error)) from error


@router.post("/custom-multimodal", response_model=EvaluationRunResponse, status_code=status.HTTP_201_CREATED)
def create_custom_run(
    payload: CustomMultimodalRunCreate,
    request: Request,
    session: SessionDependency,
) -> EvaluationRun:
    store = get_document_store(request)
    if store is not None:
        try:
            return create_mongo_custom_multimodal_run(store, data_root=request.app.state.settings.data_root, model_endpoint_id=payload.model_endpoint_id, sample_id=payload.sample_id, messages=payload.messages, reference_answer=payload.reference_answer, created_by=getattr(request.state, "actor_id", None), max_concurrency=payload.max_concurrency)
        except MongoRunExecutionError as error:
            status_code = status.HTTP_404_NOT_FOUND if str(error) in {"Model endpoint not found.", "Referenced media asset was not found."} else status.HTTP_409_CONFLICT
            raise HTTPException(status_code, str(error)) from error
    assert session is not None
    try:
        return create_custom_multimodal_run(
            session,
            data_root=request.app.state.settings.data_root,
            model_endpoint_id=payload.model_endpoint_id,
            sample_id=payload.sample_id,
            messages=payload.messages,
            reference_answer=payload.reference_answer,
            created_by=getattr(request.state, "actor_id", None),
            max_concurrency=payload.max_concurrency,
        )
    except CustomRunError as error:
        status_code = status.HTTP_404_NOT_FOUND if str(error) in {"Model endpoint not found.", "Referenced media asset was not found."} else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=str(error)) from error


@router.get("", response_model=list[EvaluationRunResponse])
def list_evaluation_runs(request: Request, session: SessionDependency) -> list[EvaluationRun | dict[str, Any]]:
    store = get_document_store(request)
    if store is not None:
        return store.list_documents("evaluation_runs", sort=[("created_at", -1)])
    assert session is not None
    return list(session.scalars(select(EvaluationRun).order_by(EvaluationRun.created_at.desc())))

@router.post("/{run_id}/pause", response_model=EvaluationRunResponse)
def pause_evaluation_run(run_id: str, request: Request, session: SessionDependency) -> EvaluationRun | dict[str, Any]:
    store = get_document_store(request)
    if store is not None:
        run = store.get_document("evaluation_runs", run_id)
        if run is None: raise HTTPException(404, "Evaluation run not found")
        if run["status"] not in {RunStatus.QUEUED.value, RunStatus.RUNNING.value}: raise HTTPException(409, "Run cannot be paused in its current state")
        for task in store.list_documents("task_units", query={"run_id": run_id}):
            if task["status"] in {TaskStatus.PENDING.value, TaskStatus.RUNNING.value}:
                store.update_document("task_units", str(task["id"]), {"status": TaskStatus.CANCELLED.value})
        updated = store.update_document("evaluation_runs", run_id, {"status": RunStatus.PAUSED.value})
        assert updated is not None
        return updated
    assert session is not None
    run = session.get(EvaluationRun, run_id)
    if run is None: raise HTTPException(404, "Evaluation run not found")
    if run.status not in {RunStatus.QUEUED.value, RunStatus.RUNNING.value}: raise HTTPException(409, "Run cannot be paused in its current state")
    run.status = RunStatus.PAUSED.value
    session.query(TaskUnit).filter(TaskUnit.run_id == run.id, TaskUnit.status.in_([TaskStatus.PENDING.value, TaskStatus.RUNNING.value])).update({TaskUnit.status: TaskStatus.CANCELLED.value})
    session.commit(); session.refresh(run); return run

@router.post("/{run_id}/resume", response_model=EvaluationRunResponse)
def resume_evaluation_run(run_id: str, request: Request, session: SessionDependency) -> EvaluationRun | dict[str, Any]:
    store = get_document_store(request)
    if store is not None:
        run = store.get_document("evaluation_runs", run_id)
        if run is None: raise HTTPException(404, "Evaluation run not found")
        if run["status"] != RunStatus.PAUSED.value: raise HTTPException(409, "Only paused runs can be resumed")
        for task in store.list_documents("task_units", query={"run_id": run_id}):
            if task["status"] == TaskStatus.CANCELLED.value:
                store.update_document("task_units", str(task["id"]), {"status": TaskStatus.PENDING.value})
        updated = store.update_document("evaluation_runs", run_id, {"status": RunStatus.QUEUED.value})
        assert updated is not None
        return updated
    assert session is not None
    run = session.get(EvaluationRun, run_id)
    if run is None: raise HTTPException(404, "Evaluation run not found")
    if run.status != RunStatus.PAUSED.value: raise HTTPException(409, "Only paused runs can be resumed")
    run.status = RunStatus.QUEUED.value
    for task in session.scalars(select(TaskUnit).where(TaskUnit.run_id == run.id)):
        if task.status == TaskStatus.CANCELLED.value: task.status = TaskStatus.PENDING.value
    session.commit(); session.refresh(run); return run

@router.post("/{run_id}/cancel", response_model=EvaluationRunResponse)
def cancel_evaluation_run(run_id: str, request: Request, session: SessionDependency) -> EvaluationRun | dict[str, Any]:
    store = get_document_store(request)
    if store is not None:
        run = store.get_document("evaluation_runs", run_id)
        if run is None: raise HTTPException(404, "Evaluation run not found")
        if run["status"] in {RunStatus.COMPLETED.value, RunStatus.COMPLETED_WITH_ERRORS.value, RunStatus.CANCELLED.value}: raise HTTPException(409, "Run cannot be cancelled in its current state")
        for task in store.list_documents("task_units", query={"run_id": run_id}):
            store.update_document("task_units", str(task["id"]), {"status": TaskStatus.CANCELLED.value})
        for attempt in store.list_documents("sample_attempts", query={"run_id": run_id, "status": SampleAttemptStatus.PENDING.value}):
            store.update_document("sample_attempts", str(attempt["id"]), {"status": SampleAttemptStatus.CANCELLED.value})
        updated = store.update_document("evaluation_runs", run_id, {"status": RunStatus.CANCELLED.value})
        assert updated is not None
        return updated
    assert session is not None
    run = session.get(EvaluationRun, run_id)
    if run is None: raise HTTPException(404, "Evaluation run not found")
    if run.status in {RunStatus.COMPLETED.value, RunStatus.COMPLETED_WITH_ERRORS.value, RunStatus.CANCELLED.value}: raise HTTPException(409, "Run cannot be cancelled in its current state")
    run.status = RunStatus.CANCELLED.value
    session.query(TaskUnit).filter(TaskUnit.run_id == run.id).update({TaskUnit.status: TaskStatus.CANCELLED.value})
    session.query(SampleAttempt).filter(SampleAttempt.run_id == run.id, SampleAttempt.status == SampleAttemptStatus.PENDING.value).update({SampleAttempt.status: SampleAttemptStatus.CANCELLED.value})
    session.commit(); session.refresh(run); return run


@router.post("/{run_id}/clone", response_model=EvaluationRunResponse, status_code=status.HTTP_201_CREATED)
def clone_evaluation_run(run_id: str, request: Request, session: SessionDependency) -> EvaluationRun | dict[str, Any]:
    store = get_document_store(request)
    try:
        if store is not None:
            return clone_mongo_run(store, run_id)
        assert session is not None
        return clone_run(session, run_id)
    except (RunOperationError, MongoRunExecutionError) as error:
        status_code = status.HTTP_404_NOT_FOUND if str(error) == "Evaluation run not found." else status.HTTP_409_CONFLICT
        raise HTTPException(status_code, str(error)) from error


@router.post("/{run_id}/retry-failed", response_model=EvaluationRunResponse)
def retry_failed_evaluation_samples(run_id: str, request: Request, session: SessionDependency) -> EvaluationRun | dict[str, Any]:
    store = get_document_store(request)
    try:
        if store is not None:
            return retry_failed_mongo_samples(store, run_id)
        assert session is not None
        return retry_failed_samples(session, run_id)
    except (RunOperationError, MongoRunExecutionError) as error:
        status_code = status.HTTP_404_NOT_FOUND if str(error) == "Evaluation run not found." else status.HTTP_409_CONFLICT
        raise HTTPException(status_code, str(error)) from error


@router.post("/{run_id}/execute", response_model=EvaluationRunResponse)
def execute_evaluation_run(
    run_id: str,
    request: Request,
    session: SessionDependency,
    cipher: CipherDependency,
    model_executor: ModelExecutorDependency,
) -> EvaluationRun | dict[str, Any]:
    store = get_document_store(request)
    try:
        if store is not None:
            return execute_mongo_queued_run(
                store,
                run_id=run_id,
                cipher=cipher,
                model_executor=model_executor,
            )
        assert session is not None
        return execute_queued_text_run(
            session,
            run_id=run_id,
            cipher=cipher,
            model_executor=model_executor,
        )
    except (RunExecutionError, MongoRunExecutionError) as error:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if str(error) == "Evaluation run not found."
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=status_code, detail=str(error)) from error
    except SecretConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.get("/{run_id}/attempts", response_model=list[SampleAttemptResponse])
def list_sample_attempts(
    run_id: str,
    request: Request,
    session: SessionDependency,
    attempt_status: Annotated[str | None, Query(alias="status")] = None,
    error_type: str | None = None,
    correct: bool | None = None,
    min_latency_ms: Annotated[float | None, Query(ge=0)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[SampleAttempt | dict[str, Any]]:
    store = get_document_store(request)
    if store is not None:
        if store.get_document("evaluation_runs", run_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
        attempts = store.list_documents("sample_attempts", query={"run_id": run_id}, sort=[("created_at", 1)])
        if attempt_status:
            attempts = [item for item in attempts if item.get("status") == attempt_status]
        if error_type:
            attempts = [item for item in attempts if item.get("error_type") == error_type]
        if correct is True:
            attempts = [item for item in attempts if item.get("score") == 1]
        if correct is False:
            attempts = [item for item in attempts if item.get("score") != 1]
        if min_latency_ms is not None:
            attempts = [item for item in attempts if (item.get("latency_ms") or 0) >= min_latency_ms]
        return attempts[offset : offset + limit]
    assert session is not None
    run = session.get(EvaluationRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    query = select(SampleAttempt).where(SampleAttempt.run_id == run.id)
    if attempt_status:
        query = query.where(SampleAttempt.status == attempt_status)
    if error_type:
        query = query.where(SampleAttempt.error_type == error_type)
    if correct is True:
        query = query.where(SampleAttempt.score == 1)
    if correct is False:
        query = query.where(SampleAttempt.score != 1)
    if min_latency_ms is not None:
        query = query.where(SampleAttempt.latency_ms >= min_latency_ms)
    return list(session.scalars(query.order_by(SampleAttempt.created_at).offset(offset).limit(limit)))


@router.get("/{run_id}/summary")
def get_run_summary(run_id: str, request: Request, session: SessionDependency) -> dict[str, Any]:
    store = get_document_store(request)
    if store is not None:
        try:
            return build_mongo_run_summary(store, run_id)
        except MongoRunExecutionError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    assert session is not None
    run = session.get(EvaluationRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    return build_run_summary(session, run)


@router.get("/{run_id}/events")
async def stream_run_events(run_id: str, request: Request, session: SessionDependency) -> StreamingResponse:
    store = get_document_store(request)
    if store is not None:
        if store.get_document("evaluation_runs", run_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")

        async def mongo_event_stream():
            previous: str | None = None
            terminal_statuses = {RunStatus.COMPLETED.value, RunStatus.COMPLETED_WITH_ERRORS.value, RunStatus.FAILED.value, RunStatus.CANCELLED.value}
            while True:
                run = store.get_document("evaluation_runs", run_id)
                if run is None:
                    return
                payload = {
                    "run_id": run["id"],
                    "status": run["status"],
                    "total_samples": run["total_samples"],
                    "completed_samples": run["completed_samples"],
                    "successful_samples": run["successful_samples"],
                    "failed_samples": run["failed_samples"],
                    "summary": build_mongo_run_summary(store, run_id),
                }
                serialized = json.dumps(payload, separators=(",", ":"))
                if serialized != previous:
                    yield f"event: run\ndata: {serialized}\n\n"
                    previous = serialized
                if payload["status"] in terminal_statuses or await request.is_disconnected():
                    return
                await asyncio.sleep(1)

        return StreamingResponse(mongo_event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
    assert session is not None
    if session.get(EvaluationRun, run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")

    async def event_stream():
        previous: str | None = None
        terminal_statuses = {RunStatus.COMPLETED.value, RunStatus.COMPLETED_WITH_ERRORS.value, RunStatus.FAILED.value, RunStatus.CANCELLED.value}
        while True:
            with request.app.state.database.get_session() as event_session:
                run = event_session.get(EvaluationRun, run_id)
                if run is None:
                    return
                payload = {
                    "run_id": run.id,
                    "status": run.status,
                    "total_samples": run.total_samples,
                    "completed_samples": run.completed_samples,
                    "successful_samples": run.successful_samples,
                    "failed_samples": run.failed_samples,
                    "summary": build_run_summary(event_session, run),
                }
            serialized = json.dumps(payload, separators=(",", ":"))
            if serialized != previous:
                yield f"event: run\ndata: {serialized}\n\n"
                previous = serialized
            if payload["status"] in terminal_statuses:
                return
            if await request.is_disconnected():
                return
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.get("/{run_id}", response_model=EvaluationRunResponse)
def get_evaluation_run(
    run_id: str,
    request: Request,
    session: SessionDependency,
) -> EvaluationRun | dict[str, Any]:
    store = get_document_store(request)
    if store is not None:
        run = store.get_document("evaluation_runs", run_id)
        if run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
        return run
    assert session is not None
    run = session.get(EvaluationRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    return run
