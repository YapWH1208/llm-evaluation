from __future__ import annotations
from collections.abc import Generator
from typing import Annotated
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.db.models import DatasetVersion, EvaluationRun, ModelEndpoint, Report, TaskUnit
router=APIRouter(prefix="/api/v1/dashboard",tags=["dashboard"])
def get_session(request:Request)->Generator[Session,None,None]:
    session=request.app.state.database.get_session()
    try:yield session
    finally:session.close()
SessionDependency=Annotated[Session,Depends(get_session)]
@router.get("")
def summary(session:SessionDependency)->dict[str,object]:
    def count(model,condition=None):
        query=select(func.count()).select_from(model)
        if condition is not None:query=query.where(condition)
        return session.scalar(query) or 0
    return {"runs":{"active":count(EvaluationRun,EvaluationRun.status.in_(["queued","running","paused"])),"completed":count(EvaluationRun,EvaluationRun.status.in_(["completed","completed_with_errors"]))},"queue":{"pending":count(TaskUnit,TaskUnit.status.in_(["pending","retry_scheduled"])),"leased":count(TaskUnit,TaskUnit.status.in_(["leased","running"]))},"endpoints":{"available":count(ModelEndpoint,ModelEndpoint.status=="available"),"unavailable":count(ModelEndpoint,ModelEndpoint.status=="unavailable"),"total":count(ModelEndpoint)},"datasets":{"ready":count(DatasetVersion,DatasetVersion.status=="ready"),"blocked":count(DatasetVersion,DatasetVersion.status.in_(["license_required","failed"]))},"reports":count(Report)}
