from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.modules.benchmarks.service import BenchmarkService


router = APIRouter(prefix="/api/v1/benchmarks", tags=["benchmarks"])


class BenchmarkCreate(BaseModel):
    benchmark_id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=200)
    manifest: dict[str, Any]


class BenchmarkResponse(BenchmarkCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    source: str
    created_at: datetime


class BenchmarkUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    manifest: dict[str, Any] | None = None
    status: Literal["registered", "enabled", "disabled"] | None = None


class BenchmarkVersionCreate(BaseModel):
    version: str = Field(min_length=1, max_length=64)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    manifest: dict[str, Any]


class BenchmarkPackInstall(BaseModel):
    pack_name: str = Field(min_length=1, max_length=128)
    benchmarks: list[BenchmarkCreate] = Field(min_length=1, max_length=100)


def get_benchmark_service(request: Request) -> BenchmarkService:
    return request.app.state.benchmark_service


BenchmarkServiceDependency = Annotated[BenchmarkService, Depends(get_benchmark_service)]


@router.get("", response_model=list[BenchmarkResponse])
def list_benchmarks(service: BenchmarkServiceDependency) -> list[Any]:
    return service.list()


@router.post("/packs", response_model=list[BenchmarkResponse], status_code=status.HTTP_201_CREATED)
def install_benchmark_pack(payload: BenchmarkPackInstall, service: BenchmarkServiceDependency) -> list[Any]:
    return service.install_pack(payload)


@router.post("", response_model=BenchmarkResponse, status_code=status.HTTP_201_CREATED)
def register_benchmark(payload: BenchmarkCreate, service: BenchmarkServiceDependency) -> Any:
    return service.register(payload)


@router.get("/{benchmark_definition_id}", response_model=BenchmarkResponse)
def get_benchmark(benchmark_definition_id: str, service: BenchmarkServiceDependency) -> Any:
    return service.get(benchmark_definition_id)


@router.post(
    "/{benchmark_definition_id}/versions", response_model=BenchmarkResponse, status_code=status.HTTP_201_CREATED
)
def create_benchmark_version(
    benchmark_definition_id: str,
    payload: BenchmarkVersionCreate,
    service: BenchmarkServiceDependency,
) -> Any:
    return service.create_version(benchmark_definition_id, payload)


@router.get("/{benchmark_definition_id}/prompt")
def get_benchmark_prompt(benchmark_definition_id: str, service: BenchmarkServiceDependency) -> dict[str, Any]:
    return service.prompt(benchmark_definition_id)


@router.get("/{benchmark_definition_id}/dataset-status")
def get_benchmark_dataset_status(
    benchmark_definition_id: str, service: BenchmarkServiceDependency
) -> list[dict[str, Any]]:
    return service.dataset_status(benchmark_definition_id)


@router.patch("/{benchmark_definition_id}", response_model=BenchmarkResponse)
def update_benchmark(
    benchmark_definition_id: str,
    payload: BenchmarkUpdate,
    service: BenchmarkServiceDependency,
) -> Any:
    return service.update(benchmark_definition_id, payload)
