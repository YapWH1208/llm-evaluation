from __future__ import annotations
import csv, html, json
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import EvaluationRun, Report, SampleAttempt

class ReportError(ValueError): pass

def generate_report(session:Session,run_id:str,format:str,data_root:str)->Report:
    run=session.get(EvaluationRun,run_id)
    if run is None: raise ReportError("Evaluation run not found.")
    if run.status not in {"completed","completed_with_errors"}: raise ReportError("Reports can only be generated after a run completes.")
    attempts=list(session.scalars(select(SampleAttempt).where(SampleAttempt.run_id==run.id).order_by(SampleAttempt.sample_id)))
    payload={"run_id":run.id,"benchmark":{"id":run.benchmark_id,"version":run.benchmark_version},"status":run.status,"summary":{"total":run.total_samples,"completed":run.completed_samples,"successful":run.successful_samples,"failed":run.failed_samples,"accuracy":(sum((a.score or 0) for a in attempts)/len(attempts) if attempts else None)},"attempts":[{"sample_id":a.sample_id,"attempt":a.attempt_number,"status":a.status,"prediction":a.parsed_prediction,"reference":a.reference_snapshot,"score":a.score,"error_type":a.error_type,"error_message":a.error_message,"latency":None} for a in attempts]}
    extension={"json":"json","csv":"csv","html":"html"}.get(format)
    if extension is None: raise ReportError("Supported report formats are json, csv, and html.")
    directory=Path(data_root).resolve()/"reports"/run.id;directory.mkdir(parents=True,exist_ok=True)
    path=directory/f"report.{extension}"
    if format=="json": path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    elif format=="csv":
        with path.open("w",newline="",encoding="utf-8") as file:
            writer=csv.DictWriter(file,fieldnames=["sample_id","attempt","status","prediction","reference","score","error_type","error_message"]);writer.writeheader()
            for item in payload["attempts"]: writer.writerow({**item,"reference":json.dumps(item["reference"],ensure_ascii=False)})
    else:
        rows="".join(f"<tr><td>{html.escape(str(x['sample_id']))}</td><td>{html.escape(str(x['status']))}</td><td>{html.escape(str(x['prediction'] or ''))}</td><td>{html.escape(str(x['score']))}</td></tr>" for x in payload["attempts"])
        path.write_text(f"<!doctype html><title>Evaluation report</title><h1>{html.escape(run.benchmark_id)}</h1><p>Status: {html.escape(run.status)} · Accuracy: {payload['summary']['accuracy']}</p><table><tr><th>Sample</th><th>Status</th><th>Prediction</th><th>Score</th></tr>{rows}</table>",encoding="utf-8")
    report=Report(run_id=run.id,report_type="single_model",format=format,artifact_path=str(path));session.add(report);session.commit();session.refresh(report);return report
