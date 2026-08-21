from enum import StrEnum


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
