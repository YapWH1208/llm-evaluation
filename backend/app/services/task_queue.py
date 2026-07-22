from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.db.models import (
    EndpointRateWindow,
    EvaluationRun,
    ModelEndpoint,
    SampleAttempt,
    SampleAttemptStatus,
    TaskStatus,
    TaskUnit,
)


def reclaim_expired_leases(session: Session) -> int:
    """Make crashed-worker tasks claimable again without discarding sample evidence."""

    now = datetime.now(timezone.utc)
    tasks = list(
        session.scalars(
            select(TaskUnit).where(
                TaskUnit.status.in_([TaskStatus.LEASED.value, TaskStatus.RUNNING.value]),
                TaskUnit.lease_expires_at < now,
            )
        )
    )
    for task in tasks:
        task.status = TaskStatus.PENDING.value
        task.leased_by = None
        task.lease_token = None
        task.lease_expires_at = None
        task.heartbeat_at = None
        session.execute(
            update(SampleAttempt)
            .where(
                SampleAttempt.task_id == task.id,
                SampleAttempt.status == SampleAttemptStatus.RUNNING.value,
            )
            .values(status=SampleAttemptStatus.PENDING.value)
        )
    if tasks:
        session.commit()
    return len(tasks)


def claim_task(
    session: Session,
    worker_id: str,
    lease_seconds: int = 60,
    *,
    run_id: str | None = None,
) -> TaskUnit | None:
    """Atomically lease one due task, optionally restricting the claim to one run."""

    reclaim_expired_leases(session)
    now = datetime.now(timezone.utc)
    claimable = [TaskStatus.PENDING.value, TaskStatus.RETRY_SCHEDULED.value]
    query = select(TaskUnit.id).where(
        TaskUnit.status.in_(claimable),
        or_(TaskUnit.next_retry_at.is_(None), TaskUnit.next_retry_at <= now),
    )
    if run_id is not None:
        query = query.where(TaskUnit.run_id == run_id)
    candidate_ids = list(
        session.scalars(query.order_by(TaskUnit.priority.desc(), TaskUnit.created_at).limit(20))
    )
    for task_id in candidate_ids:
        task = session.get(TaskUnit, task_id)
        if task is None:
            continue
        endpoint = session.scalar(
            select(ModelEndpoint)
            .join(EvaluationRun, EvaluationRun.model_endpoint_id == ModelEndpoint.id)
            .where(EvaluationRun.id == task.run_id)
        )
        if endpoint is None or not _endpoint_has_capacity(session, endpoint):
            continue
        if not _reserve_endpoint_budget(session, endpoint, task, now):
            continue
        lease_token = str(uuid4())
        claimed = session.execute(
            update(TaskUnit)
            .where(
                TaskUnit.id == task_id,
                TaskUnit.status.in_(claimable),
                or_(TaskUnit.next_retry_at.is_(None), TaskUnit.next_retry_at <= now),
            )
            .values(
                status=TaskStatus.LEASED.value,
                leased_by=worker_id,
                lease_token=lease_token,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                heartbeat_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            session.rollback()
            continue
        session.commit()
        task = session.get(TaskUnit, task_id)
        assert task is not None
        session.refresh(task)
        return task
    return None


def heartbeat_task(
    session: Session,
    task_id: str,
    lease_token: str,
    lease_seconds: int = 60,
) -> TaskUnit | None:
    task = session.get(TaskUnit, task_id)
    now = datetime.now(timezone.utc)
    if (
        task is None
        or task.lease_token != lease_token
        or task.status not in {TaskStatus.LEASED.value, TaskStatus.RUNNING.value}
        or task.lease_expires_at is None
        or _as_utc(task.lease_expires_at) < now
    ):
        return None
    task.heartbeat_at = now
    task.lease_expires_at = now + timedelta(seconds=lease_seconds)
    session.commit()
    session.refresh(task)
    return task


def has_valid_lease(task: TaskUnit, lease_token: str, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return bool(
        task.lease_token == lease_token
        and task.status in {TaskStatus.LEASED.value, TaskStatus.RUNNING.value}
        and task.lease_expires_at is not None
        and _as_utc(task.lease_expires_at) >= now
    )


def _as_utc(value: datetime) -> datetime:
    """SQLite returns timezone-naive timestamps despite timezone-aware columns."""

    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def clear_lease(task: TaskUnit) -> None:
    task.leased_by = None
    task.lease_token = None
    task.lease_expires_at = None
    task.heartbeat_at = None


def _endpoint_has_capacity(session: Session, endpoint: ModelEndpoint) -> bool:
    active_tasks = session.scalar(
        select(func.count())
        .select_from(TaskUnit)
        .join(EvaluationRun, EvaluationRun.id == TaskUnit.run_id)
        .where(
            EvaluationRun.model_endpoint_id == endpoint.id,
            TaskUnit.status.in_([TaskStatus.LEASED.value, TaskStatus.RUNNING.value]),
        )
    ) or 0
    return active_tasks < endpoint.max_concurrency


def _reserve_endpoint_budget(
    session: Session,
    endpoint: ModelEndpoint,
    task: TaskUnit,
    now: datetime,
) -> bool:
    request_count, estimated_tokens = _task_budget(task)
    if endpoint.requests_per_minute is None and endpoint.tokens_per_minute is None:
        return True

    window_started_at = int(now.timestamp() // 60) * 60
    usage = session.scalar(
        select(EndpointRateWindow).where(
            EndpointRateWindow.model_endpoint_id == endpoint.id,
            EndpointRateWindow.window_started_at == window_started_at,
        )
    )
    existing_requests = usage.request_count if usage else 0
    existing_tokens = usage.estimated_token_count if usage else 0
    if (
        endpoint.requests_per_minute is not None
        and existing_requests + request_count > endpoint.requests_per_minute
    ):
        return False
    if (
        endpoint.tokens_per_minute is not None
        and existing_tokens + estimated_tokens > endpoint.tokens_per_minute
    ):
        return False
    if usage is None:
        usage = EndpointRateWindow(
            model_endpoint_id=endpoint.id,
            window_started_at=window_started_at,
            request_count=request_count,
            estimated_token_count=estimated_tokens,
        )
        session.add(usage)
    else:
        usage.request_count += request_count
        usage.estimated_token_count += estimated_tokens
    return True


def _task_budget(task: TaskUnit) -> tuple[int, int]:
    payload = task.payload if isinstance(task.payload, dict) else {}
    sample_ids = payload.get("retry_sample_ids") or payload.get("sample_ids") or []
    fallback_requests = len([item for item in sample_ids if isinstance(item, str)])
    request_count = payload.get("estimated_request_count", fallback_requests)
    estimated_tokens = payload.get("estimated_token_count", 0)
    try:
        request_count = max(1, int(request_count))
    except (TypeError, ValueError):
        request_count = max(1, fallback_requests)
    try:
        estimated_tokens = max(0, int(estimated_tokens))
    except (TypeError, ValueError):
        estimated_tokens = 0
    if payload.get("retry_sample_ids"):
        estimated_tokens = max(1, estimated_tokens // max(1, fallback_requests))
        request_count = fallback_requests
    return request_count, estimated_tokens
