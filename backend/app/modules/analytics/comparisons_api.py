from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app.modules.analytics.comparisons import ComparisonService


router = APIRouter(prefix="/api/v1/comparisons", tags=["comparisons"])


def get_comparison_service(request: Request) -> ComparisonService:
    return request.app.state.comparison_service


ComparisonServiceDependency = Annotated[ComparisonService, Depends(get_comparison_service)]


@router.get("")
def compare(run_a: str, run_b: str, service: ComparisonServiceDependency) -> dict[str, Any]:
    return service.compare(run_a, run_b)
