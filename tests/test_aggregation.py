from pathlib import Path

from sqlalchemy import select

from app.core.config import Settings
from app.db.database import Database
from app.db.models import AggregateMetric, EvaluationRun, ModelEndpoint, RunStatus
from app.services.aggregation import AGGREGATION_VERSION, recompute_aggregate_metrics


def _endpoint() -> ModelEndpoint:
    return ModelEndpoint(
        display_name="test endpoint",
        base_url="https://example.test/v1",
        model_name="test-model",
        protocol_profile="openai_chat_completions",
        encrypted_api_key="not-used",
        api_key_mask="abcd",
    )


def _run(endpoint_id: str) -> EvaluationRun:
    return EvaluationRun(
        model_endpoint_id=endpoint_id,
        benchmark_id="benchmark-a",
        benchmark_version="1.0.0",
        configuration_snapshot={"dataset_profile": {"evaluation_type": "custom"}},
        status=RunStatus.COMPLETED.value,
        total_samples=1,
        completed_samples=1,
        successful_samples=1,
        failed_samples=0,
    )


def test_recompute_replaces_legacy_aggregation_rows_for_the_run(tmp_path: Path) -> None:
    database = Database(Settings.local_development(database_url=f"sqlite:///{tmp_path / 'aggregation.db'}"))
    database.initialize()
    try:
        with database.get_session() as session:
            endpoint = _endpoint()
            session.add(endpoint)
            session.flush()
            run = _run(endpoint.id)
            session.add(run)
            session.flush()
            session.add(
                AggregateMetric(
                    run_id=run.id,
                    benchmark_id=run.benchmark_id,
                    model_endpoint_id=run.model_endpoint_id,
                    metric_name="score",
                    metric_value=0.5,
                    sample_count=1,
                    aggregation_version="1.0.0",
                )
            )
            session.commit()
            run_id = run.id
        with database.get_session() as session:
            recompute_aggregate_metrics(session, run_id)
        with database.get_session() as session:
            rows = list(session.scalars(select(AggregateMetric).where(AggregateMetric.run_id == run_id)))
        assert rows
        assert all(row.aggregation_version == AGGREGATION_VERSION for row in rows)
    finally:
        database.dispose()
