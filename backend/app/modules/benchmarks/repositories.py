from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.db.database import Database
from app.db.models import BenchmarkDefinition, DatasetVersion, EvaluationRun, EvaluationSuite, PromptPackage
from app.db.mongo import MongoDocumentStore


class SqliteBenchmarkRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def list_definitions(self) -> list[BenchmarkDefinition]:
        with self._database.get_session() as session:
            return list(session.scalars(select(BenchmarkDefinition).order_by(BenchmarkDefinition.created_at.desc())))

    def get_definition(self, definition_id: str) -> BenchmarkDefinition | None:
        return self._get_detached(BenchmarkDefinition, definition_id)

    def find_definition(self, benchmark_id: str, version: str) -> BenchmarkDefinition | None:
        with self._database.get_session() as session:
            item = session.scalar(
                select(BenchmarkDefinition).where(
                    BenchmarkDefinition.benchmark_id == benchmark_id, BenchmarkDefinition.version == version
                )
            )
            return _detached(item) if item is not None else None

    def create_definitions(self, values: list[dict[str, Any]]) -> list[BenchmarkDefinition] | None:
        with self._database.get_session() as session:
            items = [BenchmarkDefinition(**item) for item in values]
            session.add_all(items)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return None
            for item in items:
                session.refresh(item)
            return [_detached(item) for item in items]

    def update_definition(
        self, definition_id: str, values: dict[str, Any], *, require_registered: bool
    ) -> BenchmarkDefinition | None:
        with self._database.get_session() as session:
            query = update(BenchmarkDefinition).where(BenchmarkDefinition.id == definition_id)
            if require_registered:
                query = query.where(BenchmarkDefinition.status == "registered")
            result = session.execute(query.values(**values))
            if result.rowcount != 1:
                session.rollback()
                return None
            session.commit()
            item = session.get(BenchmarkDefinition, definition_id)
            assert item is not None
            return _detached(item)

    def find_dataset(self, dataset_id: str, version: str | None) -> DatasetVersion | None:
        with self._database.get_session() as session:
            query = select(DatasetVersion).where(DatasetVersion.dataset_id == dataset_id)
            if version is not None:
                query = query.where(DatasetVersion.version == version)
            item = session.scalar(query.order_by(DatasetVersion.created_at.desc()))
            return _detached(item) if item is not None else None

    def create_prompt_package(self, values: dict[str, Any]) -> PromptPackage | None:
        with self._database.get_session() as session:
            item = PromptPackage(**values)
            session.add(item)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return None
            session.refresh(item)
            return _detached(item)

    def list_prompt_packages(self) -> list[PromptPackage]:
        with self._database.get_session() as session:
            return list(session.scalars(select(PromptPackage).order_by(PromptPackage.created_at.desc())))

    def get_prompt_package(self, prompt_package_id: str) -> PromptPackage | None:
        return self._get_detached(PromptPackage, prompt_package_id)

    def find_prompt_package(self, name: str, version: str) -> PromptPackage | None:
        with self._database.get_session() as session:
            item = session.scalar(
                select(PromptPackage).where(PromptPackage.name == name, PromptPackage.version == version)
            )
            return _detached(item) if item is not None else None

    def update_prompt_package(self, prompt_package_id: str, values: dict[str, Any]) -> PromptPackage | None:
        with self._database.get_session() as session:
            item = session.get(PromptPackage, prompt_package_id)
            if item is None:
                return None
            for field, value in values.items():
                setattr(item, field, value)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return None
            session.refresh(item)
            return _detached(item)

    def delete_prompt_package(self, prompt_package_id: str) -> bool:
        with self._database.get_session() as session:
            item = session.get(PromptPackage, prompt_package_id)
            if item is None:
                return False
            session.delete(item)
            session.commit()
            return True

    def prompt_run_reference_exists(self, prompt_package_id: str) -> bool:
        with self._database.get_session() as session:
            return bool(
                session.scalar(
                    select(EvaluationRun.id).where(EvaluationRun.prompt_package_id == prompt_package_id).limit(1)
                )
            )

    def list_suites(self) -> list[EvaluationSuite]:
        with self._database.get_session() as session:
            return list(session.scalars(select(EvaluationSuite)))

    def _get_detached(self, model: Any, item_id: str) -> Any | None:
        with self._database.get_session() as session:
            item = session.get(model, item_id)
            return _detached(item) if item is not None else None


class MongoBenchmarkRepository:
    def __init__(self, store: MongoDocumentStore) -> None:
        self._store = store

    def list_definitions(self) -> list[dict[str, Any]]:
        return self._store.list_documents("benchmark_definitions", sort=[("created_at", -1)])

    def get_definition(self, definition_id: str) -> dict[str, Any] | None:
        return self._store.get_document("benchmark_definitions", definition_id)

    def find_definition(self, benchmark_id: str, version: str) -> dict[str, Any] | None:
        items = self._store.list_documents(
            "benchmark_definitions", query={"benchmark_id": benchmark_id, "version": version}
        )
        return items[0] if items else None

    def create_definitions(self, values: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        if any(self.find_definition(str(item["benchmark_id"]), str(item["version"])) for item in values):
            return None
        return [self._store.insert_document("benchmark_definitions", item) for item in values]

    def update_definition(
        self, definition_id: str, values: dict[str, Any], *, require_registered: bool
    ) -> dict[str, Any] | None:
        if require_registered:
            return self._store.update_document_if(
                "benchmark_definitions", definition_id, {"status": "registered"}, values
            )
        return self._store.update_document("benchmark_definitions", definition_id, values)

    def find_dataset(self, dataset_id: str, version: str | None) -> dict[str, Any] | None:
        query = {"dataset_id": dataset_id, **({"version": version} if version is not None else {})}
        items = self._store.list_documents("dataset_versions", query=query, sort=[("created_at", -1)])
        return items[0] if items else None

    def create_prompt_package(self, values: dict[str, Any]) -> dict[str, Any] | None:
        if self.find_prompt_package(str(values["name"]), str(values["version"])) is not None:
            return None
        return self._store.insert_document("prompt_packages", values)

    def list_prompt_packages(self) -> list[dict[str, Any]]:
        return self._store.list_documents("prompt_packages", sort=[("created_at", -1)])

    def get_prompt_package(self, prompt_package_id: str) -> dict[str, Any] | None:
        return self._store.get_document("prompt_packages", prompt_package_id)

    def find_prompt_package(self, name: str, version: str) -> dict[str, Any] | None:
        items = self._store.list_documents("prompt_packages", query={"name": name, "version": version})
        return items[0] if items else None

    def update_prompt_package(self, prompt_package_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        return self._store.update_document("prompt_packages", prompt_package_id, values)

    def delete_prompt_package(self, prompt_package_id: str) -> bool:
        return self._store.delete_document("prompt_packages", prompt_package_id)

    def prompt_run_reference_exists(self, prompt_package_id: str) -> bool:
        return bool(
            self._store.list_documents("evaluation_runs", query={"prompt_package_id": prompt_package_id}, limit=1)
        )

    def list_suites(self) -> list[dict[str, Any]]:
        return self._store.list_documents("evaluation_suites")


def _detached(item: Any) -> Any:
    values = {column.name: getattr(item, column.name) for column in item.__table__.columns}
    return type(item)(**values)
