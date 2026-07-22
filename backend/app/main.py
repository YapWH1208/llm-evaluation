from __future__ import annotations

from contextlib import asynccontextmanager
import hmac

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.capabilities import router as capabilities_router
from app.api.datasets import router as datasets_router
from app.api.evaluation_runs import router as evaluation_runs_router
from app.api.model_endpoints import router as model_endpoints_router
from app.api.prompt_packages import router as prompt_packages_router
from app.api.workers import router as workers_router
from app.api.reports import router as reports_router
from app.api.comparisons import router as comparisons_router
from app.api.reviews import router as reviews_router
from app.api.admin import router as admin_router
from app.api.dashboard import router as dashboard_router
from app.api.assets import router as assets_router
from app.api.benchmarks import router as benchmarks_router
from app.core.config import Settings
from app.db.database import Database
from app.services.connection_tester import ConnectionTester, OpenAIChatCompletionsConnectionTester
from app.services.capability_detector import CapabilityDetector, OpenAIChatCompletionsCapabilityDetector
from app.services.model_executor import ModelExecutor, OpenAIChatCompletionsExecutor
from app.services.benchmark_registry import ensure_builtin_benchmark_definitions


class HealthResponse(BaseModel):
    status: str
    database: str
    schema_version: int


def create_app(
    settings: Settings | None = None,
    connection_tester: ConnectionTester | None = None,
    model_executor: ModelExecutor | None = None,
    capability_detector: CapabilityDetector | None = None,
) -> FastAPI:
    settings = settings or Settings.from_environment()
    database = Database(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database.initialize()
        with database.get_session() as session:
            ensure_builtin_benchmark_definitions(session)
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
    app.state.capability_detector = capability_detector or OpenAIChatCompletionsCapabilityDetector()
    app.include_router(model_endpoints_router)
    app.include_router(capabilities_router)
    app.include_router(datasets_router)
    app.include_router(prompt_packages_router)
    app.include_router(workers_router)
    app.include_router(reports_router)
    app.include_router(comparisons_router)
    app.include_router(reviews_router)
    app.include_router(admin_router)
    app.include_router(dashboard_router)
    app.include_router(assets_router)
    app.include_router(benchmarks_router)

    @app.middleware("http")
    async def require_configured_api_token(request, call_next):
        if settings.admin_token and request.url.path.startswith("/api/v1"):
            supplied = request.headers.get("Authorization", "")
            expected = f"Bearer {settings.admin_token}"
            if not hmac.compare_digest(supplied, expected):
                return JSONResponse({"detail": "Valid bearer token required."}, status_code=401)
        return await call_next(request)
    app.include_router(evaluation_runs_router)

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            database="sqlite" if settings.is_sqlite else "configured",
            schema_version=Database.CURRENT_SCHEMA_VERSION,
        )

    return app


app = create_app()
