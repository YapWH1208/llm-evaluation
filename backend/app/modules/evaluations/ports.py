from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from app.core.config import Settings
from app.core.secrets import SecretCipher
from app.infrastructure.providers.contracts import ModelExecutor


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

    def get_prompt_package(self, prompt_package_id: str) -> dict[str, Any] | None: ...

    def get_benchmark_definition(self, benchmark_id: str, benchmark_version: str) -> dict[str, Any] | None: ...

    def list_capabilities(self, endpoint_id: str) -> list[dict[str, Any]]: ...

    def get_dataset(self, dataset_version_id: str) -> dict[str, Any] | None: ...

    def get_media_asset(self, asset_id: str) -> dict[str, Any] | None: ...

    def find_dataset(self, *, dataset_id: str, version: str | None, revision: str | None) -> dict[str, Any] | None: ...

    def create_dataset(self, values: dict[str, Any]) -> dict[str, Any]: ...

    def get_suite(self, suite_id: str) -> dict[str, Any] | None: ...

    def list_suites(self) -> list[dict[str, Any]]: ...

    def create_suite(self, values: dict[str, Any]) -> dict[str, Any]: ...

    def update_suite(self, suite_id: str, values: dict[str, Any]) -> dict[str, Any] | None: ...

    def create_run_graph(
        self,
        run_values: dict[str, Any],
        tasks: list[dict[str, Any]],
        attempts: list[dict[str, Any]],
    ) -> dict[str, Any]: ...

    def append_run_graph(
        self,
        run_id: str,
        tasks: list[dict[str, Any]],
        attempts: list[dict[str, Any]],
    ) -> None: ...

    def find_previous_completed_run(self, run: dict[str, Any]) -> dict[str, Any] | None: ...

    def delete_run(self, run_id: str) -> list[str]:
        """Delete persisted run evidence and return report artifact paths."""
        ...


class ExecutionRepository(Protocol):
    """Atomic persistence operations required by queue and execution behavior."""

    def get_run(self, run_id: str) -> dict[str, Any] | None: ...

    def get_endpoint(self, endpoint_id: str) -> dict[str, Any] | None: ...

    def get_task(self, task_id: str) -> dict[str, Any] | None: ...

    def list_tasks(self, run_id: str) -> list[dict[str, Any]]: ...

    def list_attempts(self, run_id: str) -> list[dict[str, Any]]: ...

    def claim_task(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
        run_id: str | None = None,
        system_max_concurrency: int | None = None,
        worker_max_concurrency: int | None = None,
    ) -> dict[str, Any] | None: ...

    def heartbeat_task(self, task_id: str, lease_token: str, lease_seconds: int) -> dict[str, Any] | None: ...

    def reclaim_expired_leases(self) -> int: ...

    def update_run_if(
        self,
        run_id: str,
        *,
        statuses: Iterable[str],
        values: dict[str, Any],
    ) -> dict[str, Any] | None: ...

    def update_task_for_lease(
        self,
        task_id: str,
        lease_token: str,
        values: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None: ...

    def create_task(self, values: dict[str, Any]) -> dict[str, Any]: ...

    def create_attempt(self, values: dict[str, Any]) -> dict[str, Any]: ...

    def begin_attempt(self, attempt_id: str, lease_token: str, values: dict[str, Any]) -> dict[str, Any] | None: ...

    def complete_attempt(
        self,
        attempt_id: str,
        lease_token: str,
        values: dict[str, Any],
    ) -> dict[str, Any] | None: ...

    def update_attempt(self, attempt_id: str, values: dict[str, Any]) -> dict[str, Any] | None: ...

    def prepare_dataset(self, descriptor: dict[str, Any], data_root: str, settings: Settings | None) -> None: ...

    def aggregate(self, run_id: str) -> int: ...

    def generate_report(
        self,
        run_id: str,
        format: str,
        data_root: str,
        *,
        report_type: str,
    ) -> dict[str, Any]: ...

    def assess_judge(
        self,
        *,
        sample_attempt_id: str,
        judge_endpoint_id: str,
        rubric: dict[str, Any],
        system_message: str,
        cipher: SecretCipher,
        model_executor: ModelExecutor,
        endpoint_override: dict[str, Any],
    ) -> dict[str, Any]: ...

    def query_tasks(
        self,
        *,
        run_id: str | None,
        status: str | None,
        offset: int,
        limit: int,
    ) -> list[dict[str, Any]]: ...

    def update_task_priority(self, task_id: str, priority: int) -> dict[str, Any] | None: ...

    def queue_snapshot(self) -> dict[str, Any]: ...
