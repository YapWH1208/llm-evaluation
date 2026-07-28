from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db.mongo import MongoDocumentStore
from app.services.mongo_run_executor import MongoRunExecutionError, build_mongo_run_summary
from app.services.reports import REPORT_TYPES, _COMPARISON_REPORT_TYPES, ReportError, _FORMAT_EXTENSIONS, _write_report


def generate_mongo_report(store: MongoDocumentStore, run_id: str, format: str, data_root: str, *, report_type: str = "single_model", related_run_ids: list[str] | None = None) -> dict[str, Any]:
    run=store.get_document("evaluation_runs",run_id)
    if run is None: raise ReportError("Evaluation run not found.")
    if run["status"] not in {"completed","completed_with_errors","generating_report"}: raise ReportError("Reports can only be generated after a run completes.")
    extension=_FORMAT_EXTENSIONS.get(format)
    if extension is None: raise ReportError("Supported report formats are json, csv, parquet, html, markdown, and pdf.")
    if report_type not in REPORT_TYPES: raise ReportError("Unsupported report type.")
    attempts=store.list_documents("sample_attempts",query={"run_id":run_id},sort=[("sample_id",1),("attempt_number",1)])
    latest={}
    for item in reversed(attempts): latest.setdefault(item["sample_id"],item["id"])
    related=[]
    for related_id in related_run_ids or []:
        if related_id == run_id or any(item["run_id"] == related_id for item in related): continue
        related_run=store.get_document("evaluation_runs",related_id)
        if related_run is None: raise ReportError(f"Related evaluation run not found: {related_id}")
        if related_run["status"] not in {"completed","completed_with_errors"}: raise ReportError("Related runs must be completed before report generation.")
        related.append({"run_id":related_id,"benchmark":{"id":related_run["benchmark_id"],"version":related_run["benchmark_version"]},"model_endpoint_id":related_run["model_endpoint_id"],"status":related_run["status"],"prompt_standardization":related_run.get("configuration_snapshot",{}).get("prompt_standardization"),"summary":build_mongo_run_summary(store,related_id)})
    if report_type in _COMPARISON_REPORT_TYPES and not related: raise ReportError(f"{report_type} reports require at least one related completed run.")
    payload={"report_type":report_type,"related_runs":related,"run_id":run_id,"benchmark":{"id":run["benchmark_id"],"version":run["benchmark_version"]},"model_endpoint_id":run["model_endpoint_id"],"status":run["status"],"configuration_snapshot":run["configuration_snapshot"],"summary":build_mongo_run_summary(store,run_id),"attempts":[{"sample_id":item["sample_id"],"attempt":item["attempt_number"],"is_latest":latest[item["sample_id"]]==item["id"],"status":item["status"],"input":item["input_snapshot"],"reference":item["reference_snapshot"],"request":item.get("request_snapshot"),"raw_response":item.get("raw_response"),"prediction":item.get("parsed_prediction"),"score":item.get("score"),"latency_ms":item.get("latency_ms"),"input_tokens":item.get("input_tokens"),"output_tokens":item.get("output_tokens"),"estimated_cost":item.get("estimated_cost"),"error_type":item.get("error_type"),"error_message":item.get("error_message"),"human_reviews":[{"reviewer_id":review.get("reviewer_id"),"rubric":review.get("rubric"),"score":review.get("score"),"labels":review.get("labels",[]),"notes":review.get("notes"),"review_stage":review.get("review_stage","primary"),"adjudicates_review_ids":review.get("adjudicates_review_ids",[]),"created_at":review.get("created_at").isoformat() if review.get("created_at") else None} for review in store.list_documents("human_reviews",query={"sample_attempt_id":item["id"]})],"judge_assessments":[{"judge_endpoint_id":assessment.get("judge_endpoint_id"),"comparison_sample_attempt_id":assessment.get("comparison_sample_attempt_id"),"rubric":assessment.get("rubric",{}),"answer_order":assessment.get("answer_order",[]),"swap_test_group_id":assessment.get("swap_test_group_id"),"selected_answer":assessment.get("selected_answer"),"score":assessment.get("score"),"label":assessment.get("label"),"rationale":assessment.get("rationale"),"raw_response":assessment.get("raw_response"),"status":assessment.get("status"),"error_message":assessment.get("error_message"),"created_at":assessment.get("created_at").isoformat() if assessment.get("created_at") else None} for assessment in store.list_documents("judge_assessments",query={"sample_attempt_id":item["id"]})],"created_at":item.get("created_at").isoformat() if item.get("created_at") else None,"completed_at":item.get("completed_at").isoformat() if item.get("completed_at") else None} for item in attempts]}
    path=Path(data_root).resolve()/"reports"/run_id/f"{report_type}.{extension}";path.parent.mkdir(parents=True,exist_ok=True);_write_report(path,format,payload)
    return store.insert_document("reports",{"run_id":run_id,"report_type":report_type,"format":format,"artifact_path":str(path),"generator_version":"1.3.0","generated_at":datetime.now(timezone.utc)})
