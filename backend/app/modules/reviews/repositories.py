from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.database import Database
from app.db.models import HumanReview, SampleAttempt
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
