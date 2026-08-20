from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import DatasetVersion, EvaluationRun
from app.db.mongo import MongoDocumentStore
from app.db.database import Database


_DATASET_FIELDS = (
    "dataset_id", "version", "revision", "source_url", "credential_binding_id", "checksum",
    "size_bytes", "local_path", "prepared_path", "license_text", "license_accepted_at",
    "input_field", "reference_field", "capabilities", "languages", "evaluation_type",
    "status", "error_message", "created_at",
)


def _copy_dataset_model(item: DatasetVersion) -> dict[str, Any]:
    return {"id": item.id, **{field: getattr(item, field) for field in _DATASET_FIELDS}}


class SqliteDatasetRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get(self, dataset_version_id: str) -> dict[str, Any] | None:
        with self.database.get_session() as session:
            item = session.get(DatasetVersion, dataset_version_id)
            return _copy_dataset_model(item) if item is not None else None

    def list(self) -> list[dict[str, Any]]:
        with self.database.get_session() as session:
            return [_copy_dataset_model(item) for item in session.scalars(select(DatasetVersion).order_by(DatasetVersion.created_at.desc()))]

    def create(self, values: Mapping[str, Any]) -> dict[str, Any]:
        item = DatasetVersion(**{key: values[key] for key in _DATASET_FIELDS if key in values and key != "created_at"})
        with self.database.get_session() as session:
            session.add(item)
            try:
                session.commit()
            except IntegrityError as error:
                session.rollback()
                raise ValueError("Dataset revision already exists") from error
            session.refresh(item)
            return _copy_dataset_model(item)

    def update(self, dataset_version_id: str, values: Mapping[str, Any]) -> dict[str, Any] | None:
        with self.database.get_session() as session:
            item = session.get(DatasetVersion, dataset_version_id)
            if item is None:
                return None
            for key, value in values.items():
                if key in _DATASET_FIELDS and key != "created_at":
                    setattr(item, key, value)
            try:
                session.commit()
            except IntegrityError as error:
                session.rollback()
                raise ValueError("Dataset revision already exists") from error
            session.refresh(item)
            return _copy_dataset_model(item)

    def delete(self, dataset_version_id: str) -> dict[str, Any] | None:
        with self.database.get_session() as session:
            item = session.get(DatasetVersion, dataset_version_id)
            if item is None:
                return None
            result = _copy_dataset_model(item)
            session.delete(item)
            session.commit()
            return result

    def is_referenced(self, dataset_version_id: str) -> bool:
        with self.database.get_session() as session:
            for run in session.scalars(select(EvaluationRun)):
                snapshot = run.configuration_snapshot if isinstance(run.configuration_snapshot, dict) else {}
                datasets = snapshot.get("datasets") if isinstance(snapshot, dict) else None
                if isinstance(datasets, list) and any(
                    isinstance(descriptor, dict) and descriptor.get("dataset_version_id") == dataset_version_id
                    for descriptor in datasets
                ):
                    return True
            return False


class SqliteSessionDatasetRepository:
    """Repository view for an already-open worker transaction."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, dataset_version_id: str) -> dict[str, Any] | None:
        item = self.session.get(DatasetVersion, dataset_version_id)
        return _copy_dataset_model(item) if item is not None else None

    def list(self) -> list[dict[str, Any]]:
        return [_copy_dataset_model(item) for item in self.session.scalars(select(DatasetVersion).order_by(DatasetVersion.created_at.desc()))]

    def create(self, values: Mapping[str, Any]) -> dict[str, Any]:
        item = DatasetVersion(**{key: values[key] for key in _DATASET_FIELDS if key in values and key != "created_at"})
        self.session.add(item)
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise ValueError("Dataset revision already exists") from error
        self.session.refresh(item)
        return _copy_dataset_model(item)

    def update(self, dataset_version_id: str, values: Mapping[str, Any]) -> dict[str, Any] | None:
        item = self.session.get(DatasetVersion, dataset_version_id)
        if item is None:
            return None
        for key, value in values.items():
            if key in _DATASET_FIELDS and key != "created_at":
                setattr(item, key, value)
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise ValueError("Dataset revision already exists") from error
        self.session.refresh(item)
        return _copy_dataset_model(item)

    def delete(self, dataset_version_id: str) -> dict[str, Any] | None:
        item = self.session.get(DatasetVersion, dataset_version_id)
        if item is None:
            return None
        result = _copy_dataset_model(item)
        self.session.delete(item)
        self.session.commit()
        return result

    def is_referenced(self, dataset_version_id: str) -> bool:
        for run in self.session.scalars(select(EvaluationRun)):
            snapshot = run.configuration_snapshot if isinstance(run.configuration_snapshot, dict) else {}
            datasets = snapshot.get("datasets") if isinstance(snapshot, dict) else None
            if isinstance(datasets, list) and any(
                isinstance(descriptor, dict) and descriptor.get("dataset_version_id") == dataset_version_id
                for descriptor in datasets
            ):
                return True
        return False


class MongoDatasetRepository:
    def __init__(self, store: MongoDocumentStore) -> None:
        self.store = store

    def get(self, dataset_version_id: str) -> dict[str, Any] | None:
        return self.store.get_document("dataset_versions", dataset_version_id)

    def list(self) -> list[dict[str, Any]]:
        return self.store.list_documents("dataset_versions", sort=[("created_at", -1)])

    def create(self, values: Mapping[str, Any]) -> dict[str, Any]:
        existing = self.store.list_documents("dataset_versions", query={
            "dataset_id": values.get("dataset_id"), "version": values.get("version"), "revision": values.get("revision"),
        })
        if existing:
            raise ValueError("Dataset revision already exists")
        document = {key: value for key, value in values.items() if key in _DATASET_FIELDS and key != "created_at"}
        document.setdefault("id", str(uuid4()))
        document.setdefault("created_at", datetime.now())
        return self.store.insert_document("dataset_versions", document)

    def update(self, dataset_version_id: str, values: Mapping[str, Any]) -> dict[str, Any] | None:
        current = self.get(dataset_version_id)
        if current is None:
            return None
        identity = {
            field: values[field] if field in values else current.get(field)
            for field in ("dataset_id", "version", "revision")
        }
        existing = self.store.list_documents("dataset_versions", query=identity)
        if any(str(item.get("id")) != dataset_version_id for item in existing):
            raise ValueError("Dataset revision already exists")
        try:
            return self.store.update_document("dataset_versions", dataset_version_id, dict(values))
        except Exception as error:
            if type(error).__name__ != "DuplicateKeyError":
                raise
            raise ValueError("Dataset revision already exists") from error

    def delete(self, dataset_version_id: str) -> dict[str, Any] | None:
        current = self.get(dataset_version_id)
        if current is None:
            return None
        self.store.delete_document("dataset_versions", dataset_version_id)
        return current

    def is_referenced(self, dataset_version_id: str) -> bool:
        for run in self.store.list_documents("evaluation_runs"):
            snapshot = run.get("configuration_snapshot") if isinstance(run.get("configuration_snapshot"), dict) else {}
            datasets = snapshot.get("datasets") if isinstance(snapshot, dict) else None
            if isinstance(datasets, list) and any(
                isinstance(descriptor, dict) and descriptor.get("dataset_version_id") == dataset_version_id
                for descriptor in datasets
            ):
                return True
        return False
