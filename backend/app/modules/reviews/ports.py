from __future__ import annotations

from typing import Any, Protocol


class ReviewRepository(Protocol):
    def sample_attempt_exists(self, sample_attempt_id: str) -> bool: ...

    def create(self, values: dict[str, Any]) -> Any: ...

    def list_for_sample(self, sample_attempt_id: str) -> list[Any]: ...
