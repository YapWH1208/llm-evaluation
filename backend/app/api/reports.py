from __future__ import annotations
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import Report
from app.services.reports import ReportError, generate_report
router=APIRouter(prefix="/api/v1/reports",tags=["reports"])
class ReportCreate(BaseModel):run_id:str;format:str="html"
class ReportResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:str;run_id:str;report_type:str;format:str;artifact_path:str;generator_version:str;generated_at:datetime
def get_session(request:Request)->Generator[Session,None,None]:
    session=request.app.state.database.get_session()
    try:yield session
    finally:session.close()
SessionDependency=Annotated[Session,Depends(get_session)]
@router.post("",response_model=ReportResponse)
def create(payload:ReportCreate,request:Request,session:SessionDependency)->Report:
    try:return generate_report(session,payload.run_id,payload.format,request.app.state.settings.data_root)
    except ReportError as error:raise HTTPException(409,str(error)) from error
@router.get("/run/{run_id}",response_model=list[ReportResponse])
def list_for_run(run_id:str,session:SessionDependency)->list[Report]:return list(session.scalars(select(Report).where(Report.run_id==run_id).order_by(Report.generated_at.desc())))
@router.get("/{report_id}/download")
def download(report_id:str,session:SessionDependency):
    report=session.get(Report,report_id)
    if report is None:raise HTTPException(404,"Report not found")
    path=Path(report.artifact_path)
    if not path.is_file():raise HTTPException(404,"Report artifact is no longer available")
    return FileResponse(path,filename=path.name,media_type={"json":"application/json","csv":"text/csv","html":"text/html","markdown":"text/markdown"}.get(report.format,"application/octet-stream"))
