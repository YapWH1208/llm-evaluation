from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import BenchmarkDefinition, DatasetVersion
from app.db.mongo import MongoDocumentStore
from app.benchmarks import register_manifest_plugin, validate_manifest_plugin


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


class BenchmarkPackInstall(BaseModel):
    pack_name: str = Field(min_length=1, max_length=128)
    benchmarks: list[BenchmarkCreate] = Field(min_length=1, max_length=100)


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

def get_document_store(request: Request) -> MongoDocumentStore | None:
    return getattr(request.app.state, "document_store", None)


def _canonical_manifest(benchmark: BenchmarkCreate) -> dict[str, Any]:
    """Make the stored manifest self-contained and validate inline executable samples."""

    manifest = dict(benchmark.manifest)
    for field, expected in (("benchmark_id", benchmark.benchmark_id), ("version", benchmark.version), ("display_name", benchmark.display_name)):
        value = manifest.get(field)
        if value is not None and value != expected:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Manifest {field} must match the benchmark definition")
        manifest[field] = expected
    try:
        validate_manifest_plugin(manifest)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    return manifest


@router.get("", response_model=list[BenchmarkResponse])
def list_benchmarks(request: Request, session: SessionDependency) -> list[BenchmarkDefinition | dict[str, Any]]:
    store = get_document_store(request)
    if store is not None:
        return store.list_documents("benchmark_definitions", sort=[("created_at", -1)])
    assert session is not None
    return list(session.scalars(select(BenchmarkDefinition).order_by(BenchmarkDefinition.created_at.desc())))


@router.post("/packs", response_model=list[BenchmarkResponse], status_code=status.HTTP_201_CREATED)
def install_benchmark_pack(payload: BenchmarkPackInstall, request: Request, session: SessionDependency) -> list[BenchmarkDefinition | dict[str, Any]]:
    """Install a versioned manifest pack without overwriting existing benchmark versions."""

    store = get_document_store(request)
    installed: list[BenchmarkDefinition | dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []
    for benchmark in payload.benchmarks:
        manifest = _canonical_manifest(benchmark)
        manifests.append(manifest)
        if store is not None:
            if store.list_documents("benchmark_definitions", query={"benchmark_id": benchmark.benchmark_id, "version": benchmark.version}):
                raise HTTPException(status.HTTP_409_CONFLICT, f"Benchmark {benchmark.benchmark_id}@{benchmark.version} already exists")
            installed.append(store.insert_document("benchmark_definitions", {"benchmark_id": benchmark.benchmark_id, "version": benchmark.version, "display_name": benchmark.display_name, "manifest": manifest, "status": "registered", "source": f"pack:{payload.pack_name}", "created_at": datetime.now()}))
            continue
        assert session is not None
        installed.append(BenchmarkDefinition(benchmark_id=benchmark.benchmark_id, version=benchmark.version, display_name=benchmark.display_name, manifest=manifest, status="registered", source=f"pack:{payload.pack_name}"))
    if store is None:
        assert session is not None
        session.add_all(installed)
        try:
            session.commit()
        except IntegrityError as error:
            session.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "One or more benchmark versions already exist") from error
        for item in installed:
            session.refresh(item)
    for manifest in manifests:
        register_manifest_plugin(manifest)
    return installed


@router.post("", response_model=BenchmarkResponse, status_code=status.HTTP_201_CREATED)
def register_benchmark(payload: BenchmarkCreate, request: Request, session: SessionDependency) -> BenchmarkDefinition | dict[str, Any]:
    store = get_document_store(request)
    manifest = _canonical_manifest(payload)
    if store is not None:
        if store.list_documents("benchmark_definitions", query={"benchmark_id": payload.benchmark_id, "version": payload.version}):
            raise HTTPException(status.HTTP_409_CONFLICT, "Benchmark ID and version already exist")
        created = store.insert_document(
            "benchmark_definitions",
            {"benchmark_id": payload.benchmark_id, "version": payload.version, "display_name": payload.display_name, "manifest": manifest, "status": "registered", "source": "user", "created_at": datetime.now()},
        )
        register_manifest_plugin(manifest)
        return created
    assert session is not None
    definition = BenchmarkDefinition(
        benchmark_id=payload.benchmark_id,
        version=payload.version,
        display_name=payload.display_name,
        manifest=manifest,
        status="registered",
        source="user",
    )
    session.add(definition)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Benchmark ID and version already exist") from error
    session.refresh(definition)
    register_manifest_plugin(manifest)
    return definition


@router.get("/{benchmark_definition_id}", response_model=BenchmarkResponse)
def get_benchmark(benchmark_definition_id: str, request: Request, session: SessionDependency) -> BenchmarkDefinition | dict[str, Any]:
    store = get_document_store(request)
    if store is not None:
        item = store.get_document("benchmark_definitions", benchmark_definition_id)
        if item is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Benchmark definition not found")
        return item
    assert session is not None
    item = session.get(BenchmarkDefinition, benchmark_definition_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Benchmark definition not found")
    return item


@router.get("/{benchmark_definition_id}/prompt")
def get_benchmark_prompt(benchmark_definition_id: str, request: Request, session: SessionDependency) -> dict[str, Any]:
    benchmark = get_benchmark(benchmark_definition_id, request, session)
    manifest = benchmark["manifest"] if isinstance(benchmark, dict) else benchmark.manifest
    return {"benchmark_id": benchmark["benchmark_id"] if isinstance(benchmark, dict) else benchmark.benchmark_id, "version": benchmark["version"] if isinstance(benchmark, dict) else benchmark.version, "prompt": manifest.get("prompt") if isinstance(manifest, dict) else None, "default_request_body": manifest.get("default_request_body", {}) if isinstance(manifest, dict) else {}}


@router.get("/{benchmark_definition_id}/dataset-status")
def get_benchmark_dataset_status(benchmark_definition_id: str, request: Request, session: SessionDependency) -> list[dict[str, Any]]:
    benchmark = get_benchmark(benchmark_definition_id, request, session)
    manifest = benchmark["manifest"] if isinstance(benchmark, dict) else benchmark.manifest
    declared = manifest.get("datasets", []) if isinstance(manifest, dict) else []
    if not isinstance(declared, list):
        declared = []
    store = get_document_store(request)
    items: list[dict[str, Any]] = []
    for descriptor in declared:
        if not isinstance(descriptor, dict):
            continue
        dataset_id = descriptor.get("dataset_id") or descriptor.get("id")
        version = descriptor.get("version")
        if not isinstance(dataset_id, str):
            continue
        if store is not None:
            matches = store.list_documents("dataset_versions", query={"dataset_id": dataset_id, **({"version": version} if isinstance(version, str) else {})})
            dataset = matches[0] if matches else None
        else:
            assert session is not None
            query = select(DatasetVersion).where(DatasetVersion.dataset_id == dataset_id)
            if isinstance(version, str):
                query = query.where(DatasetVersion.version == version)
            dataset = session.scalar(query.order_by(DatasetVersion.created_at.desc()))
        items.append({"dataset_id": dataset_id, "version": version, "status": (dataset.get("status") if isinstance(dataset, dict) else dataset.status if dataset is not None else "not_registered"), "dataset_version_id": (dataset.get("id") if isinstance(dataset, dict) else dataset.id if dataset is not None else None)})
    return items


@router.patch("/{benchmark_definition_id}", response_model=BenchmarkResponse)
def update_benchmark(
    benchmark_definition_id: str,
    payload: BenchmarkUpdate,
    request: Request,
    session: SessionDependency,
) -> BenchmarkDefinition | dict[str, Any]:
    values = payload.model_dump(exclude_unset=True)
    store = get_document_store(request)
    if store is not None:
        existing = store.get_document("benchmark_definitions", benchmark_definition_id)
        if existing is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Benchmark definition not found")
        if "manifest" in values:
            replacement = BenchmarkCreate(benchmark_id=str(existing["benchmark_id"]), version=str(existing["version"]), display_name=str(values.get("display_name") or existing["display_name"]), manifest=values["manifest"])
            values["manifest"] = _canonical_manifest(replacement)
        updated = store.update_document("benchmark_definitions", benchmark_definition_id, values)
        assert updated is not None
        if "manifest" in values:
            register_manifest_plugin(values["manifest"])
        return updated
    assert session is not None
    item = session.get(BenchmarkDefinition, benchmark_definition_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Benchmark definition not found")
    if "manifest" in values:
        replacement = BenchmarkCreate(benchmark_id=item.benchmark_id, version=item.version, display_name=str(values.get("display_name") or item.display_name), manifest=values["manifest"])
        values["manifest"] = _canonical_manifest(replacement)
    for field, value in values.items():
        setattr(item, field, value)
    session.commit()
    session.refresh(item)
    if "manifest" in values:
        register_manifest_plugin(item.manifest)
    return item
