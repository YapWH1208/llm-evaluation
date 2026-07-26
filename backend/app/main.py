from __future__ import annotations

from contextlib import asynccontextmanager
import hashlib
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
from app.api.judge_assessments import router as judge_assessments_router
from app.core.config import Settings
from app.db.database import Database
from app.services.connection_tester import ConnectionTester, OpenAIChatCompletionsConnectionTester
from app.services.capability_detector import CapabilityDetector, OpenAIChatCompletionsCapabilityDetector
from app.services.model_executor import ModelExecutor, OpenAIChatCompletionsExecutor
from app.services.benchmark_registry import ensure_builtin_benchmark_definitions
from app.db.models import AuditEvent, User, UserRole
from sqlalchemy import select


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
        if settings.database_init_mode.lower().strip() == "auto_migrate":
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
        allow_headers=["Content-Type", "Authorization"],
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
    app.include_router(judge_assessments_router)

    @app.middleware("http")
    async def require_configured_api_token(request, call_next):
        if not request.url.path.startswith("/api/v1"):
            return await call_next(request)
        role, actor_id = _authenticate_request(request, settings, database)
        if role is None:
            return JSONResponse({"detail": "Valid bearer token required."}, status_code=401)
        if role not in _allowed_roles(request.url.path, request.method):
            return JSONResponse({"detail": "Your role is not permitted to perform this action."}, status_code=403)
        request.state.actor_id = actor_id
        request.state.actor_role = role
        response = await call_next(request)
        if request.method in {"POST", "PATCH", "PUT", "DELETE"} and response.status_code < 400:
            _record_mutation_audit(database, request, response.status_code)
        return response
    app.include_router(evaluation_runs_router)

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            database=settings.database_kind,
            schema_version=Database.CURRENT_SCHEMA_VERSION,
        )

    return app


app = create_app()


def _authenticate_request(request, settings: Settings, database: Database) -> tuple[str | None, str | None]:
    if not settings.admin_token:
        return UserRole.ADMIN.value, None
    supplied = request.headers.get("Authorization", "")
    expected = f"Bearer {settings.admin_token}"
    if hmac.compare_digest(supplied, expected):
        return UserRole.ADMIN.value, None
    if not supplied.startswith("Bearer "):
        return None, None
    token_hash = hashlib.sha256(supplied.removeprefix("Bearer ").encode()).hexdigest()
    with database.get_session() as session:
        user = session.scalar(select(User).where(User.api_token_hash == token_hash, User.status == "active"))
        if user is None:
            return None, None
        return user.role, user.id


def _allowed_roles(path: str, method: str) -> set[str]:
    all_roles = {role.value for role in UserRole}
    evaluator_roles = {UserRole.ADMIN.value, UserRole.EVALUATOR.value}
    reviewer_roles = evaluator_roles | {UserRole.REVIEWER.value}
    if path.startswith("/api/v1/users") or path.startswith("/api/v1/audit-events"):
        return {UserRole.ADMIN.value}
    if path.startswith("/api/v1/workers"):
        return {UserRole.ADMIN.value}
    if path.startswith("/api/v1/benchmarks") and method != "GET":
        return {UserRole.ADMIN.value}
    if path.startswith("/api/v1/reviews") and method != "GET":
        return reviewer_roles
    if method in {"POST", "PATCH", "PUT", "DELETE"}:
        return evaluator_roles
    return all_roles


def _record_mutation_audit(database: Database, request, status_code: int) -> None:
    """Record metadata only; request bodies can contain API keys and sample content."""

    parts = [part for part in request.url.path.split("/") if part]
    entity_type = parts[2] if len(parts) > 2 else "system"
    entity_id = parts[3] if len(parts) > 3 else None
    try:
        with database.get_session() as session:
            session.add(
                AuditEvent(
                    actor_id=getattr(request.state, "actor_id", None),
                    action=f"api.{request.method.lower()}",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    details={"path": request.url.path, "status_code": status_code},
                )
            )
            session.commit()
    except Exception:
        # Audit availability must not turn a successful external model action into an unknown outcome.
        return
