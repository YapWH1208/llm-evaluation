from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db.mongo import MongoDocumentStore
from app.services.mongo_run_executor import MongoRunExecutionError, build_mongo_run_summary
from app.services.reports import ReportError, _FORMAT_EXTENSIONS, _write_report


def generate_mongo_report(store: MongoDocumentStore, run_id: str, format: str, data_root: str) -> dict[str, Any]:
    run=store.get_document("evaluation_runs",run_id)
    if run is None: raise ReportError("Evaluation run not found.")
    if run["status"] not in {"completed","completed_with_errors"}: raise ReportError("Reports can only be generated after a run completes.")
    extension=_FORMAT_EXTENSIONS.get(format)
    if extension is None: raise ReportError("Supported report formats are json, csv, parquet, html, markdown, and pdf.")
    attempts=store.list_documents("sample_attempts",query={"run_id":run_id},sort=[("sample_id",1),("attempt_number",1)])
    latest={}
    for item in reversed(attempts): latest.setdefault(item["sample_id"],item["id"])
    payload={"run_id":run_id,"benchmark":{"id":run["benchmark_id"],"version":run["benchmark_version"]},"model_endpoint_id":run["model_endpoint_id"],"status":run["status"],"configuration_snapshot":run["configuration_snapshot"],"summary":build_mongo_run_summary(store,run_id),"attempts":[{"sample_id":item["sample_id"],"attempt":item["attempt_number"],"is_latest":latest[item["sample_id"]]==item["id"],"status":item["status"],"input":item["input_snapshot"],"reference":item["reference_snapshot"],"request":item.get("request_snapshot"),"raw_response":item.get("raw_response"),"prediction":item.get("parsed_prediction"),"score":item.get("score"),"latency_ms":item.get("latency_ms"),"input_tokens":item.get("input_tokens"),"output_tokens":item.get("output_tokens"),"estimated_cost":item.get("estimated_cost"),"error_type":item.get("error_type"),"error_message":item.get("error_message"),"human_reviews":[],"judge_assessments":[],"created_at":item.get("created_at").isoformat() if item.get("created_at") else None,"completed_at":item.get("completed_at").isoformat() if item.get("completed_at") else None} for item in attempts]}
    path=Path(data_root).resolve()/"reports"/run_id/f"report.{extension}";path.parent.mkdir(parents=True,exist_ok=True);_write_report(path,format,payload)
    return store.insert_document("reports",{"run_id":run_id,"report_type":"single_model","format":format,"artifact_path":str(path),"generator_version":"1.2.0","generated_at":datetime.now(timezone.utc)})
