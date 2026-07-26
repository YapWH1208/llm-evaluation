from __future__ import annotations

import csv
import html
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EvaluationRun, HumanReview, JudgeAssessment, Report, SampleAttempt
from app.services.run_analysis import all_attempts, build_run_summary, latest_attempts


class ReportError(ValueError):
    pass


_FORMAT_EXTENSIONS = {"json": "json", "csv": "csv", "html": "html", "markdown": "md", "pdf": "pdf"}


def generate_report(session: Session, run_id: str, format: str, data_root: str) -> Report:
    run = session.get(EvaluationRun, run_id)
    if run is None:
        raise ReportError("Evaluation run not found.")
    if run.status not in {"completed", "completed_with_errors"}:
        raise ReportError("Reports can only be generated after a run completes.")
    extension = _FORMAT_EXTENSIONS.get(format)
    if extension is None:
        raise ReportError("Supported report formats are json, csv, html, markdown, and pdf.")

    payload = _build_report_payload(session, run)
    directory = Path(data_root).resolve() / "reports" / run.id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"report.{extension}"
    _write_report(path, format, payload)

    report = Report(
        run_id=run.id,
        report_type="single_model",
        format=format,
        artifact_path=str(path),
        generator_version="1.1.0",
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


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
                "created_at": review.created_at.isoformat() if review.created_at else None,
            }
        )
    judges_by_attempt: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for assessment in session.scalars(
        select(JudgeAssessment).join(SampleAttempt).where(SampleAttempt.run_id == run.id)
    ):
        judges_by_attempt[assessment.sample_attempt_id].append(
            {
                "judge_endpoint_id": assessment.judge_endpoint_id,
                "rubric": assessment.rubric,
                "score": assessment.score,
                "label": assessment.label,
                "rationale": assessment.rationale,
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
    if format == "pdf":
        path.write_bytes(_pdf_report(payload))
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
            writer.writerow(
                {
                    key: json.dumps(attempt[key], ensure_ascii=False)
                    if key in {"input", "reference", "request", "human_reviews", "judge_assessments"}
                    else attempt[key]
                    for key in fields
                }
            )


def _markdown_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    samples = summary["samples"]
    latency = summary["latency_ms"]
    tokens = summary["tokens"]
    cost = summary["cost"]
    currency = cost["currency"] or "unconfigured currency"
    rows = [
        f"# Evaluation report: {payload['benchmark']['id']}",
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
        "## Sample evidence",
        "",
        "| Sample | Attempt | Current | Status | Score | Latency (ms) | Tokens in/out | Estimated cost | Error |",
        "| --- | ---: | --- | --- | ---: | ---: | --- | ---: | --- |",
    ]
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
<h1>{html.escape(payload['benchmark']['id'])} evaluation report</h1>
<p>Run {html.escape(payload['run_id'])} · Status: <strong>{html.escape(payload['status'])}</strong></p>
<h2>Executive summary</h2>
<div class=\"metrics\">
<div class=\"metric\"><strong>Completion</strong><br>{samples['completed']}/{samples['total']} ({_display_percent(samples['completion_rate'])})</div>
<div class=\"metric\"><strong>Accuracy</strong><br>{_display_percent(samples['accuracy'])}</div>
<div class=\"metric\"><strong>Avg / P95 latency</strong><br>{_display(latency['average'])} / {_display(latency['p95'])} ms</div>
<div class=\"metric\"><strong>Tokens in / out</strong><br>{tokens['input']} / {tokens['output']}</div>
<div class=\"metric\"><strong>Estimated cost</strong><br>{_display(cost['estimated'])} {html.escape(cost['currency'] or '')}</div>
</div>
<h2>Sample evidence</h2>
<table><thead><tr><th>Sample</th><th>Attempt</th><th>Current</th><th>Status</th><th>Score</th><th>Latency (ms)</th><th>Tokens</th><th>Estimated cost</th><th>Error</th></tr></thead><tbody>{table_rows}</tbody></table>
</body></html>"""


def _pdf_report(payload: dict[str, Any]) -> bytes:
    summary = payload["summary"]
    samples = summary["samples"]
    latency = summary["latency_ms"]
    cost = summary["cost"]
    lines = [
        f"Evaluation report: {payload['benchmark']['id']}",
        f"Run: {payload['run_id']}",
        f"Status: {payload['status']}",
        "",
        "Executive summary",
        f"Completion: {samples['completed']}/{samples['total']} ({_display_percent(samples['completion_rate'])})",
        f"Accuracy: {_display_percent(samples['accuracy'])}",
        f"Success rate: {_display_percent(samples['success_rate'])}",
        f"Average latency: {_display(latency['average'])} ms; P95: {_display(latency['p95'])} ms",
        f"Tokens (input/output): {summary['tokens']['input']}/{summary['tokens']['output']}",
        f"Estimated cost: {_display(cost['estimated'])} {cost['currency'] or ''}",
        "",
        "Sample outcomes",
    ]
    lines.extend(
        f"{attempt['sample_id']} | attempt {attempt['attempt']} | {attempt['status']} | score {_display(attempt['score'])} | {_display(attempt['latency_ms'])} ms"
        for attempt in payload["attempts"][:25]
    )
    content_lines = ["BT", "/F1 12 Tf", "50 760 Td", "15 TL"]
    for index, line in enumerate(lines):
        if index:
            content_lines.append("T*")
        content_lines.append(f"({_pdf_escape(line)}) Tj")
    content_lines.append("ET")
    content = "\n".join(content_lines).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, object_data in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode())
        output.extend(object_data)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode())
    return bytes(output)


def _pdf_escape(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


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
