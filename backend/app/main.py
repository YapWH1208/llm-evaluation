from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.modules.endpoints.capabilities_api import router as capabilities_router
from app.modules.datasets.api import router as datasets_router
from app.modules.evaluations.api import router as evaluation_runs_router
from app.modules.endpoints.api import router as model_endpoints_router
from app.modules.benchmarks.prompts_api import router as prompt_packages_router
from app.modules.evaluations.queue_api import router as workers_router
from app.modules.reports.api import public_router as shared_reports_router
from app.modules.reports.api import router as reports_router
from app.modules.analytics.comparisons_api import router as comparisons_router
from app.modules.reviews.api import router as reviews_router
from app.modules.analytics.dashboard_api import router as dashboard_router
from app.modules.reports.assets_api import router as assets_router
from app.modules.benchmarks.api import router as benchmarks_router
from app.modules.reviews.judges_api import router as judge_assessments_router
from app.modules.evaluations.tasks_api import router as tasks_router
from app.modules.analytics.api import router as analytics_router
from app.api.errors import register_application_error_handlers
from app.modules.evaluations.suites_api import router as suites_router
from app.modules.analytics.leaderboard_api import router as leaderboard_router
from app.core.config import Settings
from app.db.database import Database
from app.db.mongo import MongoDocumentStore
from app.infrastructure.providers.capabilities import CapabilityDetector, ProviderCapabilityDetector
from app.infrastructure.providers.connection import ProviderConnectionTester
from app.infrastructure.providers.contracts import ModelExecutor
from app.infrastructure.providers.executor import ProviderExecutor
from app.modules.endpoints.repositories import MongoEndpointRepository, SqliteEndpointRepository
from app.modules.endpoints.service import EndpointService
from app.modules.datasets.repositories import MongoDatasetRepository, SqliteDatasetRepository
from app.modules.datasets.service import DatasetService
from app.modules.benchmarks.registry import ensure_builtin_benchmark_definitions
from sqlalchemy import select, text


request_logger = logging.getLogger("lle.request")


class HealthResponse(BaseModel):
    status: str
    database: str
    schema_version: int
    database_connected: bool
    disk: dict[str, int]
    queue: dict[str, int]


def create_app(
    settings: Settings | None = None,
    connection_tester: ProviderConnectionTester | None = None,
    model_executor: ModelExecutor | None = None,
    capability_detector: CapabilityDetector | None = None,
    document_store: MongoDocumentStore | None = None,
) -> FastAPI:
    settings = settings or Settings.from_environment()
    database = Database(settings) if settings.database_kind != "mongodb" else None
    document_store = (
        document_store or MongoDocumentStore(settings)
        if settings.database_kind == "mongodb"
        else None
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if document_store is not None:
            document_store.initialize()
            _ensure_mongo_builtin_benchmarks(document_store)
        else:
            assert database is not None
            database.initialize()
        if document_store is None and settings.database_init_mode.lower().strip() == "auto_migrate":
            assert database is not None
            with database.get_session() as session:
                ensure_builtin_benchmark_definitions(session)
        app.state.database = database
        app.state.document_store = document_store
        yield
        if document_store is not None:
            document_store.close()
        elif database is not None:
            database.dispose()

    app = FastAPI(
        title=settings.application_name,
        version=settings.application_version,
        lifespan=lifespan,
    )
    register_application_error_handlers(app)
    app.state.settings = settings
    app.state.endpoint_service = EndpointService(
        MongoEndpointRepository(document_store) if document_store is not None else SqliteEndpointRepository(database)  # type: ignore[arg-type]
    )
    app.state.dataset_service = DatasetService(
        MongoDatasetRepository(document_store) if document_store is not None else SqliteDatasetRepository(database)  # type: ignore[arg-type]
    )
    app.state.connection_tester = connection_tester or ProviderConnectionTester(max_response_bytes=settings.provider_response_max_bytes)
    app.state.model_executor = model_executor or ProviderExecutor(max_response_bytes=settings.provider_response_max_bytes)
    app.state.capability_detector = capability_detector or ProviderCapabilityDetector(max_response_bytes=settings.provider_response_max_bytes)
    app.include_router(model_endpoints_router)
    app.include_router(capabilities_router)
    app.include_router(datasets_router)
    app.include_router(prompt_packages_router)
    app.include_router(workers_router)
    app.include_router(reports_router)
    app.include_router(shared_reports_router)
    app.include_router(comparisons_router)
    app.include_router(reviews_router)
    app.include_router(dashboard_router)
    app.include_router(assets_router)
    app.include_router(benchmarks_router)
    app.include_router(judge_assessments_router)
    app.include_router(tasks_router)
    app.include_router(analytics_router)
    app.include_router(suites_router)
    app.include_router(leaderboard_router)

    @app.middleware("http")
    async def request_context(request, call_next):
        request_id = request.headers.get("X-Request-ID", "").strip()
        request.state.request_id = request_id[:128] if request_id else str(uuid4())
        started_at = datetime.now(timezone.utc)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        request_logger.info(json.dumps({"event": "http_request", "request_id": request.state.request_id, "method": request.method, "path": request.url.path, "status_code": response.status_code, "duration_ms": round((datetime.now(timezone.utc) - started_at).total_seconds() * 1000, 3)}, separators=(",", ":")))
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Report-Password"],
    )
    app.include_router(evaluation_runs_router)

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse | JSONResponse:
        database_connected = True
        queue = {"pending": 0, "active": 0}
        try:
            if document_store is not None:
                queue = {
                    "pending": document_store.count_documents("task_units", {"status": {"$in": ["pending", "retry_scheduled"]}}),
                    "active": document_store.count_documents("task_units", {"status": {"$in": ["leased", "running"]}}),
                }
            else:
                assert database is not None
                from app.db.models import TaskUnit

                with database.get_session() as session:
                    session.execute(text("SELECT 1"))
                    from sqlalchemy import func

                    queue = {
                        "pending": session.scalar(select(func.count()).select_from(TaskUnit).where(TaskUnit.status.in_(["pending", "retry_scheduled"]))) or 0,
                        "active": session.scalar(select(func.count()).select_from(TaskUnit).where(TaskUnit.status.in_(["leased", "running"]))) or 0,
                    }
        except Exception:
            database_connected = False
        disk = shutil.disk_usage(Path(settings.data_root).resolve())
        payload = HealthResponse(
            status="ok" if database_connected else "degraded",
            database=settings.database_kind,
            schema_version=Database.CURRENT_SCHEMA_VERSION,
            database_connected=database_connected,
            disk={"available_bytes": disk.free, "total_bytes": disk.total},
            queue=queue,
        )
        if not database_connected:
            return JSONResponse(status_code=503, content=payload.model_dump())
        return payload

    return app


app = create_app()


def _ensure_mongo_builtin_benchmarks(document_store: MongoDocumentStore) -> None:
    """Register the same built-in benchmark manifests in document storage."""

    from app.benchmarks import BUILTIN_PLUGINS

    for plugin in BUILTIN_PLUGINS:
        manifest = plugin.manifest
        existing = document_store.list_documents(
            "benchmark_definitions",
            query={"benchmark_id": manifest["benchmark_id"], "version": manifest["version"]},
        )
        if existing:
            continue
        document_store.insert_document(
            "benchmark_definitions",
            {
                "benchmark_id": manifest["benchmark_id"],
                "version": manifest["version"],
                "display_name": manifest["display_name"],
                "status": "available",
                "manifest": manifest,
                "source": "builtin",
                "created_at": datetime.now(timezone.utc),
            },
        )
    from app.benchmarks import register_manifest_plugin

    for definition in document_store.list_documents("benchmark_definitions"):
        manifest = definition.get("manifest")
        if isinstance(manifest, dict):
            register_manifest_plugin(manifest)
