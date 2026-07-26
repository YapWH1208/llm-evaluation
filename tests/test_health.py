from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from app.core.config import Settings
from app.db import SchemaVersion
from app.main import create_app


def test_health_initializes_the_configured_sqlite_database(tmp_path: Path) -> None:
    database_path = tmp_path / "platform.db"
    app = create_app(Settings(database_url=f"sqlite:///{database_path}"))

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "database": "sqlite",
            "schema_version": 7,
        }

        tables = inspect(app.state.database.engine).get_table_names()
        assert "schema_versions" in tables

        with app.state.database.get_session() as session:
            assert session.scalar(select(SchemaVersion.version).order_by(SchemaVersion.version.desc())) == 7
