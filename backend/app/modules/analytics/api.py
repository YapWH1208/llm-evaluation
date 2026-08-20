from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.analytics.aggregation import AggregationService
from app.modules.analytics.matrix import MatrixService
from app.modules.analytics.scatter import ScatterFilters, ScatterService
from app.modules.benchmarks.metrics import METRIC_PROFILE_VERSION, metric_definition


router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


class AggregateMetricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    benchmark_id: str
    model_endpoint_id: str
    metric_name: str
    metric_value: float | None
    availability_reason: str | None = None
    sample_count: int
    confidence_interval: dict[str, object] | None
    aggregation_version: str
    created_at: datetime
    metric_label: str = ""
    unit: str = ""
    profile: str = ""
    required_evidence: list[str] = Field(default_factory=list)
    profile_version: str = METRIC_PROFILE_VERSION

    @model_validator(mode="after")
    def add_metric_definition(self) -> "AggregateMetricResponse":
        try:
            definition = metric_definition(self.metric_name)
        except ValueError:
            self.metric_label = self.metric_name.replace("_", " ").title()
            self.unit = "value"
            self.profile = "custom"
            self.required_evidence = []
            return self
        self.metric_label = definition.label
        self.unit = definition.unit
        self.profile = definition.profile
        self.required_evidence = list(definition.required_evidence)
        return self


def get_aggregation_service(request: Request) -> AggregationService:
    return request.app.state.aggregation_service


def get_scatter_service(request: Request) -> ScatterService:
    return request.app.state.scatter_service


def get_matrix_service(request: Request) -> MatrixService:
    return request.app.state.matrix_service


AggregationServiceDependency = Annotated[AggregationService, Depends(get_aggregation_service)]
ScatterServiceDependency = Annotated[ScatterService, Depends(get_scatter_service)]
MatrixServiceDependency = Annotated[MatrixService, Depends(get_matrix_service)]


@router.get("/runs/{run_id}/metrics", response_model=list[AggregateMetricResponse])
def run_aggregate_metrics(run_id: str, service: AggregationServiceDependency) -> list[dict[str, Any]]:
    return service.list(run_id)


@router.post("/runs/{run_id}/metrics/recompute", response_model=list[AggregateMetricResponse])
def recompute_run_aggregate_metrics(run_id: str, service: AggregationServiceDependency) -> list[dict[str, Any]]:
    return service.recompute(run_id)


@router.get("/scatter")
def evidence_scatter(
    service: ScatterServiceDependency,
    x_axis: str = Query(default="score", min_length=1, max_length=128),
    y_axis: str = Query(default="average_latency_ms", min_length=1, max_length=128),
    run_ids: list[str] | None = Query(default=None),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    model_endpoint_id: str | None = Query(default=None, max_length=128),
    dataset: str | None = Query(default=None, max_length=128),
    statuses: list[str] | None = Query(default=None, alias="status"),
    capability: str | None = Query(default=None, max_length=64),
    language: str | None = Query(default=None, max_length=64),
    evaluation_type: str | None = Query(default=None, max_length=32),
    min_score: float | None = None,
    max_score: float | None = None,
    min_accuracy: float | None = None,
    max_accuracy: float | None = None,
    min_latency_ms: float | None = None,
    max_latency_ms: float | None = None,
    min_cost: float | None = None,
    max_cost: float | None = None,
    max_points: int = Query(default=500, ge=1, le=500),
) -> dict[str, object]:
    return service.build(
        x_axis=x_axis,
        y_axis=y_axis,
        filters=ScatterFilters(
            run_ids=frozenset(run_ids) if run_ids is not None else None,
            created_from=date_from,
            created_to=date_to,
            model_endpoint_id=model_endpoint_id,
            dataset=dataset,
            statuses=frozenset(statuses) if statuses is not None else None,
            capability=capability,
            language=language,
            evaluation_type=evaluation_type,
            min_score=min_score,
            max_score=max_score,
            min_accuracy=min_accuracy,
            max_accuracy=max_accuracy,
            min_latency_ms=min_latency_ms,
            max_latency_ms=max_latency_ms,
            min_cost=min_cost,
            max_cost=max_cost,
            max_points=max_points,
        ),
    )


@router.get("/matrix")
def capability_matrix(
    service: MatrixServiceDependency,
    baseline_run_id: str | None = None,
) -> dict[str, Any]:
    return service.build(baseline_run_id)
