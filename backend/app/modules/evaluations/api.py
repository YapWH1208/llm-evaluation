from __future__ import annotations

import asyncio
import json
from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.core.secrets import SecretCipher, SecretConfigurationError
from app.db import EvaluationRun, RunStatus
from app.db.mongo import MongoDocumentStore
from app.modules.evaluations.service import (
    EvaluationService,
)
from app.infrastructure.providers.contracts import ModelExecutor
from app.modules.evaluations.executor import RunExecutionError, execute_queued_text_run
from app.modules.evaluations.names import resolve_run_display_name
from app.modules.benchmarks.scoring import ScoringError, validate_scoring_rule
from app.modules.evaluations.mongo_executor import (
    MongoRunExecutionError,
    execute_mongo_queued_run,
)

router = APIRouter(prefix="/api/v1/evaluation-runs", tags=["evaluation runs"])


class EvaluationRunCreate(BaseModel):
    model_endpoint_id: str
    sample_limit: Annotated[int | None, Field(ge=1, le=10_000)] = None
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


class DatasetRunCreate(BaseModel):
    model_endpoint_id: str
    dataset_version_id: str
    prompt_package_id: str | None = None
    input_field: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    reference_field: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    sample_limit: Annotated[int, Field(ge=1, le=10_000)] = 100
    max_concurrency: Annotated[int | None, Field(ge=1, le=1000)] = None
    request_body_override: dict[str, Any] = Field(default_factory=dict)
    scoring_rule: dict[str, Any] | None = None

    @field_validator("input_field", "reference_field")
    @classmethod
    def normalize_field_selection(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Dataset field selections must not be blank.")
        return normalized

    @field_validator("scoring_rule")
    @classmethod
    def validate_dataset_scoring_rule(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return value
        try:
            validate_scoring_rule(value)
        except ScoringError as error:
            raise ValueError(str(error)) from error
        return value


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
    display_name: str | None = None
    configuration_snapshot: dict[str, Any]
    status: str
    total_samples: int
    completed_samples: int
    successful_samples: int
    failed_samples: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    archived_at: datetime | None = None

    @model_validator(mode="after")
    def populate_legacy_display_name(self) -> "EvaluationRunResponse":
        self.display_name = resolve_run_display_name(self)
        return self


class EvaluationRunPreflightResponse(BaseModel):
    can_queue: bool
    issues: list[str]
    sample_count: int
    estimated_requests: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost: float | None
    currency: str | None
    judge_estimate: dict[str, Any] | None = None
    compatibility: dict[str, list[str]]
    datasets: list[dict[str, Any]]
    request_body_evidence: dict[str, Any] | None


class RunSchedulingUpdate(BaseModel):
    """Operational controls are mutable without changing a run's frozen inputs."""

    max_concurrency: Annotated[int | None, Field(ge=1, le=1000)] = None


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
    metric_evidence: dict[str, Any] | None = None
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
    sample_metadata: dict[str, Any] = Field(default_factory=dict)
    judge_disagreement: bool = False
    human_review_status: str = "unreviewed"


class RunLogEntry(BaseModel):
    timestamp: datetime
    level: str
    event: str
    message: str
    task_id: str | None = None
    sample_attempt_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class EvaluationRunProgress(BaseModel):
    run_id: str
    status: str
    total_samples: int
    completed_samples: int
    successful_samples: int
    failed_samples: int
    completion_rate: float | None


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


def get_evaluation_service(request: Request) -> EvaluationService:
    return request.app.state.evaluation_service


SessionDependency = Annotated[Session | None, Depends(get_session)]
CipherDependency = Annotated[SecretCipher, Depends(get_cipher)]
ModelExecutorDependency = Annotated[ModelExecutor, Depends(get_model_executor)]
EvaluationServiceDependency = Annotated[EvaluationService, Depends(get_evaluation_service)]


def get_document_store(request: Request) -> MongoDocumentStore | None:
    return getattr(request.app.state, "document_store", None)


@router.post("", response_model=EvaluationRunResponse, status_code=status.HTTP_201_CREATED)
def create_evaluation_run(
    payload: EvaluationRunCreate,
    request: Request,
    service: EvaluationServiceDependency,
) -> dict[str, Any]:
    return service.create_benchmark(
        model_endpoint_id=payload.model_endpoint_id,
        sample_limit=payload.sample_limit,
        prompt_package_id=payload.prompt_package_id,
        benchmark_id=payload.benchmark_id,
        benchmark_version=payload.benchmark_version,
        request_body_override=payload.request_body_override,
        created_by=getattr(request.state, "actor_id", None),
        max_concurrency=payload.max_concurrency,
    )


@router.post("/validate", response_model=EvaluationRunPreflightResponse)
def validate_evaluation_run(
    payload: EvaluationRunCreate,
    service: EvaluationServiceDependency,
) -> dict[str, object]:
    """Preview schedule compatibility and cost without persisting a run or task."""

    return service.preflight_benchmark(
        model_endpoint_id=payload.model_endpoint_id,
        sample_limit=payload.sample_limit,
        prompt_package_id=payload.prompt_package_id,
        benchmark_id=payload.benchmark_id,
        benchmark_version=payload.benchmark_version,
        request_body_override=payload.request_body_override,
    )


@router.post("/custom-multimodal", response_model=EvaluationRunResponse, status_code=status.HTTP_201_CREATED)
def create_custom_run(
    payload: CustomMultimodalRunCreate,
    request: Request,
    service: EvaluationServiceDependency,
) -> dict[str, Any]:
    return service.create_custom_run(
        model_endpoint_id=payload.model_endpoint_id,
        sample_id=payload.sample_id,
        messages=payload.messages,
        reference_answer=payload.reference_answer,
        created_by=getattr(request.state, "actor_id", None),
        max_concurrency=payload.max_concurrency,
    )


@router.post("/dataset", response_model=EvaluationRunResponse, status_code=status.HTTP_201_CREATED)
def create_dataset_evaluation_run(
    payload: DatasetRunCreate,
    request: Request,
    service: EvaluationServiceDependency,
) -> dict[str, Any]:
    return service.create_dataset_run(
        model_endpoint_id=payload.model_endpoint_id,
        dataset_version_id=payload.dataset_version_id,
        prompt_package_id=payload.prompt_package_id,
        input_field=payload.input_field,
        reference_field=payload.reference_field,
        sample_limit=payload.sample_limit,
        request_body_override=payload.request_body_override,
        scoring_rule=payload.scoring_rule,
        created_by=getattr(request.state, "actor_id", None),
        max_concurrency=payload.max_concurrency,
    )


@router.post("/dataset/preflight", response_model=EvaluationRunPreflightResponse)
def preflight_dataset_evaluation_run(
    payload: DatasetRunCreate,
    service: EvaluationServiceDependency,
) -> dict[str, object]:
    return service.preflight_dataset_run(
        model_endpoint_id=payload.model_endpoint_id,
        dataset_version_id=payload.dataset_version_id,
        prompt_package_id=payload.prompt_package_id,
        input_field=payload.input_field,
        reference_field=payload.reference_field,
        sample_limit=payload.sample_limit,
        request_body_override=payload.request_body_override,
        scoring_rule=payload.scoring_rule,
    )


@router.get("", response_model=list[EvaluationRunResponse])
def list_evaluation_runs(
    service: EvaluationServiceDependency,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    return service.list(include_archived=include_archived)


@router.post("/{run_id}/pause", response_model=EvaluationRunResponse)
def pause_evaluation_run(run_id: str, service: EvaluationServiceDependency) -> dict[str, Any]:
    return service.pause(run_id)


@router.post("/{run_id}/resume", response_model=EvaluationRunResponse)
def resume_evaluation_run(run_id: str, service: EvaluationServiceDependency) -> dict[str, Any]:
    return service.resume(run_id)


@router.post("/{run_id}/cancel", response_model=EvaluationRunResponse)
def cancel_evaluation_run(run_id: str, service: EvaluationServiceDependency) -> dict[str, Any]:
    return service.cancel(run_id)


@router.post("/{run_id}/archive", response_model=EvaluationRunResponse)
def archive_evaluation_run(run_id: str, service: EvaluationServiceDependency) -> dict[str, Any]:
    """Hide a terminal run while retaining its complete immutable evidence."""

    return service.archive(run_id)


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evaluation_run(run_id: str, service: EvaluationServiceDependency) -> Response:
    """Permanently delete a run only after it has been explicitly archived."""

    service.delete(run_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{run_id}/clone", response_model=EvaluationRunResponse, status_code=status.HTTP_201_CREATED)
def clone_evaluation_run(run_id: str, service: EvaluationServiceDependency) -> dict[str, Any]:
    return service.clone(run_id)


@router.post("/{run_id}/rerun-benchmark", response_model=EvaluationRunResponse, status_code=status.HTTP_201_CREATED)
def rerun_evaluation_benchmark(run_id: str, service: EvaluationServiceDependency) -> dict[str, Any]:
    """Create a new benchmark pass without mutating completed or historical evidence."""

    return service.rerun_benchmark(run_id)


@router.patch("/{run_id}/scheduling", response_model=EvaluationRunResponse)
def update_run_scheduling(
    run_id: str,
    payload: RunSchedulingUpdate,
    service: EvaluationServiceDependency,
) -> dict[str, Any]:
    """Update the live concurrency ceiling while retaining the immutable run snapshot."""

    values = payload.model_dump(exclude_unset=True)
    return service.update_scheduling(run_id, values)


@router.post("/{run_id}/retry-failed", response_model=EvaluationRunResponse)
def retry_failed_evaluation_samples(
    run_id: str,
    service: EvaluationServiceDependency,
) -> dict[str, Any]:
    return service.retry_failed(run_id)


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
                data_root=str(request.app.state.settings.data_root),
                settings=request.app.state.settings,
            )
        assert session is not None
        return execute_queued_text_run(
            session,
            run_id=run_id,
            cipher=cipher,
            model_executor=model_executor,
            data_root=str(request.app.state.settings.data_root),
            settings=request.app.state.settings,
        )
    except (RunExecutionError, MongoRunExecutionError) as error:
        status_code = (
            status.HTTP_404_NOT_FOUND if str(error) == "Evaluation run not found." else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=status_code, detail=str(error)) from error
    except SecretConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.get("/{run_id}/attempts", response_model=list[SampleAttemptResponse])
def list_sample_attempts(
    run_id: str,
    service: EvaluationServiceDependency,
    attempt_status: Annotated[str | None, Query(alias="status")] = None,
    error_type: str | None = None,
    correct: bool | None = None,
    min_latency_ms: Annotated[float | None, Query(ge=0)] = None,
    min_tokens: Annotated[int | None, Query(ge=0)] = None,
    min_cost: Annotated[float | None, Query(ge=0)] = None,
    capability: str | None = None,
    modality: str | None = None,
    language: str | None = None,
    difficulty: str | None = None,
    api_error: bool | None = None,
    parser_error: bool | None = None,
    judge_disagreement: bool | None = None,
    human_review_status: str | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[dict[str, Any]]:
    return service.list_attempts(
        run_id,
        offset=offset,
        limit=limit,
        attempt_status=attempt_status,
        error_type=error_type,
        correct=correct,
        min_latency_ms=min_latency_ms,
        min_tokens=min_tokens,
        min_cost=min_cost,
        capability=capability,
        modality=modality,
        language=language,
        difficulty=difficulty,
        api_error=api_error,
        parser_error=parser_error,
        judge_disagreement=judge_disagreement,
        human_review_status=human_review_status,
    )


@router.get("/{run_id}/summary")
def get_run_summary(run_id: str, service: EvaluationServiceDependency) -> dict[str, Any]:
    return service.summary(run_id)


@router.get("/{run_id}/progress", response_model=EvaluationRunProgress)
def get_run_progress(run_id: str, service: EvaluationServiceDependency) -> dict[str, Any]:
    return service.progress(run_id)


@router.get("/{run_id}/logs", response_model=list[RunLogEntry])
def get_run_logs(
    run_id: str,
    service: EvaluationServiceDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1_000)] = 200,
) -> list[dict[str, Any]]:
    """Return durable, secret-safe task and sample lifecycle log entries."""

    return service.logs(run_id, offset=offset, limit=limit)


@router.get("/{run_id}/events")
async def stream_run_events(run_id: str, request: Request, service: EvaluationServiceDependency) -> StreamingResponse:
    service.get(run_id)

    async def event_stream():
        previous: str | None = None
        terminal_statuses = {
            RunStatus.COMPLETED.value,
            RunStatus.COMPLETED_WITH_ERRORS.value,
            RunStatus.FAILED.value,
            RunStatus.CANCELLED.value,
        }
        while True:
            payload = service.event_payload(run_id)
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
    service: EvaluationServiceDependency,
) -> dict[str, Any]:
    return service.get(run_id)
