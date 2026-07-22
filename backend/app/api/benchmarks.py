from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import BenchmarkDefinition


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


def get_session(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.database.get_session()
    try:
        yield session
    finally:
        session.close()


SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("", response_model=list[BenchmarkResponse])
def list_benchmarks(session: SessionDependency) -> list[BenchmarkDefinition]:
    return list(session.scalars(select(BenchmarkDefinition).order_by(BenchmarkDefinition.created_at.desc())))


@router.post("", response_model=BenchmarkResponse, status_code=status.HTTP_201_CREATED)
def register_benchmark(payload: BenchmarkCreate, session: SessionDependency) -> BenchmarkDefinition:
    definition = BenchmarkDefinition(
        **payload.model_dump(),
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
    return definition
