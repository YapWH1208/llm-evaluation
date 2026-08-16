from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.orm import Session

from app.db.models import (
    EndpointRateWindow,
    EndpointSecondRateWindow,
    BenchmarkDefinition,
    EvaluationRun,
    ModelEndpoint,
    SampleAttempt,
    SampleAttemptStatus,
    TaskStatus,
    TaskType,
    TaskUnit,
    User,
)


def reclaim_expired_leases(session: Session, *, commit: bool = True) -> int:
    """Make crashed-worker tasks claimable again without discarding sample evidence."""

    if commit:
        _begin_admission_transaction(session)
    now = datetime.now(timezone.utc)
    candidates = list(
        session.scalars(
            select(TaskUnit).where(
                TaskUnit.status.in_([TaskStatus.LEASED.value, TaskStatus.RUNNING.value]),
                TaskUnit.lease_expires_at < now,
            )
        )
    )
    reclaimed = 0
    for task in candidates:
        result = session.execute(
            update(TaskUnit)
            .where(
                TaskUnit.id == task.id,
                TaskUnit.lease_version == task.lease_version,
                TaskUnit.status.in_([TaskStatus.LEASED.value, TaskStatus.RUNNING.value]),
                TaskUnit.lease_expires_at < now,
            )
            .values(
                status=TaskStatus.PENDING.value,
                leased_by=None,
                lease_token=None,
                lease_expires_at=None,
                heartbeat_at=None,
                lease_version=TaskUnit.lease_version + 1,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            continue
        reclaimed += 1
        session.execute(
            update(SampleAttempt)
            .where(
                SampleAttempt.task_id == task.id,
                SampleAttempt.status == SampleAttemptStatus.RUNNING.value,
            )
            .values(status=SampleAttemptStatus.PENDING.value)
        )
    if commit:
        session.commit()
        session.expire_all()
    return reclaimed


def claim_task(
    session: Session,
    worker_id: str,
    lease_seconds: int = 60,
    *,
    run_id: str | None = None,
    system_max_concurrency: int | None = None,
    worker_max_concurrency: int | None = None,
) -> TaskUnit | None:
    """Atomically lease one due task, optionally restricting the claim to one run."""

    _begin_admission_transaction(session)
    reclaim_expired_leases(session, commit=False)
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
        if task.parent_task_id:
            parent = session.get(TaskUnit, task.parent_task_id)
            if parent is None or parent.status != TaskStatus.SUCCEEDED.value:
                continue
        endpoint = session.scalar(
            select(ModelEndpoint)
            .join(EvaluationRun, EvaluationRun.model_endpoint_id == ModelEndpoint.id)
            .where(EvaluationRun.id == task.run_id)
        )
        if endpoint is None or not _has_execution_capacity(
            session,
            endpoint,
            task=task,
            worker_id=worker_id,
            system_max_concurrency=system_max_concurrency,
            worker_max_concurrency=worker_max_concurrency,
        ):
            continue
        if not _reserve_endpoint_budget(session, endpoint, task, now):
            continue
        lease_token = str(uuid4())
        claimed = session.execute(
            update(TaskUnit)
            .where(
                TaskUnit.id == task_id,
                TaskUnit.lease_version == task.lease_version,
                TaskUnit.status.in_(claimable),
                or_(TaskUnit.next_retry_at.is_(None), TaskUnit.next_retry_at <= now),
            )
            .values(
                status=TaskStatus.LEASED.value,
                leased_by=worker_id,
                lease_token=lease_token,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                heartbeat_at=now,
                lease_version=TaskUnit.lease_version + 1,
            )
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            session.rollback()
            return claim_task(
                session,
                worker_id,
                lease_seconds,
                run_id=run_id,
                system_max_concurrency=system_max_concurrency,
                worker_max_concurrency=worker_max_concurrency,
            )
        session.commit()
        session.expire_all()
        task = session.get(TaskUnit, task_id)
        assert task is not None
        session.refresh(task)
        return task
    session.commit()
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
    updated = session.execute(
        update(TaskUnit)
        .where(
            TaskUnit.id == task_id,
            TaskUnit.lease_token == lease_token,
            TaskUnit.lease_version == task.lease_version,
            TaskUnit.status.in_([TaskStatus.LEASED.value, TaskStatus.RUNNING.value]),
            TaskUnit.lease_expires_at >= now,
        )
        .values(
            heartbeat_at=now,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
        )
        .execution_options(synchronize_session=False)
    )
    if updated.rowcount != 1:
        session.rollback()
        return None
    session.commit()
    session.expire_all()
    return session.get(TaskUnit, task_id)


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


def _begin_admission_transaction(session: Session) -> None:
    """Serialize capacity and rate reservations across all relational workers.

    SQLite has no row locks, so an immediate write transaction is the
    equivalent safe single-writer gate. ``claim_task`` already commits
    independently, therefore closing a caller's read-only transaction before
    acquiring this gate preserves its contract.
    """

    if session.in_transaction():
        session.commit()
    session.execute(text("BEGIN IMMEDIATE"))


def _has_execution_capacity(
    session: Session,
    endpoint: ModelEndpoint,
    *,
    task: TaskUnit,
    worker_id: str,
    system_max_concurrency: int | None,
    worker_max_concurrency: int | None,
) -> bool:
    active_statuses = [TaskStatus.LEASED.value, TaskStatus.RUNNING.value]
    run = session.get(EvaluationRun, task.run_id)
    if run is None:
        return False
    if system_max_concurrency is not None:
        system_active = session.scalar(
            select(func.count()).select_from(TaskUnit).where(TaskUnit.status.in_(active_statuses))
        ) or 0
        if system_active >= system_max_concurrency:
            return False
    if worker_max_concurrency is not None:
        worker_active = session.scalar(
            select(func.count()).select_from(TaskUnit).where(
                TaskUnit.status.in_(active_statuses), TaskUnit.leased_by == worker_id
            )
        ) or 0
        if worker_active >= worker_max_concurrency:
            return False
    if run.max_concurrency is not None:
        run_active = session.scalar(
            select(func.count()).select_from(TaskUnit).where(
                TaskUnit.status.in_(active_statuses), TaskUnit.run_id == run.id
            )
        ) or 0
        if run_active >= run.max_concurrency:
            return False
    if run.created_by:
        user = session.get(User, run.created_by)
        if user is not None and user.max_concurrency is not None:
            user_active = session.scalar(
                select(func.count())
                .select_from(TaskUnit)
                .join(EvaluationRun, EvaluationRun.id == TaskUnit.run_id)
                .where(TaskUnit.status.in_(active_statuses), EvaluationRun.created_by == run.created_by)
            ) or 0
            if user_active >= user.max_concurrency:
                return False
    if endpoint.api_key_max_concurrency is not None and endpoint.api_key_fingerprint:
        credential_active = session.scalar(
            select(func.count())
            .select_from(TaskUnit)
            .join(EvaluationRun, EvaluationRun.id == TaskUnit.run_id)
            .join(ModelEndpoint, ModelEndpoint.id == EvaluationRun.model_endpoint_id)
            .where(
                TaskUnit.status.in_(active_statuses),
                ModelEndpoint.api_key_fingerprint == endpoint.api_key_fingerprint,
            )
        ) or 0
        if credential_active >= endpoint.api_key_max_concurrency:
            return False
    benchmark = session.scalar(
        select(BenchmarkDefinition).where(
            BenchmarkDefinition.benchmark_id == run.benchmark_id,
            BenchmarkDefinition.version == run.benchmark_version,
        )
    )
    benchmark_limit = _positive_limit((benchmark.manifest if benchmark is not None else {}).get("max_concurrency"))
    if benchmark_limit is not None:
        benchmark_active = session.scalar(
            select(func.count())
            .select_from(TaskUnit)
            .join(EvaluationRun, EvaluationRun.id == TaskUnit.run_id)
            .where(
                TaskUnit.status.in_(active_statuses),
                EvaluationRun.benchmark_id == run.benchmark_id,
                EvaluationRun.benchmark_version == run.benchmark_version,
            )
        ) or 0
        if benchmark_active >= benchmark_limit:
            return False
    active_tasks = session.scalar(
        select(func.count())
        .select_from(TaskUnit)
        .join(EvaluationRun, EvaluationRun.id == TaskUnit.run_id)
        .where(
            EvaluationRun.model_endpoint_id == endpoint.id,
            TaskUnit.status.in_(active_statuses),
        )
    ) or 0
    return active_tasks < endpoint.max_concurrency


def _positive_limit(value: object) -> int | None:
    try:
        limit = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return limit if limit > 0 else None


def _reserve_endpoint_budget(
    session: Session,
    endpoint: ModelEndpoint,
    task: TaskUnit,
    now: datetime,
) -> bool:
    # Only evaluation shards call the configured model endpoint. Pipeline
    # bookkeeping must not consume the provider's inference budget.
    if task.task_type != TaskType.EVALUATION_SHARD.value:
        return True
    request_count, estimated_tokens, estimated_input_tokens, estimated_output_tokens = _task_budget(task)
    if all(
        limit is None
        for limit in (
            endpoint.requests_per_second,
            endpoint.requests_per_minute,
            endpoint.tokens_per_minute,
            endpoint.input_tokens_per_minute,
            endpoint.output_tokens_per_minute,
        )
    ):
        return True

    second_started_at = int(now.timestamp())
    window_started_at = int(now.timestamp() // 60) * 60
    second_usage = session.scalar(
        select(EndpointSecondRateWindow).where(
            EndpointSecondRateWindow.model_endpoint_id == endpoint.id,
            EndpointSecondRateWindow.window_started_at == second_started_at,
        )
    )
    usage = session.scalar(
        select(EndpointRateWindow).where(
            EndpointRateWindow.model_endpoint_id == endpoint.id,
            EndpointRateWindow.window_started_at == window_started_at,
        )
    )
    existing_requests = usage.request_count if usage else 0
    existing_tokens = usage.estimated_token_count if usage else 0
    existing_input_tokens = usage.estimated_input_token_count if usage else 0
    existing_output_tokens = usage.estimated_output_token_count if usage else 0
    if endpoint.requests_per_second is not None and (second_usage.request_count if second_usage else 0) + request_count > endpoint.requests_per_second:
        return False
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
    if endpoint.input_tokens_per_minute is not None and existing_input_tokens + estimated_input_tokens > endpoint.input_tokens_per_minute:
        return False
    if endpoint.output_tokens_per_minute is not None and existing_output_tokens + estimated_output_tokens > endpoint.output_tokens_per_minute:
        return False
    if second_usage is None:
        session.add(
            EndpointSecondRateWindow(
                model_endpoint_id=endpoint.id,
                window_started_at=second_started_at,
                request_count=request_count,
            )
        )
    else:
        second_usage.request_count += request_count
    if usage is None:
        usage = EndpointRateWindow(
            model_endpoint_id=endpoint.id,
            window_started_at=window_started_at,
            request_count=request_count,
            estimated_token_count=estimated_tokens,
            estimated_input_token_count=estimated_input_tokens,
            estimated_output_token_count=estimated_output_tokens,
        )
        session.add(usage)
    else:
        usage.request_count += request_count
        usage.estimated_token_count += estimated_tokens
        usage.estimated_input_token_count += estimated_input_tokens
        usage.estimated_output_token_count += estimated_output_tokens
    return True


def _task_budget(task: TaskUnit) -> tuple[int, int, int, int]:
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
        per_sample = payload.get("sample_token_estimates")
        if isinstance(per_sample, dict):
            selected = [sample_id for sample_id in sample_ids if isinstance(sample_id, str)]
            selected_estimates = [per_sample.get(sample_id) for sample_id in selected]
            if all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in selected_estimates):
                estimated_tokens = sum(int(value) for value in selected_estimates)
            else:
                estimated_tokens = max(1, estimated_tokens // max(1, request_count)) * fallback_requests
        else:
            estimated_tokens = max(1, estimated_tokens // max(1, request_count)) * fallback_requests
        request_count = fallback_requests
    estimated_output_tokens = min(estimated_tokens, request_count * 32)
    estimated_input_tokens = max(0, estimated_tokens - estimated_output_tokens)
    return request_count, estimated_tokens, estimated_input_tokens, estimated_output_tokens
