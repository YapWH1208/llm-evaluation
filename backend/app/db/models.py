from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
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
    api_key_mask: Mapped[str] = mapped_column(String(16), nullable=False)
    default_request_body: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    max_concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    requests_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    NOT_DOWNLOADED="not_downloaded"; DOWNLOADING="downloading"; VERIFYING="verifying"; PREPARING="preparing"; READY="ready"; LICENSE_REQUIRED="license_required"; FAILED="failed"

class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version", "revision", name="uq_dataset_revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    dataset_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[str] = mapped_column(String(128), nullable=False, default="default")
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    license_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=DatasetStatus.NOT_DOWNLOADED.value)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    generator_version: Mapped[str] = mapped_column(String(64), nullable=False, default="1.0.0")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RunStatus(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(StrEnum):
    PENDING = "pending"
    LEASED = "leased"
    RUNNING = "running"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SampleAttemptStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
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
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TaskStatus.PENDING.value)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    leased_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
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
