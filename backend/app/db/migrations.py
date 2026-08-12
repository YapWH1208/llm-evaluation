from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import Connection, inspect, text


@dataclass(frozen=True, slots=True)
class Migration:
    """A forward-only relational schema upgrade."""

    version: int
    migration_id: str
    description: str
    upgrade: Callable[[Connection], None]


def _add_column_if_missing(
    connection: Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    table_names = set(inspect(connection).get_table_names())
    if table_name not in table_names:
        return

    existing_columns = {column["name"] for column in inspect(connection).get_columns(table_name)}
    if column_name not in existing_columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}"))


def _create_index_if_missing(
    connection: Connection,
    table_name: str,
    index_name: str,
    columns: tuple[str, ...],
) -> None:
    table_names = set(inspect(connection).get_table_names())
    if table_name not in table_names:
        return
    existing_indexes = {index.get("name") for index in inspect(connection).get_indexes(table_name)}
    if index_name not in existing_indexes:
        joined_columns = ", ".join(columns)
        connection.execute(text(f"CREATE INDEX {index_name} ON {table_name} ({joined_columns})"))


def _upgrade_v2_prompt_package_reference(connection: Connection) -> None:
    """Preserve existing runs while adding the prompt package snapshot reference."""

    _add_column_if_missing(
        connection,
        "evaluation_runs",
        "prompt_package_id",
        "prompt_package_id VARCHAR(36)",
    )


def _upgrade_v3_endpoint_rate_windows(_connection: Connection) -> None:
    """The ORM creates the new durable admission-accounting table."""


def _upgrade_v4_media_assets(_connection: Connection) -> None:
    """The ORM creates the content-addressed local media asset table."""


def _upgrade_v5_benchmark_definitions(_connection: Connection) -> None:
    """The ORM creates the versioned benchmark manifest table."""


def _upgrade_v6_user_api_tokens(connection: Connection) -> None:
    _add_column_if_missing(connection, "users", "api_token_hash", "api_token_hash VARCHAR(64)")


def _upgrade_v7_judge_assessments(_connection: Connection) -> None:
    """The ORM creates durable LLM-as-judge assessment records."""


def _upgrade_v8_usage_and_cost_evidence(connection: Connection) -> None:
    _add_column_if_missing(connection, "model_endpoints", "input_cost_per_million", "input_cost_per_million FLOAT")
    _add_column_if_missing(connection, "model_endpoints", "output_cost_per_million", "output_cost_per_million FLOAT")
    _add_column_if_missing(connection, "model_endpoints", "currency", "currency VARCHAR(8) NOT NULL DEFAULT 'USD'")
    _add_column_if_missing(connection, "sample_attempts", "latency_ms", "latency_ms FLOAT")
    _add_column_if_missing(connection, "sample_attempts", "input_tokens", "input_tokens INTEGER")
    _add_column_if_missing(connection, "sample_attempts", "output_tokens", "output_tokens INTEGER")
    _add_column_if_missing(connection, "sample_attempts", "estimated_cost", "estimated_cost FLOAT")


def _upgrade_v9_report_shares(_connection: Connection) -> None:
    """The ORM creates expiring report-share records."""


def _upgrade_v10_endpoint_metadata(connection: Connection) -> None:
    _add_column_if_missing(connection, "model_endpoints", "custom_headers", "custom_headers JSON NOT NULL DEFAULT '{}'")
    _add_column_if_missing(connection, "model_endpoints", "tags", "tags JSON NOT NULL DEFAULT '[]'")
    _add_column_if_missing(connection, "model_endpoints", "notes", "notes TEXT")


def _upgrade_v11_evaluation_suites(_connection: Connection) -> None:
    """The ORM creates versioned evaluation suite storage."""


def _upgrade_v12_run_suite_reference(connection: Connection) -> None:
    _add_column_if_missing(connection, "evaluation_runs", "suite_id", "suite_id VARCHAR(36)")


def _upgrade_v13_extended_rate_limits(connection: Connection) -> None:
    _add_column_if_missing(connection, "model_endpoints", "requests_per_second", "requests_per_second INTEGER")
    _add_column_if_missing(connection, "model_endpoints", "input_tokens_per_minute", "input_tokens_per_minute INTEGER")
    _add_column_if_missing(connection, "model_endpoints", "output_tokens_per_minute", "output_tokens_per_minute INTEGER")
    _add_column_if_missing(connection, "endpoint_rate_windows", "estimated_input_token_count", "estimated_input_token_count INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(connection, "endpoint_rate_windows", "estimated_output_token_count", "estimated_output_token_count INTEGER NOT NULL DEFAULT 0")


def _upgrade_v14_hierarchical_concurrency_limits(connection: Connection) -> None:
    _add_column_if_missing(connection, "model_endpoints", "api_key_fingerprint", "api_key_fingerprint VARCHAR(64)")
    _add_column_if_missing(connection, "model_endpoints", "api_key_max_concurrency", "api_key_max_concurrency INTEGER")
    _add_column_if_missing(connection, "users", "max_concurrency", "max_concurrency INTEGER")
    _add_column_if_missing(connection, "evaluation_runs", "created_by", "created_by VARCHAR(36)")
    _add_column_if_missing(connection, "evaluation_runs", "max_concurrency", "max_concurrency INTEGER")


def _upgrade_v15_dataset_source_credentials(connection: Connection) -> None:
    _add_column_if_missing(connection, "dataset_versions", "credential_env_var", "credential_env_var VARCHAR(128)")


def _upgrade_v16_run_archiving(connection: Connection) -> None:
    _add_column_if_missing(connection, "evaluation_runs", "archived_at", "archived_at DATETIME")


def _upgrade_v17_structured_human_review(connection: Connection) -> None:
    _add_column_if_missing(connection, "human_reviews", "review_stage", "review_stage VARCHAR(32) NOT NULL DEFAULT 'primary'")
    _add_column_if_missing(connection, "human_reviews", "adjudicates_review_ids", "adjudicates_review_ids JSON NOT NULL DEFAULT '[]'")


def _upgrade_v18_task_hierarchy_and_aggregate_metrics(connection: Connection) -> None:
    _add_column_if_missing(connection, "task_units", "parent_task_id", "parent_task_id VARCHAR(36)")


def _upgrade_v19_pairwise_judge_evidence(connection: Connection) -> None:
    _add_column_if_missing(connection, "judge_assessments", "comparison_sample_attempt_id", "comparison_sample_attempt_id VARCHAR(36)")
    _add_column_if_missing(connection, "judge_assessments", "answer_order", "answer_order JSON NOT NULL DEFAULT '[]'")
    _add_column_if_missing(connection, "judge_assessments", "swap_test_group_id", "swap_test_group_id VARCHAR(36)")
    _add_column_if_missing(connection, "judge_assessments", "selected_answer", "selected_answer VARCHAR(16)")


def _upgrade_v20_dataset_uploads(connection: Connection) -> None:
    _add_column_if_missing(connection, "dataset_versions", "size_bytes", "size_bytes BIGINT")


def _upgrade_v21_dataset_preparation(connection: Connection) -> None:
    _add_column_if_missing(connection, "dataset_versions", "prepared_path", "prepared_path VARCHAR(2048)")


def _upgrade_v22_remediation_persistence_contracts(connection: Connection) -> None:
    """Add non-destructive fields required by the security and fencing remediation."""

    _add_column_if_missing(connection, "task_units", "lease_version", "lease_version INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(connection, "dataset_versions", "credential_binding_id", "credential_binding_id VARCHAR(128)")
    _add_column_if_missing(connection, "reports", "artifact_sha256", "artifact_sha256 VARCHAR(64)")
    _create_index_if_missing(connection, "evaluation_runs", "ix_evaluation_runs_archived_at", ("archived_at",))
    _create_index_if_missing(connection, "evaluation_runs", "ix_evaluation_runs_created_by", ("created_by",))
    _create_index_if_missing(connection, "evaluation_runs", "ix_evaluation_runs_model_endpoint_id", ("model_endpoint_id",))
    _create_index_if_missing(connection, "evaluation_runs", "ix_evaluation_runs_prompt_package_id", ("prompt_package_id",))
    _create_index_if_missing(connection, "evaluation_runs", "ix_evaluation_runs_suite_id", ("suite_id",))
    if connection.dialect.name == "postgresql":
        connection.execute(text("ALTER TABLE report_shares ALTER COLUMN password_hash TYPE VARCHAR(512)"))


def _upgrade_v23_report_share_password_limits(_connection: Connection) -> None:
    """The ORM creates the additive durable report-share password limiter table."""


def _upgrade_v24_dataset_field_defaults(connection: Connection) -> None:
    _add_column_if_missing(connection, "dataset_versions", "input_field", "input_field VARCHAR(255)")
    _add_column_if_missing(connection, "dataset_versions", "reference_field", "reference_field VARCHAR(255)")


def _upgrade_v25_evaluation_experience_persistence(connection: Connection) -> None:
    """Add compatibility-safe fields for names, dataset metadata, and metric evidence."""

    _add_column_if_missing(connection, "evaluation_runs", "display_name", "display_name VARCHAR(500)")
    _add_column_if_missing(
        connection,
        "dataset_versions",
        "capabilities",
        "capabilities JSON NOT NULL DEFAULT '[]'",
    )
    _add_column_if_missing(
        connection,
        "dataset_versions",
        "languages",
        "languages JSON NOT NULL DEFAULT '[]'",
    )
    _add_column_if_missing(
        connection,
        "dataset_versions",
        "evaluation_type",
        "evaluation_type VARCHAR(32) NOT NULL DEFAULT 'custom'",
    )
    _add_column_if_missing(connection, "sample_attempts", "metric_evidence", "metric_evidence JSON")
    _add_column_if_missing(
        connection,
        "aggregate_metrics",
        "availability_reason",
        "availability_reason VARCHAR(500)",
    )


def _upgrade_v26_judge_usage_and_cost(connection: Connection) -> None:
    _add_column_if_missing(connection, "judge_assessments", "input_tokens", "input_tokens INTEGER")
    _add_column_if_missing(connection, "judge_assessments", "output_tokens", "output_tokens INTEGER")
    _add_column_if_missing(connection, "judge_assessments", "estimated_cost", "estimated_cost FLOAT")


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=2,
        migration_id="20260722_add_prompt_package_reference",
        description="Add prompt package references and register post-v1 platform tables.",
        upgrade=_upgrade_v2_prompt_package_reference,
    ),
    Migration(
        version=3,
        migration_id="20260722_add_endpoint_rate_windows",
        description="Add durable per-endpoint request and token admission accounting.",
        upgrade=_upgrade_v3_endpoint_rate_windows,
    ),
    Migration(
        version=4,
        migration_id="20260722_add_media_assets",
        description="Add validated content-addressed media assets for multimodal samples.",
        upgrade=_upgrade_v4_media_assets,
    ),
    Migration(
        version=5,
        migration_id="20260722_add_benchmark_definitions",
        description="Add versioned benchmark manifests and plugin registration records.",
        upgrade=_upgrade_v5_benchmark_definitions,
    ),
    Migration(
        version=6,
        migration_id="20260722_add_user_api_tokens",
        description="Add hashed per-user bearer tokens for role-enforced API access.",
        upgrade=_upgrade_v6_user_api_tokens,
    ),
    Migration(
        version=7,
        migration_id="20260726_add_judge_assessments",
        description="Add durable LLM-as-judge assessment evidence for sample attempts.",
        upgrade=_upgrade_v7_judge_assessments,
    ),
    Migration(
        version=8,
        migration_id="20260726_add_usage_and_cost_evidence",
        description="Add provider usage, latency, and estimated cost evidence to sample attempts.",
        upgrade=_upgrade_v8_usage_and_cost_evidence,
    ),
    Migration(
        version=9,
        migration_id="20260726_add_report_shares",
        description="Add expiring, revocable, password-protected report share records.",
        upgrade=_upgrade_v9_report_shares,
    ),
    Migration(
        version=10,
        migration_id="20260726_add_endpoint_metadata",
        description="Add safe custom headers, tags, and notes to model endpoints.",
        upgrade=_upgrade_v10_endpoint_metadata,
    ),
    Migration(
        version=11,
        migration_id="20260726_add_evaluation_suites",
        description="Add versioned evaluation-suite definitions.",
        upgrade=_upgrade_v11_evaluation_suites,
    ),
    Migration(
        version=12,
        migration_id="20260726_add_run_suite_reference",
        description="Link evaluation runs to immutable suite selections.",
        upgrade=_upgrade_v12_run_suite_reference,
    ),
    Migration(
        version=13,
        migration_id="20260726_add_extended_rate_limits",
        description="Add durable RPS and directional token-per-minute admission accounting.",
        upgrade=_upgrade_v13_extended_rate_limits,
    ),
    Migration(
        version=14,
        migration_id="20260726_add_hierarchical_concurrency_limits",
        description="Add per-user, API-key, benchmark, and run concurrency admission controls.",
        upgrade=_upgrade_v14_hierarchical_concurrency_limits,
    ),
    Migration(
        version=15,
        migration_id="20260726_add_dataset_source_credentials",
        description="Add environment-referenced dataset download credentials.",
        upgrade=_upgrade_v15_dataset_source_credentials,
    ),
    Migration(
        version=16,
        migration_id="20260726_add_run_archiving",
        description="Add a durable archive marker before terminal evaluation runs may be deleted.",
        upgrade=_upgrade_v16_run_archiving,
    ),
    Migration(
        version=17,
        migration_id="20260726_add_structured_human_review",
        description="Add independent review stages and adjudication evidence for human review workflows.",
        upgrade=_upgrade_v17_structured_human_review,
    ),
    Migration(
        version=18,
        migration_id="20260728_add_task_hierarchy_and_aggregate_metrics",
        description="Add parent task lineage and durable versioned aggregate metric records.",
        upgrade=_upgrade_v18_task_hierarchy_and_aggregate_metrics,
    ),
    Migration(
        version=19,
        migration_id="20260728_add_pairwise_judge_evidence",
        description="Add blinded pairwise judge answer order, swap-test grouping, and selected-answer evidence.",
        upgrade=_upgrade_v19_pairwise_judge_evidence,
    ),
    Migration(
        version=20,
        migration_id="20260728_add_dataset_upload_size",
        description="Add durable size evidence for uploaded and downloaded dataset revisions.",
        upgrade=_upgrade_v20_dataset_uploads,
    ),
    Migration(
        version=21,
        migration_id="20260728_add_dataset_preparation_index",
        description="Record atomically prepared dataset sample-index artifacts.",
        upgrade=_upgrade_v21_dataset_preparation,
    ),
    Migration(
        version=22,
        migration_id="20260729_add_remediation_persistence_contracts",
        description="Add lease fencing, safe dataset binding, and immutable report metadata fields.",
        upgrade=_upgrade_v22_remediation_persistence_contracts,
    ),
    Migration(
        version=23,
        migration_id="20260730_add_report_share_password_limits",
        description="Add durable, expiring per-client failed-password windows for public report shares.",
        upgrade=_upgrade_v23_report_share_password_limits,
    ),
    Migration(
        version=24,
        migration_id="20260807_add_dataset_field_defaults",
        description="Add optional input and reference field defaults to dataset versions.",
        upgrade=_upgrade_v24_dataset_field_defaults,
    ),
    Migration(
        version=25,
        migration_id="20260811_add_evaluation_experience_persistence",
        description="Add run names, dataset metadata, and named-metric evidence fields.",
        upgrade=_upgrade_v25_evaluation_experience_persistence,
    ),
    Migration(
        version=26,
        migration_id="20260812_add_judge_usage_and_cost",
        description="Add provider token usage and estimated cost evidence to judge assessments.",
        upgrade=_upgrade_v26_judge_usage_and_cost,
    ),
)

LATEST_SCHEMA_VERSION = MIGRATIONS[-1].version
