from __future__ import annotations
from typing import Any
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import Depends, Request
from collections.abc import Generator
from app.db.models import EvaluationRun, SampleAttempt
router=APIRouter(prefix="/api/v1/comparisons",tags=["comparisons"])
def get_session(request:Request)->Generator[Session,None,None]:
    session=request.app.state.database.get_session()
    try:yield session
    finally:session.close()
@router.get("")
def compare(run_a:str,run_b:str,session:Session=Depends(get_session))->dict[str,Any]:
    first=session.get(EvaluationRun,run_a);second=session.get(EvaluationRun,run_b)
    if first is None or second is None:raise HTTPException(404,"One or both evaluation runs were not found")
    if first.benchmark_id!=second.benchmark_id or first.benchmark_version!=second.benchmark_version:raise HTTPException(409,"Runs must use the same benchmark version")
    def scores(run_id:str)->dict[str,float]:return {a.sample_id:float(a.score or 0) for a in session.scalars(select(SampleAttempt).where(SampleAttempt.run_id==run_id,SampleAttempt.status=="succeeded"))}
    a,b=scores(run_a),scores(run_b);shared=sorted(set(a)&set(b));both=sum(a[x]==1 and b[x]==1 for x in shared);a_only=sum(a[x]==1 and b[x]!=1 for x in shared);b_only=sum(a[x]!=1 and b[x]==1 for x in shared);neither=sum(a[x]!=1 and b[x]!=1 for x in shared)
    return {"run_a":run_a,"run_b":run_b,"benchmark_id":first.benchmark_id,"shared_samples":len(shared),"run_a_accuracy":(sum(a.values())/len(a) if a else None),"run_b_accuracy":(sum(b.values())/len(b) if b else None),"both_correct":both,"run_a_only_correct":a_only,"run_b_only_correct":b_only,"both_incorrect":neither}
