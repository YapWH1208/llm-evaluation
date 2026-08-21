from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect

from app.core.config import Settings
from app.db.database import Database
from app.db.migrations import LATEST_SCHEMA_VERSION, MIGRATIONS
from app.db.models import Base
from app.db.mongo import MongoDocumentStore
from tests.test_mongo_document_store import FakeClient


EXPECTED_SQLITE_TABLES = frozenset(
    {
        "schema_versions",
        "schema_migrations",
        "model_endpoints",
        "model_capabilities",
        "endpoint_rate_windows",
        "endpoint_second_rate_windows",
        "media_assets",
        "benchmark_definitions",
        "prompt_packages",
        "dataset_versions",
        "evaluation_suites",
        "reports",
        "report_shares",
        "report_share_password_attempts",
        "human_reviews",
        "judge_assessments",
        "evaluation_runs",
        "task_units",
        "sample_attempts",
        "aggregate_metrics",
    }
)

EXPECTED_MONGO_COLLECTIONS = frozenset(
    {
        "schema_versions",
        "schema_migrations",
        "model_endpoints",
        "model_capabilities",
        "endpoint_rate_windows",
        "endpoint_second_rate_windows",
        "media_assets",
        "benchmark_definitions",
        "prompt_packages",
        "dataset_versions",
        "evaluation_suites",
        "evaluation_runs",
        "task_units",
        "queue_admission_locks",
        "sample_attempts",
        "aggregate_metrics",
        "reports",
        "report_shares",
        "report_share_password_attempts",
        "human_reviews",
        "judge_assessments",
    }
)


def test_sqlite_schema_contract_is_stable(tmp_path: Path) -> None:
    database = Database(Settings.local_development(database_url=f"sqlite:///{tmp_path / 'contract.db'}"))
    try:
        validation = database.initialize()
        assert validation.is_valid
        assert Database.CURRENT_SCHEMA_VERSION == LATEST_SCHEMA_VERSION
        assert [migration.version for migration in MIGRATIONS] == list(range(2, LATEST_SCHEMA_VERSION + 1))

        table_names = set(inspect(database.engine).get_table_names())
        assert table_names == EXPECTED_SQLITE_TABLES
        assert set(Base.metadata.tables) == EXPECTED_SQLITE_TABLES
        assert validation.current_version == LATEST_SCHEMA_VERSION
    finally:
        database.dispose()


def test_mongo_schema_contract_is_stable() -> None:
    client = FakeClient()
    store = MongoDocumentStore(
        Settings.local_development(database_url="mongodb://mongo.test/platform"),
        client=client,
    )
    try:
        validation = store.initialize()
        assert validation.is_valid
        assert MongoDocumentStore.CURRENT_SCHEMA_VERSION == LATEST_SCHEMA_VERSION
        assert set(store.database.list_collection_names()) == EXPECTED_MONGO_COLLECTIONS
        assert validation.current_version == LATEST_SCHEMA_VERSION
        assert [migration.version for migration in MIGRATIONS] == list(range(2, LATEST_SCHEMA_VERSION + 1))
    finally:
        store.close()
