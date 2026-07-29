from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from app.core.config import Settings
from app.db.migrations import LATEST_SCHEMA_VERSION
from app.db import SchemaVersion
from app.main import create_app


def test_health_initializes_the_configured_sqlite_database(tmp_path: Path) -> None:
    database_path = tmp_path / "platform.db"
    app = create_app(Settings.local_development(database_url=f"sqlite:///{database_path}"))

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["database"] == "sqlite"
        assert body["schema_version"] == LATEST_SCHEMA_VERSION
        assert body["database_connected"] is True
        assert body["disk"]["available_bytes"] > 0
        assert body["queue"] == {"pending": 0, "active": 0}
        assert response.headers["X-Request-ID"]

        tables = inspect(app.state.database.engine).get_table_names()
        assert "schema_versions" in tables

        with app.state.database.get_session() as session:
            assert session.scalar(select(SchemaVersion.version).order_by(SchemaVersion.version.desc())) == LATEST_SCHEMA_VERSION
