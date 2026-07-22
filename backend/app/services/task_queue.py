from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.db.models import TaskStatus, TaskUnit

def reclaim_expired_leases(session: Session) -> int:
    now=datetime.now(timezone.utc)
    tasks=list(session.scalars(select(TaskUnit).where(TaskUnit.status.in_([TaskStatus.LEASED.value,TaskStatus.RUNNING.value]),TaskUnit.lease_expires_at < now)))
    for task in tasks:
        task.status=TaskStatus.PENDING.value;task.leased_by=None;task.lease_token=None;task.lease_expires_at=None
    if tasks:session.commit()
    return len(tasks)

def claim_task(session: Session, worker_id: str, lease_seconds: int=60) -> TaskUnit|None:
    reclaim_expired_leases(session);now=datetime.now(timezone.utc)
    task=session.scalar(select(TaskUnit).where(TaskUnit.status.in_([TaskStatus.PENDING.value,TaskStatus.RETRY_SCHEDULED.value]),or_(TaskUnit.next_retry_at.is_(None),TaskUnit.next_retry_at<=now)).order_by(TaskUnit.priority.desc(),TaskUnit.created_at).limit(1))
    if task is None:return None
    task.status=TaskStatus.LEASED.value;task.leased_by=worker_id;task.lease_token=str(uuid4());task.lease_expires_at=now+timedelta(seconds=lease_seconds);task.heartbeat_at=now;session.commit();session.refresh(task);return task

def heartbeat_task(session:Session, task_id:str, lease_token:str, lease_seconds:int=60)->TaskUnit|None:
    task=session.get(TaskUnit,task_id)
    if task is None or task.lease_token!=lease_token:return None
    now=datetime.now(timezone.utc);task.heartbeat_at=now;task.lease_expires_at=now+timedelta(seconds=lease_seconds);session.commit();session.refresh(task);return task
