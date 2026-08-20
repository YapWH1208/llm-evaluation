from __future__ import annotations

from app.db.models import RunStatus


class RunLifecycle:
    """Single policy table for user-visible evaluation-run transitions."""

    terminal = frozenset({
        RunStatus.COMPLETED.value,
        RunStatus.COMPLETED_WITH_ERRORS.value,
        RunStatus.FAILED.value,
        RunStatus.CANCELLED.value,
    })

    @classmethod
    def can_pause(cls, status: str) -> bool:
        return status in {RunStatus.QUEUED.value, RunStatus.RUNNING.value}

    @classmethod
    def can_resume(cls, status: str) -> bool:
        return status == RunStatus.PAUSED.value

    @classmethod
    def can_cancel(cls, status: str) -> bool:
        return status not in {RunStatus.COMPLETED.value, RunStatus.COMPLETED_WITH_ERRORS.value, RunStatus.CANCELLED.value}

    @classmethod
    def can_archive(cls, status: str) -> bool:
        return status in cls.terminal

    @classmethod
    def can_change_scheduling(cls, status: str) -> bool:
        return status not in cls.terminal

    @classmethod
    def can_delete(cls, archived_at: object | None) -> bool:
        return archived_at is not None
