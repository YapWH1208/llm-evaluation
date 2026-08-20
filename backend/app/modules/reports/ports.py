from __future__ import annotations

from typing import Any, Protocol


class AssetRepository(Protocol):
    def find_by_digest(self, sha256: str) -> Any | None: ...

    def create_asset(self, values: dict[str, Any]) -> Any: ...

    def get_asset(self, asset_id: str) -> Any | None: ...
