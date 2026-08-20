from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class DatasetRepository(Protocol):
    """Persistence primitives used by the dataset application service."""

    def get(self, dataset_version_id: str) -> dict[str, Any] | None: ...

    def list(self) -> list[dict[str, Any]]: ...

    def find(
        self,
        *,
        dataset_id: str,
        version: str | None = None,
        revision: str | None = None,
    ) -> dict[str, Any] | None: ...

    def create(self, values: Mapping[str, Any]) -> dict[str, Any]: ...

    def update(self, dataset_version_id: str, values: Mapping[str, Any]) -> dict[str, Any] | None: ...

    def delete(self, dataset_version_id: str) -> dict[str, Any] | None: ...

    def is_referenced(self, dataset_version_id: str) -> bool: ...
