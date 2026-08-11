from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all relational persistence models."""


class SchemaVersion(Base):
    """Records the latest schema managed by the application.

    Dedicated migration files will advance this record in later increments.
    """

    __tablename__ = "schema_versions"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SchemaMigration(Base):
    """Auditable record of each successful forward-only schema migration."""

    __tablename__ = "schema_migrations"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    migration_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class EndpointStatus(StrEnum):
    UNVERIFIED = "unverified"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ModelEndpoint(Base):
    """A remote model connection whose API key is encrypted at rest."""

    __tablename__ = "model_endpoints"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    protocol_profile: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="openai_chat_completions",
    )
    encrypted_api_key: Mapped[str] = mapped_column(String, nullable=False)
    api_key_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    api_key_mask: Mapped[str] = mapped_column(String(16), nullable=False)
    custom_headers: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    default_request_body: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    max_concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    api_key_max_concurrency: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requests_per_second: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requests_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_cost_per_million: Mapped[float | None] = mapped_column(nullable=True)
    output_cost_per_million: Mapped[float | None] = mapped_column(nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=EndpointStatus.UNVERIFIED.value,
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_connection_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CapabilityDeclaration(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class CapabilityDetection(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    NOT_TESTED = "not_tested"
    UNSUPPORTED_BY_ADAPTER = "unsupported_by_adapter"


class ModelCapability(Base):
    """Keeps user declarations separate from platform detection evidence."""

    __tablename__ = "model_capabilities"
    __table_args__ = (UniqueConstraint("model_endpoint_id", "capability_key", name="uq_model_capability"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    model_endpoint_id: Mapped[str] = mapped_column(ForeignKey("model_endpoints.id", ondelete="CASCADE"), nullable=False, index=True)
    capability_key: Mapped[str] = mapped_column(String(128), nullable=False)
    user_declared_status: Mapped[str] = mapped_column(String(32), nullable=False, default=CapabilityDeclaration.UNKNOWN.value)
    auto_detection_status: Mapped[str] = mapped_column(String(32), nullable=False, default=CapabilityDetection.NOT_TESTED.value)
    effective_status: Mapped[str] = mapped_column(String(64), nullable=False, default="unverified")
    detection_evidence: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    detector_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class EndpointRateWindow(Base):
    """Durable per-endpoint fixed-window request and token admission accounting."""

    __tablename__ = "endpoint_rate_windows"
    __table_args__ = (UniqueConstraint("model_endpoint_id", "window_started_at", name="uq_endpoint_rate_window"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    model_endpoint_id: Mapped[str] = mapped_column(
        ForeignKey("model_endpoints.id", ondelete="CASCADE"), nullable=False, index=True
    )
    window_started_at: Mapped[int] = mapped_column(Integer, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_input_token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_output_token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class EndpointSecondRateWindow(Base):
    """Durable one-second request admission accounting for endpoint RPS limits."""

    __tablename__ = "endpoint_second_rate_windows"
    __table_args__ = (UniqueConstraint("model_endpoint_id", "window_started_at", name="uq_endpoint_second_rate_window"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    model_endpoint_id: Mapped[str] = mapped_column(ForeignKey("model_endpoints.id", ondelete="CASCADE"), nullable=False, index=True)
    window_started_at: Mapped[int] = mapped_column(Integer, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MediaAsset(Base):
    """A validated, content-addressed local media artifact referenced by sample content."""

    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    storage_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BenchmarkDefinition(Base):
    """Versioned benchmark manifest, independent from a particular worker implementation."""

    __tablename__ = "benchmark_definitions"
    __table_args__ = (UniqueConstraint("benchmark_id", "version", name="uq_benchmark_definition_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    benchmark_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="registered")
    manifest: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PromptPackage(Base):
    """Versioned prompt, parser, and scoring configuration."""

    __tablename__ = "prompt_packages"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_prompt_package_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_type: Mapped[str] = mapped_column(String(64), nullable=False, default="user_custom")
    system_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_template: Mapped[str] = mapped_column(Text, nullable=False)
    few_shot_examples: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    output_format: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    response_parser: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    scoring_rule: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    change_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class DatasetStatus(StrEnum):
    NOT_DOWNLOADED="not_downloaded"; WAITING="waiting"; DOWNLOADING="downloading"; VERIFYING="verifying"; PREPARING="preparing"; READY="ready"; UPDATE_AVAILABLE="update_available"; LICENSE_REQUIRED="license_required"; CREDENTIAL_REQUIRED="credential_required"; CORRUPTED="corrupted"; FAILED="failed"; REMOVING="removing"

class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version", "revision", name="uq_dataset_revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    dataset_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[str] = mapped_column(String(128), nullable=False, default="main")
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    credential_env_var: Mapped[str | None] = mapped_column(String(128), nullable=True)
    credential_binding_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    prepared_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    license_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_field: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_field: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=DatasetStatus.NOT_DOWNLOADED.value)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EvaluationSuite(Base):
    """A versioned collection of benchmark selections and run defaults."""

    __tablename__ = "evaluation_suites"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_evaluation_suite_name_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    benchmark_list: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    default_prompt_overrides: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    default_request_body: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    weight_configuration: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    version: Mapped[str] = mapped_column(String(64), nullable=False, default="1")
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generator_version: Mapped[str] = mapped_column(String(64), nullable=False, default="1.0.0")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ReportShare(Base):
    __tablename__ = "report_shares"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    allow_download: Mapped[bool] = mapped_column(nullable=False, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ReportSharePasswordAttempt(Base):
    """One durable, expiring password-failure window per share and client partition."""

    __tablename__ = "report_share_password_attempts"
    __table_args__ = (
        UniqueConstraint("share_id", "client_key", name="uq_report_share_password_attempt_client"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    share_id: Mapped[str] = mapped_column(
        ForeignKey("report_shares.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_key: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

class HumanReview(Base):
    __tablename__="human_reviews"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid4()))
    sample_attempt_id: Mapped[str]=mapped_column(ForeignKey("sample_attempts.id",ondelete="CASCADE"),nullable=False,index=True)
    reviewer_id: Mapped[str]=mapped_column(String(128),nullable=False)
    rubric: Mapped[dict[str,object]|None]=mapped_column(JSON,nullable=True)
    score: Mapped[float|None]=mapped_column(nullable=True)
    labels: Mapped[list[object]]=mapped_column(JSON,nullable=False,default=list)
    notes: Mapped[str|None]=mapped_column(Text,nullable=True)
    review_stage: Mapped[str]=mapped_column(String(32),nullable=False,default="primary")
    adjudicates_review_ids: Mapped[list[object]]=mapped_column(JSON,nullable=False,default=list)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now())


class JudgeAssessment(Base):
    """LLM-as-judge assessment retained separately from deterministic and human evidence."""

    __tablename__ = "judge_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    sample_attempt_id: Mapped[str] = mapped_column(
        ForeignKey("sample_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    judge_endpoint_id: Mapped[str] = mapped_column(
        ForeignKey("model_endpoints.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    comparison_sample_attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey("sample_attempts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    rubric: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    answer_order: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    swap_test_group_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    selected_answer: Mapped[str | None] = mapped_column(String(16), nullable=True)
    score: Mapped[float | None] = mapped_column(nullable=True)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

class UserRole(StrEnum):
    ADMIN="admin"; EVALUATOR="evaluator"; REVIEWER="reviewer"; VIEWER="viewer"

class User(Base):
    __tablename__="users"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid4()))
    email: Mapped[str]=mapped_column(String(320),nullable=False,unique=True,index=True)
    display_name: Mapped[str]=mapped_column(String(200),nullable=False)
    role: Mapped[str]=mapped_column(String(32),nullable=False,default=UserRole.VIEWER.value)
    status: Mapped[str]=mapped_column(String(32),nullable=False,default="active")
    max_concurrency: Mapped[int | None]=mapped_column(Integer,nullable=True)
    api_token_hash: Mapped[str|None]=mapped_column(String(64),nullable=True,unique=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now())

class AuditEvent(Base):
    __tablename__="audit_events"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid4()))
    actor_id: Mapped[str|None]=mapped_column(String(36),nullable=True,index=True)
    action: Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    entity_type: Mapped[str]=mapped_column(String(64),nullable=False)
    entity_id: Mapped[str|None]=mapped_column(String(36),nullable=True,index=True)
    details: Mapped[dict[str,object]|None]=mapped_column(JSON,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now())


class RunStatus(StrEnum):
    DRAFT = "draft"
    VALIDATING = "validating"
    WAITING_FOR_DATASET = "waiting_for_dataset"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SCORING = "scoring"
    AGGREGATING = "aggregating"
    GENERATING_REPORT = "generating_report"


class TaskStatus(StrEnum):
    PENDING = "pending"
    LEASED = "leased"
    RUNNING = "running"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(StrEnum):
    DATASET_PREPARATION = "dataset_preparation"
    BENCHMARK = "benchmark"
    EVALUATION_SHARD = "evaluation_shard"
    SCORING = "scoring"
    JUDGE = "judge"
    AGGREGATION = "aggregation"
    REPORT_GENERATION = "report_generation"
    CLEANUP = "cleanup"


class SampleAttemptStatus(StrEnum):
    PENDING = "pending"
    LEASED = "leased"
    RUNNING = "running"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class EvaluationRun(Base):
    """An immutable evaluation configuration and its execution state."""

    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    model_endpoint_id: Mapped[str] = mapped_column(
        ForeignKey("model_endpoints.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    prompt_package_id: Mapped[str | None] = mapped_column(
        ForeignKey("prompt_packages.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    suite_id: Mapped[str | None] = mapped_column(
        ForeignKey("evaluation_suites.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    max_concurrency: Mapped[int | None] = mapped_column(Integer, nullable=True)
    benchmark_id: Mapped[str] = mapped_column(String(128), nullable=False)
    benchmark_version: Mapped[str] = mapped_column(String(64), nullable=False)
    configuration_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=RunStatus.QUEUED.value)
    total_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class TaskUnit(Base):
    """A durable work item, designed for lease-based worker execution."""

    __tablename__ = "task_units"
    __table_args__ = (
        Index("ix_task_units_claimable", "status", "next_retry_at", "priority"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_task_id: Mapped[str | None] = mapped_column(
        ForeignKey("task_units.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TaskStatus.PENDING.value)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    leased_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SampleAttempt(Base):
    """An individual sample attempt, kept even when a later retry succeeds."""

    __tablename__ = "sample_attempts"
    __table_args__ = (
        UniqueConstraint("run_id", "sample_id", "attempt_number", name="uq_sample_attempt"),
        Index("ix_sample_attempts_run_status", "run_id", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("task_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sample_id: Mapped[str] = mapped_column(String(255), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    input_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    reference_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    request_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_prediction: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SampleAttemptStatus.PENDING.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AggregateMetric(Base):
    """A versioned aggregate retained independently from per-sample evidence."""

    __tablename__ = "aggregate_metrics"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "metric_name",
            "aggregation_version",
            name="uq_aggregate_metric_run_name_version",
        ),
        Index("ix_aggregate_metrics_run_metric", "run_id", "metric_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    benchmark_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    model_endpoint_id: Mapped[str] = mapped_column(
        ForeignKey("model_endpoints.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_value: Mapped[float | None] = mapped_column(nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_interval: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    aggregation_version: Mapped[str] = mapped_column(String(64), nullable=False, default="1.0.0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
