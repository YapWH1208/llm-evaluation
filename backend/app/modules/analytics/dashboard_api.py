from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app.modules.analytics.dashboard import DashboardService


router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def get_dashboard_service(request: Request) -> DashboardService:
    return request.app.state.dashboard_service


DashboardServiceDependency = Annotated[DashboardService, Depends(get_dashboard_service)]


@router.get("")
def summary(service: DashboardServiceDependency) -> dict[str, Any]:
    return service.summary()
