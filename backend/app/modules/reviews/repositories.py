from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.database import Database
from app.db.models import EvaluationRun, HumanReview, JudgeAssessment, ModelEndpoint, SampleAttempt
from app.db.mongo import MongoDocumentStore


class SqliteReviewRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def sample_attempt_exists(self, sample_attempt_id: str) -> bool:
        with self._database.get_session() as session:
            return session.get(SampleAttempt, sample_attempt_id) is not None

    def create(self, values: dict[str, Any]) -> HumanReview:
        with self._database.get_session() as session:
            review = HumanReview(**values)
            session.add(review)
            session.commit()
            session.refresh(review)
            return review

    def list_for_sample(self, sample_attempt_id: str) -> list[HumanReview]:
        with self._database.get_session() as session:
            return list(
                session.scalars(
                    select(HumanReview)
                    .where(HumanReview.sample_attempt_id == sample_attempt_id)
                    .order_by(HumanReview.created_at)
                )
            )


class SqliteJudgeRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def get_sample_attempt(self, sample_attempt_id: str) -> SampleAttempt | None:
        return self._get_detached(SampleAttempt, sample_attempt_id)

    def get_endpoint(self, endpoint_id: str) -> ModelEndpoint | None:
        return self._get_detached(ModelEndpoint, endpoint_id)

    def get_run(self, run_id: str) -> EvaluationRun | None:
        return self._get_detached(EvaluationRun, run_id)

    def create_assessment(self, values: dict[str, Any]) -> JudgeAssessment:
        with self._database.get_session() as session:
            assessment = JudgeAssessment(**values)
            session.add(assessment)
            session.commit()
            session.refresh(assessment)
            return _detached(assessment)

    def update_assessment(self, assessment_id: str, values: dict[str, Any]) -> JudgeAssessment | None:
        with self._database.get_session() as session:
            assessment = session.get(JudgeAssessment, assessment_id)
            if assessment is None:
                return None
            for field, value in values.items():
                setattr(assessment, field, value)
            session.commit()
            session.refresh(assessment)
            return _detached(assessment)

    def list_assessments(self, sample_attempt_id: str) -> list[JudgeAssessment]:
        with self._database.get_session() as session:
            return list(
                session.scalars(
                    select(JudgeAssessment)
                    .where(JudgeAssessment.sample_attempt_id == sample_attempt_id)
                    .order_by(JudgeAssessment.created_at.desc())
                )
            )

    def _get_detached(self, model: Any, item_id: str) -> Any | None:
        with self._database.get_session() as session:
            item = session.get(model, item_id)
            return _detached(item) if item is not None else None


class MongoReviewRepository:
    def __init__(self, store: MongoDocumentStore) -> None:
        self._store = store

    def sample_attempt_exists(self, sample_attempt_id: str) -> bool:
        return self._store.get_document("sample_attempts", sample_attempt_id) is not None

    def create(self, values: dict[str, Any]) -> dict[str, Any]:
        return self._store.insert_document("human_reviews", values)

    def list_for_sample(self, sample_attempt_id: str) -> list[dict[str, Any]]:
        return self._store.list_documents(
            "human_reviews", query={"sample_attempt_id": sample_attempt_id}, sort=[("created_at", 1)]
        )


class MongoJudgeRepository:
    def __init__(self, store: MongoDocumentStore) -> None:
        self._store = store

    def get_sample_attempt(self, sample_attempt_id: str) -> dict[str, Any] | None:
        return self._store.get_document("sample_attempts", sample_attempt_id)

    def get_endpoint(self, endpoint_id: str) -> dict[str, Any] | None:
        return self._store.get_document("model_endpoints", endpoint_id)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self._store.get_document("evaluation_runs", run_id)

    def create_assessment(self, values: dict[str, Any]) -> dict[str, Any]:
        return self._store.insert_document("judge_assessments", values)

    def update_assessment(self, assessment_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        return self._store.update_document("judge_assessments", assessment_id, values)

    def list_assessments(self, sample_attempt_id: str) -> list[dict[str, Any]]:
        return self._store.list_documents(
            "judge_assessments", query={"sample_attempt_id": sample_attempt_id}, sort=[("created_at", -1)]
        )


def _detached(item: Any) -> Any:
    values = {column.name: getattr(item, column.name) for column in item.__table__.columns}
    return type(item)(**values)
