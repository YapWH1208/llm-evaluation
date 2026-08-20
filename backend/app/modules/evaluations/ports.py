from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol


class EvaluationRepository(Protocol):
    """Persistence primitives used by evaluation application behavior."""

    def get_run(self, run_id: str) -> dict[str, Any] | None: ...

    def list_runs(self, *, include_archived: bool = False) -> list[dict[str, Any]]: ...

    def update_run(self, run_id: str, values: dict[str, Any]) -> dict[str, Any] | None: ...

    def update_tasks(
        self,
        run_id: str,
        *,
        statuses: Iterable[str],
        values: dict[str, Any],
        increment_lease_version: bool = False,
    ) -> int: ...

    def update_attempts(
        self,
        run_id: str,
        *,
        statuses: Iterable[str],
        values: dict[str, Any],
    ) -> int: ...

    def list_tasks(self, run_id: str) -> list[dict[str, Any]]: ...

    def list_attempts(self, run_id: str) -> list[dict[str, Any]]: ...

    def list_reviews(self, attempt_ids: Iterable[str]) -> list[dict[str, Any]]: ...

    def list_judge_assessments(self, attempt_ids: Iterable[str]) -> list[dict[str, Any]]: ...

    def get_endpoint(self, endpoint_id: str) -> dict[str, Any] | None: ...

    def find_previous_completed_run(self, run: dict[str, Any]) -> dict[str, Any] | None: ...

    def delete_run(self, run_id: str) -> list[str]:
        """Delete persisted run evidence and return report artifact paths."""
        ...
