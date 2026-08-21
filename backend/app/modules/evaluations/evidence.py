from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def decorate_attempts(
    attempts: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    reviews_by_attempt: dict[str, list[dict[str, Any]]] = {}
    judges_by_attempt: dict[str, list[dict[str, Any]]] = {}
    for review in reviews:
        reviews_by_attempt.setdefault(str(review["sample_attempt_id"]), []).append(review)
    for assessment in assessments:
        judges_by_attempt.setdefault(str(assessment["sample_attempt_id"]), []).append(assessment)

    items: list[dict[str, Any]] = []
    for attempt in attempts:
        payload = dict(attempt)
        attempt_id = str(payload["id"])
        snapshot = payload.get("input_snapshot")
        snapshot = snapshot if isinstance(snapshot, dict) else {}
        metadata = snapshot.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        attempt_reviews = reviews_by_attempt.get(attempt_id, [])
        attempt_judges = [item for item in judges_by_attempt.get(attempt_id, []) if item.get("status") == "succeeded"]
        labels = {str(item["label"]) for item in attempt_judges if item.get("label")}
        scores = [float(item["score"]) for item in attempt_judges if item.get("score") is not None]
        payload["input_snapshot"] = safe_evidence_snapshot(snapshot)
        payload["sample_metadata"] = {
            str(key): str(value) for key, value in metadata.items() if isinstance(value, (str, int, float, bool))
        }
        payload["human_review_status"] = (
            "adjudicated"
            if any(item.get("review_stage") == "adjudication" for item in attempt_reviews)
            else "reviewed"
            if attempt_reviews
            else "unreviewed"
        )
        payload["judge_disagreement"] = len(labels) > 1 or (len(scores) > 1 and max(scores) - min(scores) > 0.1)
        items.append(payload)
    return items


def safe_evidence_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Redact embedded media bytes while retaining durable asset evidence."""

    visible = dict(snapshot)
    messages = snapshot.get("messages")
    if not isinstance(messages, list):
        return visible
    visible_messages: list[Any] = []
    for message in messages:
        if not isinstance(message, dict) or not isinstance(message.get("content"), list):
            visible_messages.append(message)
            continue
        visible_parts: list[Any] = []
        for part in message["content"]:
            if not isinstance(part, dict) or not isinstance(part.get("source"), dict):
                visible_parts.append(part)
                continue
            copy_part = dict(part)
            source = dict(part["source"])
            embedded = source.pop("base64_data", None)
            if isinstance(embedded, str):
                source["embedded_media"] = {
                    "redacted": True,
                    "approximate_bytes": (len(embedded) * 3) // 4,
                }
            copy_part["source"] = source
            visible_parts.append(copy_part)
        copy_message = dict(message)
        copy_message["content"] = visible_parts
        visible_messages.append(copy_message)
    visible["messages"] = visible_messages
    return visible


def filter_attempts(
    attempts: list[dict[str, Any]],
    *,
    attempt_status: str | None = None,
    error_type: str | None = None,
    correct: bool | None = None,
    min_latency_ms: float | None = None,
    min_tokens: int | None = None,
    min_cost: float | None = None,
    capability: str | None = None,
    modality: str | None = None,
    language: str | None = None,
    difficulty: str | None = None,
    api_error: bool | None = None,
    parser_error: bool | None = None,
    judge_disagreement: bool | None = None,
    human_review_status: str | None = None,
) -> list[dict[str, Any]]:
    def matches(item: dict[str, Any]) -> bool:
        metadata = item.get("sample_metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        snapshot = item.get("input_snapshot")
        snapshot = snapshot if isinstance(snapshot, dict) else {}
        current_error = str(item.get("error_type") or "")
        is_api_error = current_error.startswith("http_") or current_error in {
            "timeout",
            "connection_error",
        }
        tokens = int(item.get("input_tokens") or 0) + int(item.get("output_tokens") or 0)
        score = item.get("score")
        return (
            (attempt_status is None or item.get("status") == attempt_status)
            and (error_type is None or item.get("error_type") == error_type)
            and (correct is None or (score == 1) == correct)
            and (min_latency_ms is None or float(item.get("latency_ms") or 0) >= min_latency_ms)
            and (capability is None or metadata.get("capability") == capability)
            and (modality is None or snapshot.get("modality") == modality)
            and (language is None or metadata.get("language") == language)
            and (difficulty is None or metadata.get("difficulty") == difficulty)
            and (api_error is None or is_api_error == api_error)
            and (parser_error is None or (current_error == "response_parse_error") == parser_error)
            and (judge_disagreement is None or bool(item.get("judge_disagreement")) == judge_disagreement)
            and (human_review_status is None or item.get("human_review_status") == human_review_status)
            and (min_tokens is None or tokens >= min_tokens)
            and (min_cost is None or float(item.get("estimated_cost") or 0) >= min_cost)
        )

    return [item for item in attempts if matches(item)]


def run_progress(run: dict[str, Any]) -> dict[str, Any]:
    total = int(run.get("total_samples") or 0)
    completed = int(run.get("completed_samples") or 0)
    return {
        "run_id": str(run["id"]),
        "status": str(run["status"]),
        "total_samples": total,
        "completed_samples": completed,
        "successful_samples": int(run.get("successful_samples") or 0),
        "failed_samples": int(run.get("failed_samples") or 0),
        "completion_rate": completed / total if total else None,
    }


def run_logs(tasks: list[dict[str, Any]], attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries = [*_task_log_entries(tasks), *_attempt_log_entries(attempts)]
    entries.sort(key=lambda entry: _as_log_timestamp(entry["timestamp"]))
    return entries


def _task_log_entries(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for task in tasks:
        payload = task.get("payload")
        safe_payload = payload if isinstance(payload, dict) else {}
        status_value = str(task.get("status") or "unknown")
        task_type = str(task.get("task_type") or "task")
        error = safe_payload.get("dataset_error") or safe_payload.get("report_error")
        entries.append(
            {
                "timestamp": task.get("updated_at") or task.get("created_at"),
                "level": "error" if status_value == "failed" or error else "info",
                "event": "task.lifecycle",
                "message": str(error) if error else f"{task_type} task is {status_value}.",
                "task_id": str(task["id"]),
                "sample_attempt_id": None,
                "details": {
                    "task_type": task_type,
                    "status": status_value,
                    "attempt_count": int(task.get("attempt_count") or 0),
                    "worker_id": task.get("leased_by"),
                },
            }
        )
    return entries


def _attempt_log_entries(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for attempt in attempts:
        status_value = str(attempt.get("status") or "unknown")
        error_type = attempt.get("error_type")
        error_message = attempt.get("error_message")
        entries.append(
            {
                "timestamp": attempt.get("completed_at") or attempt.get("started_at") or attempt.get("created_at"),
                "level": "error" if status_value == "failed" else "info",
                "event": "sample.lifecycle",
                "message": (
                    f"{error_type}: {error_message}"
                    if error_type
                    else f"Sample {attempt.get('sample_id')} is {status_value}."
                ),
                "task_id": str(attempt["task_id"]) if attempt.get("task_id") else None,
                "sample_attempt_id": str(attempt["id"]),
                "details": {
                    "sample_id": attempt.get("sample_id"),
                    "attempt_number": int(attempt.get("attempt_number") or 1),
                    "status": status_value,
                },
            }
        )
    return entries


def _as_log_timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return datetime.min.replace(tzinfo=timezone.utc)
