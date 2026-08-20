from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.database import Database
from app.db.models import MediaAsset
from app.db.mongo import MongoDocumentStore


class SqliteAssetRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def find_by_digest(self, sha256: str) -> MediaAsset | None:
        with self._database.get_session() as session:
            asset = session.scalar(select(MediaAsset).where(MediaAsset.sha256 == sha256))
            return _detached(asset) if asset is not None else None

    def create_asset(self, values: dict[str, Any]) -> MediaAsset:
        with self._database.get_session() as session:
            asset = MediaAsset(**values)
            session.add(asset)
            session.commit()
            session.refresh(asset)
            return _detached(asset)

    def get_asset(self, asset_id: str) -> MediaAsset | None:
        with self._database.get_session() as session:
            asset = session.get(MediaAsset, asset_id)
            return _detached(asset) if asset is not None else None


class MongoAssetRepository:
    def __init__(self, store: MongoDocumentStore) -> None:
        self._store = store

    def find_by_digest(self, sha256: str) -> dict[str, Any] | None:
        assets = self._store.list_documents("media_assets", query={"sha256": sha256})
        return assets[0] if assets else None

    def create_asset(self, values: dict[str, Any]) -> dict[str, Any]:
        return self._store.insert_document("media_assets", values)

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        return self._store.get_document("media_assets", asset_id)


def _detached(asset: MediaAsset) -> MediaAsset:
    values = {column.name: getattr(asset, column.name) for column in MediaAsset.__table__.columns}
    return MediaAsset(**values)
