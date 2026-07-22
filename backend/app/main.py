from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.capabilities import router as capabilities_router
from app.api.evaluation_runs import router as evaluation_runs_router
from app.api.model_endpoints import router as model_endpoints_router
from app.api.prompt_packages import router as prompt_packages_router
from app.core.config import Settings
from app.db.database import Database
from app.services.connection_tester import ConnectionTester, OpenAIChatCompletionsConnectionTester
from app.services.model_executor import ModelExecutor, OpenAIChatCompletionsExecutor


class HealthResponse(BaseModel):
    status: str
    database: str
    schema_version: int


def create_app(
    settings: Settings | None = None,
    connection_tester: ConnectionTester | None = None,
    model_executor: ModelExecutor | None = None,
) -> FastAPI:
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )
    app.state.settings = settings
    app.state.connection_tester = connection_tester or OpenAIChatCompletionsConnectionTester()
    app.state.model_executor = model_executor or OpenAIChatCompletionsExecutor()
    app.include_router(model_endpoints_router)
    app.include_router(capabilities_router)
    app.include_router(prompt_packages_router)
    app.include_router(evaluation_runs_router)

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            database="sqlite" if settings.is_sqlite else "configured",
            schema_version=Database.INITIAL_SCHEMA_VERSION,
        )

    return app


app = create_app()
