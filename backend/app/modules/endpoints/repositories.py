from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.database import Database
from app.db.models import ModelCapability, ModelEndpoint
from app.db.mongo import MongoDocumentStore


class SqliteEndpointRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, values: dict[str, Any]) -> ModelEndpoint:
        with self._database.get_session() as session:
            endpoint = ModelEndpoint(**values)
            session.add(endpoint)
            session.commit()
            session.refresh(endpoint)
            return endpoint

    def list(self) -> list[ModelEndpoint]:
        with self._database.get_session() as session:
            return list(session.scalars(select(ModelEndpoint).order_by(ModelEndpoint.created_at.desc())))

    def get(self, endpoint_id: str) -> ModelEndpoint | None:
        with self._database.get_session() as session:
            endpoint = session.get(ModelEndpoint, endpoint_id)
            if endpoint is None:
                return None
            values = {column.name: getattr(endpoint, column.name) for column in ModelEndpoint.__table__.columns}
            return ModelEndpoint(**values)

    def update(self, endpoint_id: str, values: dict[str, Any]) -> ModelEndpoint | None:
        with self._database.get_session() as session:
            endpoint = session.get(ModelEndpoint, endpoint_id)
            if endpoint is None:
                return None
            for field, value in values.items():
                setattr(endpoint, field, value)
            session.commit()
            session.refresh(endpoint)
            values = {column.name: getattr(endpoint, column.name) for column in ModelEndpoint.__table__.columns}
            return ModelEndpoint(**values)

    def delete(self, endpoint_id: str) -> bool:
        with self._database.get_session() as session:
            endpoint = session.get(ModelEndpoint, endpoint_id)
            if endpoint is None:
                return False
            session.delete(endpoint)
            session.commit()
            return True

    def list_capabilities(self, endpoint_id: str) -> list[ModelCapability]:
        with self._database.get_session() as session:
            return list(session.scalars(select(ModelCapability).where(ModelCapability.model_endpoint_id == endpoint_id).order_by(ModelCapability.capability_key)))

    def find_capability(self, endpoint_id: str, capability_key: str) -> ModelCapability | None:
        with self._database.get_session() as session:
            item = session.scalar(select(ModelCapability).where(ModelCapability.model_endpoint_id == endpoint_id, ModelCapability.capability_key == capability_key))
            if item is None:
                return None
            values = {column.name: getattr(item, column.name) for column in ModelCapability.__table__.columns}
            return ModelCapability(**values)

    def upsert_capability(self, endpoint_id: str, capability_key: str, values: dict[str, Any]) -> ModelCapability:
        with self._database.get_session() as session:
            item = session.scalar(select(ModelCapability).where(ModelCapability.model_endpoint_id == endpoint_id, ModelCapability.capability_key == capability_key))
            if item is None:
                item = ModelCapability(model_endpoint_id=endpoint_id, capability_key=capability_key)
                session.add(item)
            for field, value in values.items():
                setattr(item, field, value)
            session.commit()
            session.refresh(item)
            return item


class MongoEndpointRepository:
    def __init__(self, store: MongoDocumentStore) -> None:
        self._store = store

    def create(self, values: dict[str, Any]) -> dict[str, Any]:
        return self._store.insert_document("model_endpoints", values)

    def list(self) -> list[dict[str, Any]]:
        return self._store.list_documents("model_endpoints", sort=[("created_at", -1)])

    def get(self, endpoint_id: str) -> dict[str, Any] | None:
        return self._store.get_document("model_endpoints", endpoint_id)

    def update(self, endpoint_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        return self._store.update_document("model_endpoints", endpoint_id, values)

    def delete(self, endpoint_id: str) -> bool:
        return self._store.delete_document("model_endpoints", endpoint_id)

    def list_capabilities(self, endpoint_id: str) -> list[dict[str, Any]]:
        return self._store.list_documents("model_capabilities", query={"model_endpoint_id": endpoint_id}, sort=[("capability_key", 1)])

    def find_capability(self, endpoint_id: str, capability_key: str) -> dict[str, Any] | None:
        items = self._store.list_documents("model_capabilities", query={"model_endpoint_id": endpoint_id, "capability_key": capability_key})
        return items[0] if items else None

    def upsert_capability(self, endpoint_id: str, capability_key: str, values: dict[str, Any]) -> dict[str, Any]:
        existing = self.find_capability(endpoint_id, capability_key)
        if existing is not None:
            updated = self._store.update_document("model_capabilities", str(existing["id"]), values)
            assert updated is not None
            return updated
        return self._store.insert_document("model_capabilities", {"model_endpoint_id": endpoint_id, "capability_key": capability_key, **values})
