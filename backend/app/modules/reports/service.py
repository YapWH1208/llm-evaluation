from __future__ import annotations

import csv
import base64
import hashlib
import hmac
import html
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import secrets
from typing import Any
from uuid import uuid4

from app.core.errors import AccessDeniedError, ConflictError, NotFoundError, ValidationError
from app.modules.benchmarks.metrics import METRIC_PROFILE_VERSION, metric_definition
from app.modules.evaluations.analysis import build_repository_run_summary
from app.modules.evaluations.ports import EvaluationRepository
from app.modules.reports.ports import ReportRepository
from app.version import VERSION


_FORMAT_EXTENSIONS = {"json": "json", "csv": "csv", "html": "html", "markdown": "md"}
REPORT_TYPES = frozenset(
    {
        "single_model",
        "multi_model_comparison",
        "regression",
        "prompt_comparison",
        "benchmark",
        "reliability",
        "cost",
        "human_review",
    }
)
_COMPARISON_REPORT_TYPES = frozenset({"multi_model_comparison", "regression", "prompt_comparison"})
_PASSWORD_WINDOW = timedelta(minutes=5)
_PASSWORD_ATTEMPT_LIMIT = 5


class ReportService:
    """Report generation, sharing, and artifact lifecycle shared by all adapters."""

    def __init__(self, repository: ReportRepository, evaluations: EvaluationRepository, *, data_root: str) -> None:
        self._repository = repository
        self._evaluations = evaluations
        self._data_root = data_root

    def generate(
        self,
        run_id: str,
        format: str,
        *,
        report_type: str = "single_model",
        related_run_ids: list[str] | None = None,
    ) -> Any:
        run = self._require_run(run_id)
        if run["status"] not in {"completed", "completed_with_errors", "generating_report"}:
            raise ConflictError("Reports can only be generated after a run completes.")
        extension = _FORMAT_EXTENSIONS.get(format)
        if extension is None:
            raise ConflictError("Supported report formats are json, csv, html, and markdown.")
        if report_type not in REPORT_TYPES:
            raise ConflictError("Unsupported report type.")
        related_runs = self._related_run_overviews(run, related_run_ids or [])
        if report_type in _COMPARISON_REPORT_TYPES and not related_runs:
            raise ConflictError(f"{report_type} reports require at least one related completed run.")
        payload = self._build_report_payload(run)
        payload.update({"report_type": report_type, "related_runs": related_runs})
        report_id = str(uuid4())
        path = Path(self._data_root).resolve() / "reports" / run_id / f"{report_id}.{extension}"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            _write_report(path, format, payload)
            report = self._repository.create_report(
                {
                    "id": report_id,
                    "run_id": run_id,
                    "report_type": report_type,
                    "format": format,
                    "artifact_path": str(path),
                    "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "generator_version": VERSION,
                    "generated_at": datetime.now(timezone.utc),
                }
            )
            return _mapping(report)
        except Exception:
            path.unlink(missing_ok=True)
            raise

    def list_for_run(self, run_id: str) -> list[Any]:
        return [_mapping(report) for report in self._repository.list_reports(run_id)]

    def create_share(self, report_id: str, payload: Any, *, base_url: str) -> dict[str, Any]:
        report = self._require_report(report_id)
        if _value(report, "format") in {"json", "csv"} and not (payload.include_evidence and payload.allow_download):
            raise ConflictError(
                "Raw-evidence JSON/CSV reports require explicit evidence sharing and download permission."
            )
        now = datetime.now(timezone.utc)
        expires_at = payload.expires_at or now + timedelta(days=7)
        if _as_utc(expires_at) <= now:
            raise ValidationError("Share expiration must be in the future.")
        token = secrets.token_urlsafe(32)
        password = payload.password.get_secret_value() if payload.password is not None else None
        share = self._repository.create_share(
            {
                "id": str(uuid4()),
                "report_id": report_id,
                "token_hash": _hash_value(token),
                "password_hash": _hash_password(password) if password else None,
                "expires_at": expires_at,
                "allow_download": payload.allow_download,
                "revoked_at": None,
                "created_at": now,
            }
        )
        return _share_response(share, base_url=base_url, token=token)

    def list_shares(self, report_id: str, *, base_url: str) -> list[dict[str, Any]]:
        self._require_report(report_id)
        return [_share_response(share, base_url=base_url) for share in self._repository.list_shares(report_id)]

    def revoke_share(self, report_id: str, share_id: str, *, base_url: str) -> dict[str, Any]:
        share = self._repository.get_share(share_id)
        if share is None or str(_value(share, "report_id")) != report_id:
            raise NotFoundError("Report share not found", context={"report_id": report_id, "share_id": share_id})
        updated = self._repository.update_share(share_id, {"revoked_at": datetime.now(timezone.utc)})
        if updated is None:
            raise NotFoundError("Report share not found", context={"report_id": report_id, "share_id": share_id})
        return _share_response(updated, base_url=base_url)

    def download(self, report_id: str) -> tuple[Path, str, bool]:
        return _report_file(self._require_report(report_id), download=True)

    def delete(self, report_id: str) -> None:
        report = self._require_report(report_id)
        delete_report_artifact(self._data_root, str(_value(report, "artifact_path")))
        if not self._repository.delete_report(report_id):
            raise NotFoundError("Report not found", context={"report_id": report_id})

    def open_shared(self, token: str, *, supplied_password: str, client_host: str) -> tuple[Path, str, bool]:
        share = self._repository.find_share_by_token_hash(_hash_value(token))
        now = datetime.now(timezone.utc)
        if share is None or _value(share, "revoked_at") is not None or _as_utc(_value(share, "expires_at")) <= now:
            raise NotFoundError("Shared report not found or expired")
        password_hash = _value(share, "password_hash")
        if password_hash is not None:
            share_id = str(_value(share, "id"))
            client_key = _hash_value(client_host)
            if self._repository.password_attempt_limit_reached(
                share_id=share_id, client_key=client_key, now=now, limit=_PASSWORD_ATTEMPT_LIMIT
            ):
                raise AccessDeniedError("Shared report access was denied")
            valid, needs_upgrade = _verify_share_password(supplied_password, str(password_hash))
            if not valid:
                self._repository.record_password_failure(
                    share_id=share_id,
                    client_key=client_key,
                    now=now,
                    window=_PASSWORD_WINDOW,
                    limit=_PASSWORD_ATTEMPT_LIMIT,
                )
                raise AccessDeniedError("Shared report access was denied")
            if needs_upgrade:
                updated = self._repository.update_share(share_id, {"password_hash": _hash_password(supplied_password)})
                if updated is not None:
                    share = updated
        report = self._require_report(str(_value(share, "report_id")))
        return _report_file(report, download=bool(_value(share, "allow_download")))

    def _require_run(self, run_id: str) -> dict[str, Any]:
        run = self._evaluations.get_run(run_id)
        if run is None:
            raise NotFoundError("Evaluation run not found.", context={"run_id": run_id})
        return run

    def _require_report(self, report_id: str) -> Any:
        report = self._repository.get_report(report_id)
        if report is None:
            raise NotFoundError("Report not found", context={"report_id": report_id})
        return report

    def _related_run_overviews(self, primary_run: dict[str, Any], related_run_ids: list[str]) -> list[dict[str, Any]]:
        overviews: list[dict[str, Any]] = []
        seen = {str(primary_run["id"])}
        for run_id in related_run_ids:
            if not isinstance(run_id, str) or not run_id or run_id in seen:
                continue
            seen.add(run_id)
            run = self._evaluations.get_run(run_id)
            if run is None:
                raise NotFoundError(f"Related evaluation run not found: {run_id}", context={"run_id": run_id})
            if run["status"] not in {"completed", "completed_with_errors"}:
                raise ConflictError("Related runs must be completed before report generation.")
            configuration = run.get("configuration_snapshot")
            configuration = configuration if isinstance(configuration, dict) else {}
            overviews.append(
                {
                    "run_id": run_id,
                    "benchmark": {"id": run["benchmark_id"], "version": run["benchmark_version"]},
                    "model_endpoint_id": run["model_endpoint_id"],
                    "status": run["status"],
                    "prompt_standardization": configuration.get("prompt_standardization"),
                    "summary": build_repository_run_summary(self._evaluations, run_id),
                }
            )
        return overviews

    def _build_report_payload(self, run: dict[str, Any]) -> dict[str, Any]:
        run_id = str(run["id"])
        attempts = self._evaluations.list_attempts(run_id)
        latest_ids: dict[str, str] = {}
        for attempt in attempts:
            latest_ids[str(attempt["sample_id"])] = str(attempt["id"])
        attempt_ids = [str(attempt["id"]) for attempt in attempts]
        reviews_by_attempt: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for review in self._evaluations.list_reviews(attempt_ids):
            reviews_by_attempt[str(review["sample_attempt_id"])].append(_serialize_review(review))
        judges_by_attempt: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for assessment in self._evaluations.list_judge_assessments(attempt_ids):
            judges_by_attempt[str(assessment["sample_attempt_id"])].append(_serialize_assessment(assessment))
        return {
            "run_id": run_id,
            "benchmark": {"id": run["benchmark_id"], "version": run["benchmark_version"]},
            "model_endpoint_id": run["model_endpoint_id"],
            "status": run["status"],
            "configuration_snapshot": run.get("configuration_snapshot", {}),
            "summary": build_repository_run_summary(self._evaluations, run_id),
            "attempts": [
                _serialize_attempt(
                    attempt,
                    is_latest=latest_ids[str(attempt["sample_id"])] == str(attempt["id"]),
                    human_reviews=reviews_by_attempt[str(attempt["id"])],
                    judge_assessments=judges_by_attempt[str(attempt["id"])],
                )
                for attempt in attempts
            ],
            "metrics": [_serialize_metric(metric) for metric in self._evaluations.list_metrics(run_id)],
        }


def delete_report_artifact(data_root: str, artifact_path: str) -> None:
    """Delete only an artifact that remains within this deployment's report root."""

    reports_root = Path(data_root).resolve() / "reports"
    path = Path(artifact_path).resolve()
    try:
        path.relative_to(reports_root)
    except ValueError:
        return
    path.unlink(missing_ok=True)


def _serialize_attempt(
    attempt: dict[str, Any],
    *,
    is_latest: bool,
    human_reviews: list[dict[str, Any]],
    judge_assessments: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "sample_id": attempt["sample_id"],
        "attempt": attempt["attempt_number"],
        "is_latest": is_latest,
        "status": attempt["status"],
        "input": attempt["input_snapshot"],
        "reference": attempt["reference_snapshot"],
        "request": attempt.get("request_snapshot"),
        "raw_response": attempt.get("raw_response"),
        "prediction": attempt.get("parsed_prediction"),
        "score": attempt.get("score"),
        "latency_ms": attempt.get("latency_ms"),
        "input_tokens": attempt.get("input_tokens"),
        "output_tokens": attempt.get("output_tokens"),
        "estimated_cost": attempt.get("estimated_cost"),
        "error_type": attempt.get("error_type"),
        "error_message": attempt.get("error_message"),
        "human_reviews": human_reviews,
        "judge_assessments": judge_assessments,
        "created_at": _isoformat(attempt.get("created_at")),
        "completed_at": _isoformat(attempt.get("completed_at")),
    }


def _serialize_review(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "reviewer_id": review.get("reviewer_id"),
        "rubric": review.get("rubric"),
        "score": review.get("score"),
        "labels": review.get("labels", []),
        "notes": review.get("notes"),
        "review_stage": review.get("review_stage", "primary"),
        "adjudicates_review_ids": review.get("adjudicates_review_ids", []),
        "created_at": _isoformat(review.get("created_at")),
    }


def _serialize_assessment(assessment: dict[str, Any]) -> dict[str, Any]:
    return {
        "judge_endpoint_id": assessment.get("judge_endpoint_id"),
        "comparison_sample_attempt_id": assessment.get("comparison_sample_attempt_id"),
        "rubric": assessment.get("rubric", {}),
        "answer_order": assessment.get("answer_order", []),
        "swap_test_group_id": assessment.get("swap_test_group_id"),
        "selected_answer": assessment.get("selected_answer"),
        "score": assessment.get("score"),
        "label": assessment.get("label"),
        "rationale": assessment.get("rationale"),
        "raw_response": assessment.get("raw_response"),
        "status": assessment.get("status"),
        "error_message": assessment.get("error_message"),
        "created_at": _isoformat(assessment.get("created_at")),
    }


def _share_response(share: Any, *, base_url: str, token: str | None = None) -> dict[str, Any]:
    return {
        "id": str(_value(share, "id")),
        "report_id": str(_value(share, "report_id")),
        "expires_at": _value(share, "expires_at"),
        "allow_download": bool(_value(share, "allow_download")),
        "revoked_at": _value(share, "revoked_at"),
        "created_at": _value(share, "created_at"),
        "share_url": f"{base_url}/shared-reports/{token}" if token else None,
    }


def _report_file(report: Any, *, download: bool) -> tuple[Path, str, bool]:
    path = Path(str(_value(report, "artifact_path")))
    if not path.is_file():
        raise NotFoundError("Report artifact is no longer available")
    report_format = str(_value(report, "format"))
    media_type = {
        "json": "application/json",
        "csv": "text/csv",
        "html": "text/html",
        "markdown": "text/markdown",
    }.get(report_format, "application/octet-stream")
    return path, media_type, download


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_password(value: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(value.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$16384$8$1$" + base64.b64encode(salt).decode("ascii") + "$" + base64.b64encode(digest).decode("ascii")


def _verify_share_password(supplied: str, encoded: str) -> tuple[bool, bool]:
    """Return whether a password is valid and whether its legacy hash needs upgrading."""

    valid = False
    legacy = not encoded.startswith("scrypt$")
    if encoded.startswith("scrypt$"):
        try:
            _, n, r, p, salt, digest = encoded.split("$", 5)
            computed = hashlib.scrypt(
                supplied.encode("utf-8"),
                salt=base64.b64decode(salt),
                n=int(n),
                r=int(r),
                p=int(p),
                dklen=len(base64.b64decode(digest)),
            )
            valid = hmac.compare_digest(computed, base64.b64decode(digest))
        except (ValueError, TypeError):
            valid = False
    else:
        valid = hmac.compare_digest(_hash_value(supplied), encoded)
    return valid, valid and legacy


def _value(item: Any, key: str, default: Any = None) -> Any:
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


def _mapping(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    return {column.name: getattr(item, column.name) for column in item.__table__.columns}


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _isoformat(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


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
                    availability=_markdown_cell(
                        metric["availability_reason"] if metric["metric_value"] is None else "—"
                    ),
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
        rows.extend(
            [
                "",
                "## Related completed runs",
                "",
                "| Run | Benchmark | Accuracy | Success | Estimated cost |",
                "| --- | --- | ---: | ---: | ---: |",
            ]
        )
        for related in payload["related_runs"]:
            summary = related["summary"]
            rows.append(
                f"| `{related['run_id']}` | {related['benchmark']['id']} | {_display_percent(summary['samples']['accuracy'])} | {_display_percent(summary['samples']['success_rate'])} | {_display(summary['cost']['estimated'])} |"
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
<h1>{html.escape(_report_title(payload))}: {html.escape(payload["benchmark"]["id"])}</h1>
<p>Run {html.escape(payload["run_id"])} · Status: <strong>{html.escape(payload["status"])}</strong></p>
<h2>Executive summary</h2>
<div class=\"metrics\">
<div class=\"metric\"><strong>Completion</strong><br>{samples["completed"]}/{samples["total"]} ({_display_percent(samples["completion_rate"])})</div>
<div class=\"metric\"><strong>Accuracy</strong><br>{_display_percent(samples["accuracy"])}</div>
<div class=\"metric\"><strong>Avg / P95 latency</strong><br>{_display(latency["average"])} / {_display(latency["p95"])} ms</div>
<div class=\"metric\"><strong>Tokens in / out</strong><br>{tokens["input"]} / {tokens["output"]}</div>
<div class=\"metric\"><strong>Estimated cost</strong><br>{_display(cost["estimated"])} {html.escape(cost["currency"] or "")}</div>
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
