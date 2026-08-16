from __future__ import annotations

import csv
import hashlib
import html
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EvaluationRun, HumanReview, JudgeAssessment, Report, SampleAttempt
from app.services.aggregation import list_aggregate_metrics
from app.services.metric_profiles import METRIC_PROFILE_VERSION, metric_definition
from app.services.run_analysis import all_attempts, build_run_summary, latest_attempts


class ReportError(ValueError):
    pass


_FORMAT_EXTENSIONS = {"json": "json", "csv": "csv", "html": "html", "markdown": "md"}
REPORT_TYPES = frozenset({"single_model", "multi_model_comparison", "regression", "prompt_comparison", "benchmark", "reliability", "cost", "human_review"})
_COMPARISON_REPORT_TYPES = frozenset({"multi_model_comparison", "regression", "prompt_comparison"})


def generate_report(
    session: Session,
    run_id: str,
    format: str,
    data_root: str,
    *,
    report_type: str = "single_model",
    related_run_ids: list[str] | None = None,
) -> Report:
    run = session.get(EvaluationRun, run_id)
    if run is None:
        raise ReportError("Evaluation run not found.")
    if run.status not in {"completed", "completed_with_errors", "generating_report"}:
        raise ReportError("Reports can only be generated after a run completes.")
    extension = _FORMAT_EXTENSIONS.get(format)
    if extension is None:
        raise ReportError("Supported report formats are json, csv, html, and markdown.")
    if report_type not in REPORT_TYPES:
        raise ReportError("Unsupported report type.")

    payload = _build_report_payload(session, run)
    related_runs = _related_run_overviews(session, run, related_run_ids or [])
    if report_type in _COMPARISON_REPORT_TYPES and not related_runs:
        raise ReportError(f"{report_type} reports require at least one related completed run.")
    payload["report_type"] = report_type
    payload["related_runs"] = related_runs
    report = Report(
        run_id=run.id,
        report_type=report_type,
        format=format,
        artifact_path="",
        generator_version="1.4.0",
    )
    session.add(report)
    session.flush()
    directory = Path(data_root).resolve() / "reports" / run.id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{report.id}.{extension}"
    try:
        _write_report(path, format, payload)
        report.artifact_path = str(path)
        report.artifact_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        session.commit()
    except Exception:
        session.rollback()
        path.unlink(missing_ok=True)
        raise
    session.refresh(report)
    return report


def delete_report_artifact(data_root: str, artifact_path: str) -> None:
    """Delete only an artifact that remains within this deployment's report root."""

    reports_root = Path(data_root).resolve() / "reports"
    path = Path(artifact_path).resolve()
    try:
        path.relative_to(reports_root)
    except ValueError:
        return
    path.unlink(missing_ok=True)


def _related_run_overviews(session: Session, primary_run: EvaluationRun, related_run_ids: list[str]) -> list[dict[str, Any]]:
    overviews: list[dict[str, Any]] = []
    seen = {primary_run.id}
    for run_id in related_run_ids:
        if not isinstance(run_id, str) or not run_id or run_id in seen:
            continue
        seen.add(run_id)
        run = session.get(EvaluationRun, run_id)
        if run is None:
            raise ReportError(f"Related evaluation run not found: {run_id}")
        if run.status not in {"completed", "completed_with_errors"}:
            raise ReportError("Related runs must be completed before report generation.")
        overviews.append(
            {
                "run_id": run.id,
                "benchmark": {"id": run.benchmark_id, "version": run.benchmark_version},
                "model_endpoint_id": run.model_endpoint_id,
                "status": run.status,
                "prompt_standardization": run.configuration_snapshot.get("prompt_standardization"),
                "summary": build_run_summary(session, run),
            }
        )
    return overviews


def _build_report_payload(session: Session, run: EvaluationRun) -> dict[str, Any]:
    latest_ids = {attempt.id for attempt in latest_attempts(session, run.id)}
    reviews_by_attempt: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for review in session.scalars(
        select(HumanReview).join(SampleAttempt).where(SampleAttempt.run_id == run.id)
    ):
        reviews_by_attempt[review.sample_attempt_id].append(
            {
                "reviewer_id": review.reviewer_id,
                "rubric": review.rubric,
                "score": review.score,
                "labels": review.labels,
                "notes": review.notes,
                "review_stage": review.review_stage,
                "adjudicates_review_ids": review.adjudicates_review_ids,
                "created_at": review.created_at.isoformat() if review.created_at else None,
            }
        )
    judges_by_attempt: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for assessment in session.scalars(
        select(JudgeAssessment)
        .join(SampleAttempt, JudgeAssessment.sample_attempt_id == SampleAttempt.id)
        .where(SampleAttempt.run_id == run.id)
    ):
        judges_by_attempt[assessment.sample_attempt_id].append(
            {
                "judge_endpoint_id": assessment.judge_endpoint_id,
                "comparison_sample_attempt_id": assessment.comparison_sample_attempt_id,
                "rubric": assessment.rubric,
                "answer_order": assessment.answer_order,
                "swap_test_group_id": assessment.swap_test_group_id,
                "selected_answer": assessment.selected_answer,
                "score": assessment.score,
                "label": assessment.label,
                "rationale": assessment.rationale,
                "raw_response": assessment.raw_response,
                "status": assessment.status,
                "error_message": assessment.error_message,
                "created_at": assessment.created_at.isoformat() if assessment.created_at else None,
            }
        )

    attempts = [
        _serialize_attempt(
            attempt,
            is_latest=attempt.id in latest_ids,
            human_reviews=reviews_by_attempt[attempt.id],
            judge_assessments=judges_by_attempt[attempt.id],
        )
        for attempt in all_attempts(session, run.id)
    ]
    return {
        "run_id": run.id,
        "benchmark": {"id": run.benchmark_id, "version": run.benchmark_version},
        "model_endpoint_id": run.model_endpoint_id,
        "status": run.status,
        "configuration_snapshot": run.configuration_snapshot,
        "summary": build_run_summary(session, run),
        "attempts": attempts,
        "metrics": [_serialize_metric(metric) for metric in list_aggregate_metrics(session, run.id)],
    }


def _serialize_attempt(
    attempt: SampleAttempt,
    *,
    is_latest: bool,
    human_reviews: list[dict[str, Any]],
    judge_assessments: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "sample_id": attempt.sample_id,
        "attempt": attempt.attempt_number,
        "is_latest": is_latest,
        "status": attempt.status,
        "input": attempt.input_snapshot,
        "reference": attempt.reference_snapshot,
        "request": attempt.request_snapshot,
        "raw_response": attempt.raw_response,
        "prediction": attempt.parsed_prediction,
        "score": attempt.score,
        "latency_ms": attempt.latency_ms,
        "input_tokens": attempt.input_tokens,
        "output_tokens": attempt.output_tokens,
        "estimated_cost": attempt.estimated_cost,
        "error_type": attempt.error_type,
        "error_message": attempt.error_message,
        "human_reviews": human_reviews,
        "judge_assessments": judge_assessments,
        "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
        "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
    }


def _serialize_metric(row: Any) -> dict[str, Any]:
    """Serialize an AggregateMetric row (ORM or Mongo document) with its profile enrichment."""

    get = (lambda key: row[key]) if isinstance(row, dict) else (lambda key: getattr(row, key))
    try:
        definition = metric_definition(get("metric_name"))
    except ValueError:
        metric_label = get("metric_name").replace("_", " ").title()
        unit = "value"
        profile = "custom"
        required_evidence: list[str] = []
    else:
        metric_label = definition.label
        unit = definition.unit
        profile = definition.profile
        required_evidence = list(definition.required_evidence)
    created_at = get("created_at")
    return {
        "id": get("id"),
        "run_id": get("run_id"),
        "benchmark_id": get("benchmark_id"),
        "model_endpoint_id": get("model_endpoint_id"),
        "metric_name": get("metric_name"),
        "metric_value": get("metric_value"),
        "availability_reason": get("availability_reason"),
        "sample_count": get("sample_count"),
        "confidence_interval": get("confidence_interval"),
        "aggregation_version": get("aggregation_version"),
        "profile_version": METRIC_PROFILE_VERSION,
        "created_at": created_at.isoformat() if created_at else None,
        "metric_label": metric_label,
        "unit": unit,
        "profile": profile,
        "required_evidence": required_evidence,
    }


def _write_report(path: Path, format: str, payload: dict[str, Any]) -> None:
    if format == "json":
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    if format == "csv":
        _write_csv(path, payload)
        return
    if format == "markdown":
        path.write_text(_markdown_report(payload), encoding="utf-8")
        return
    path.write_text(_html_report(payload), encoding="utf-8")


def _write_csv(path: Path, payload: dict[str, Any]) -> None:
    fields = [
        "sample_id",
        "attempt",
        "is_latest",
        "status",
        "prediction",
        "score",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "estimated_cost",
        "error_type",
        "error_message",
        "input",
        "reference",
        "request",
        "raw_response",
        "human_reviews",
        "judge_assessments",
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for attempt in payload["attempts"]:
            writer.writerow(_tabular_attempt(attempt, fields))


def _tabular_attempt(attempt: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    return {
        key: json.dumps(attempt[key], ensure_ascii=False)
        if key in {"input", "reference", "request", "human_reviews", "judge_assessments"}
        else attempt[key]
        for key in fields
    }


def _markdown_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    samples = summary["samples"]
    latency = summary["latency_ms"]
    tokens = summary["tokens"]
    cost = summary["cost"]
    currency = cost["currency"] or "unconfigured currency"
    rows = [
        f"# {_report_title(payload)}: {payload['benchmark']['id']}",
        "",
        f"Run: `{payload['run_id']}`  ",
        f"Status: **{payload['status']}**",
        "",
        "## Executive summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Completion | {samples['completed']}/{samples['total']} ({_display_percent(samples['completion_rate'])}) |",
        f"| Success rate | {_display_percent(samples['success_rate'])} |",
        f"| Accuracy | {_display_percent(samples['accuracy'])} |",
        f"| API error rate | {_display_percent(summary['errors']['api_error_rate'])} |",
        f"| Parser error rate | {_display_percent(summary['errors']['parser_error_rate'])} |",
        f"| Average latency | {_display(latency['average'])} ms |",
        f"| P50 / P95 / P99 latency | {_display(latency['p50'])} / {_display(latency['p95'])} / {_display(latency['p99'])} ms |",
        f"| Input / output tokens | {tokens['input']} / {tokens['output']} |",
        f"| Estimated cost | {_display(cost['estimated'])} {currency} |",
        "",
    ]
    if payload.get("metrics"):
        rows.extend(
            [
                "",
                "## Metrics",
                "",
                "| Metric | Value | Samples | Availability |",
                "| --- | --- | ---: | --- |",
            ]
            + [
                "| {label} | {value} | {samples} | {availability} |".format(
                    label=_markdown_cell(metric["metric_label"]),
                    value=_markdown_cell(_display(metric["metric_value"])),
                    samples=metric["sample_count"],
                    availability=_markdown_cell(metric["availability_reason"] if metric["metric_value"] is None else "—"),
                )
                for metric in payload["metrics"]
            ]
        )
    rows.extend(
        [
            "",
            "## Sample evidence",
            "",
            "| Sample | Attempt | Current | Status | Score | Latency (ms) | Tokens in/out | Estimated cost | Error |",
            "| --- | ---: | --- | --- | ---: | ---: | --- | ---: | --- |",
        ]
    )
    for attempt in payload["attempts"]:
        rows.append(
            "| {sample_id} | {attempt} | {latest} | {status} | {score} | {latency} | {input_tokens}/{output_tokens} | {cost} | {error} |".format(
                sample_id=_markdown_cell(attempt["sample_id"]),
                attempt=attempt["attempt"],
                latest="yes" if attempt["is_latest"] else "no",
                status=_markdown_cell(attempt["status"]),
                score=_display(attempt["score"]),
                latency=_display(attempt["latency_ms"]),
                input_tokens=_display(attempt["input_tokens"]),
                output_tokens=_display(attempt["output_tokens"]),
                cost=_display(attempt["estimated_cost"]),
                error=_markdown_cell(attempt["error_type"] or ""),
            )
        )
    if payload.get("related_runs"):
        rows.extend(["", "## Related completed runs", "", "| Run | Benchmark | Accuracy | Success | Estimated cost |", "| --- | --- | ---: | ---: | ---: |"])
        for related in payload["related_runs"]:
            summary = related["summary"]
            rows.append(f"| `{related['run_id']}` | {related['benchmark']['id']} | {_display_percent(summary['samples']['accuracy'])} | {_display_percent(summary['samples']['success_rate'])} | {_display(summary['cost']['estimated'])} |")
    return "\n".join(rows) + "\n"


def _html_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    samples = summary["samples"]
    latency = summary["latency_ms"]
    tokens = summary["tokens"]
    cost = summary["cost"]
    table_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(attempt['sample_id']))}</td>"
        f"<td>{attempt['attempt']}</td>"
        f"<td>{'yes' if attempt['is_latest'] else 'no'}</td>"
        f"<td>{html.escape(str(attempt['status']))}</td>"
        f"<td>{html.escape(_display(attempt['score']))}</td>"
        f"<td>{html.escape(_display(attempt['latency_ms']))}</td>"
        f"<td>{html.escape(_display(attempt['input_tokens']))}/{html.escape(_display(attempt['output_tokens']))}</td>"
        f"<td>{html.escape(_display(attempt['estimated_cost']))}</td>"
        f"<td>{html.escape(str(attempt['error_type'] or ''))}</td>"
        "</tr>"
        for attempt in payload["attempts"]
    )
    return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><title>Evaluation report</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #cbd5e1;padding:.5rem;text-align:left}}th{{background:#f1f5f9}}.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:1rem}}.metric{{padding:1rem;background:#f8fafc;border-radius:.5rem}}</style>
</head><body>
<h1>{html.escape(_report_title(payload))}: {html.escape(payload['benchmark']['id'])}</h1>
<p>Run {html.escape(payload['run_id'])} · Status: <strong>{html.escape(payload['status'])}</strong></p>
<h2>Executive summary</h2>
<div class=\"metrics\">
<div class=\"metric\"><strong>Completion</strong><br>{samples['completed']}/{samples['total']} ({_display_percent(samples['completion_rate'])})</div>
<div class=\"metric\"><strong>Accuracy</strong><br>{_display_percent(samples['accuracy'])}</div>
<div class=\"metric\"><strong>Avg / P95 latency</strong><br>{_display(latency['average'])} / {_display(latency['p95'])} ms</div>
<div class=\"metric\"><strong>Tokens in / out</strong><br>{tokens['input']} / {tokens['output']}</div>
<div class=\"metric\"><strong>Estimated cost</strong><br>{_display(cost['estimated'])} {html.escape(cost['currency'] or '')}</div>
</div>
{_metrics_html(payload)}
<h2>Sample evidence</h2>
<table><thead><tr><th>Sample</th><th>Attempt</th><th>Current</th><th>Status</th><th>Score</th><th>Latency (ms)</th><th>Tokens</th><th>Estimated cost</th><th>Error</th></tr></thead><tbody>{table_rows}</tbody></table>
{_related_runs_html(payload)}
</body></html>"""



def _metrics_html(payload: dict[str, Any]) -> str:
    metrics = payload.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        return ""
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(metric['metric_label']))}</td>"
        f"<td>{html.escape(_display(metric['metric_value']))}</td>"
        f"<td>{metric['sample_count']}</td>"
        f"<td>{html.escape(str(metric['availability_reason'] if metric['metric_value'] is None else ''))}</td>"
        "</tr>"
        for metric in metrics
    )
    return (
        "<h2>Metrics</h2>"
        "<table><thead><tr><th>Metric</th><th>Value</th><th>Samples</th><th>Availability</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _report_title(payload: dict[str, Any]) -> str:
    report_type = str(payload.get("report_type", "single_model"))
    if report_type == "single_model":
        return "Evaluation report"
    return report_type.replace("_", " ").title() + " report"


def _related_runs_html(payload: dict[str, Any]) -> str:
    related = payload.get("related_runs")
    if not isinstance(related, list) or not related:
        return ""
    rows = "".join(
        f"<tr><td>{html.escape(str(item['run_id']))}</td><td>{html.escape(str(item['benchmark']['id']))}</td><td>{html.escape(_display_percent(item['summary']['samples']['accuracy']))}</td><td>{html.escape(_display_percent(item['summary']['samples']['success_rate']))}</td></tr>"
        for item in related
    )
    return f"<h2>Related completed runs</h2><table><thead><tr><th>Run</th><th>Benchmark</th><th>Accuracy</th><th>Success</th></tr></thead><tbody>{rows}</tbody></table>"


def _display(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)


def _display_percent(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.2f}%"


def _markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
