from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from app.api.model_endpoints import router as model_endpoints_router
from app.core.config import Settings
from app.db.database import Database


class HealthResponse(BaseModel):
    status: str
    database: str
    schema_version: int


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_environment()
    database = Database(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database.initialize()
        app.state.database = database
        yield
        database.dispose()

    app = FastAPI(
        title=settings.application_name,
        version=settings.application_version,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.include_router(model_endpoints_router)

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            database="sqlite" if settings.is_sqlite else "configured",
            schema_version=Database.INITIAL_SCHEMA_VERSION,
        )

    return app


app = create_app()
