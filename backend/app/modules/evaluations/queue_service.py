from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.db.models import TaskStatus
from app.modules.evaluations.ports import ExecutionRepository


class QueueService:
    """Store-neutral worker leasing and task administration."""

    def __init__(self, repository: ExecutionRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    def claim(self, worker_id: str, lease_seconds: int, *, run_id: str | None = None) -> dict[str, Any] | None:
        return self._repository.claim_task(
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            run_id=run_id,
            system_max_concurrency=self._settings.system_max_concurrency,
            worker_max_concurrency=self._settings.worker_max_concurrency,
        )

    def heartbeat(self, task_id: str, lease_token: str, lease_seconds: int) -> dict[str, Any]:
        task = self._repository.heartbeat_task(task_id, lease_token, lease_seconds)
        if task is None:
            raise ConflictError("Task lease is no longer valid")
        return task

    def reclaim_expired(self) -> int:
        return self._repository.reclaim_expired_leases()

    def list_tasks(
        self,
        *,
        run_id: str | None,
        status: str | None,
        offset: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        return self._repository.query_tasks(
            run_id=run_id,
            status=status,
            offset=max(0, offset),
            limit=min(max(1, limit), 1000),
        )

    def update_priority(self, task_id: str, priority: int) -> dict[str, Any]:
        task = self._repository.get_task(task_id)
        if task is None:
            raise NotFoundError("Task not found", context={"task_id": task_id})
        if task.get("status") not in {TaskStatus.PENDING.value, TaskStatus.RETRY_SCHEDULED.value}:
            raise ConflictError("Only queued tasks can have their priority adjusted")
        updated = self._repository.update_task_priority(task_id, priority)
        if updated is None:
            raise NotFoundError("Task not found", context={"task_id": task_id})
        return updated

    def snapshot(self) -> dict[str, Any]:
        return self._repository.queue_snapshot()
