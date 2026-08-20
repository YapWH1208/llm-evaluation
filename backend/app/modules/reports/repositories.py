from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.db.database import Database
from app.db.models import MediaAsset, Report, ReportShare, ReportSharePasswordAttempt
from app.db.mongo import MongoDocumentStore


class SqliteAssetRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def find_by_digest(self, sha256: str) -> MediaAsset | None:
        with self._database.get_session() as session:
            asset = session.scalar(select(MediaAsset).where(MediaAsset.sha256 == sha256))
            return _detached(asset) if asset is not None else None

    def create_asset(self, values: dict[str, Any]) -> MediaAsset:
        with self._database.get_session() as session:
            asset = MediaAsset(**values)
            session.add(asset)
            session.commit()
            session.refresh(asset)
            return _detached(asset)

    def get_asset(self, asset_id: str) -> MediaAsset | None:
        with self._database.get_session() as session:
            asset = session.get(MediaAsset, asset_id)
            return _detached(asset) if asset is not None else None


class MongoAssetRepository:
    def __init__(self, store: MongoDocumentStore) -> None:
        self._store = store

    def find_by_digest(self, sha256: str) -> dict[str, Any] | None:
        assets = self._store.list_documents("media_assets", query={"sha256": sha256})
        return assets[0] if assets else None

    def create_asset(self, values: dict[str, Any]) -> dict[str, Any]:
        return self._store.insert_document("media_assets", values)

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        return self._store.get_document("media_assets", asset_id)


class SqliteReportRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create_report(self, values: dict[str, Any]) -> Report:
        with self._database.get_session() as session:
            report = Report(**values)
            session.add(report)
            session.commit()
            session.refresh(report)
            return _detached_model(report)

    def get_report(self, report_id: str) -> Report | None:
        with self._database.get_session() as session:
            report = session.get(Report, report_id)
            return _detached_model(report) if report is not None else None

    def list_reports(self, run_id: str) -> list[Report]:
        with self._database.get_session() as session:
            return list(
                session.scalars(select(Report).where(Report.run_id == run_id).order_by(Report.generated_at.desc()))
            )

    def delete_report(self, report_id: str) -> bool:
        with self._database.get_session() as session:
            report = session.get(Report, report_id)
            if report is None:
                return False
            session.execute(delete(ReportShare).where(ReportShare.report_id == report_id))
            session.delete(report)
            session.commit()
            return True

    def create_share(self, values: dict[str, Any]) -> ReportShare:
        with self._database.get_session() as session:
            share = ReportShare(**values)
            session.add(share)
            session.commit()
            session.refresh(share)
            return _detached_model(share)

    def get_share(self, share_id: str) -> ReportShare | None:
        with self._database.get_session() as session:
            share = session.get(ReportShare, share_id)
            return _detached_model(share) if share is not None else None

    def find_share_by_token_hash(self, token_hash: str) -> ReportShare | None:
        with self._database.get_session() as session:
            share = session.scalar(select(ReportShare).where(ReportShare.token_hash == token_hash))
            return _detached_model(share) if share is not None else None

    def list_shares(self, report_id: str) -> list[ReportShare]:
        with self._database.get_session() as session:
            return list(
                session.scalars(
                    select(ReportShare)
                    .where(ReportShare.report_id == report_id)
                    .order_by(ReportShare.created_at.desc())
                )
            )

    def update_share(self, share_id: str, values: dict[str, Any]) -> ReportShare | None:
        with self._database.get_session() as session:
            share = session.get(ReportShare, share_id)
            if share is None:
                return None
            for field, value in values.items():
                setattr(share, field, value)
            session.commit()
            session.refresh(share)
            return _detached_model(share)

    def password_attempt_limit_reached(self, *, share_id: str, client_key: str, now: datetime, limit: int) -> bool:
        with self._database.get_session() as session:
            attempt = session.scalar(
                select(ReportSharePasswordAttempt).where(
                    ReportSharePasswordAttempt.share_id == share_id,
                    ReportSharePasswordAttempt.client_key == client_key,
                )
            )
            return bool(attempt is not None and _as_utc(attempt.expires_at) > now and attempt.failure_count >= limit)

    def record_password_failure(
        self, *, share_id: str, client_key: str, now: datetime, window: timedelta, limit: int
    ) -> None:
        with self._database.get_session() as session:
            expires_at = now + window
            incremented = session.execute(
                update(ReportSharePasswordAttempt)
                .where(
                    ReportSharePasswordAttempt.share_id == share_id,
                    ReportSharePasswordAttempt.client_key == client_key,
                    ReportSharePasswordAttempt.expires_at > now,
                    ReportSharePasswordAttempt.failure_count < limit,
                )
                .values(failure_count=ReportSharePasswordAttempt.failure_count + 1, updated_at=now)
            )
            if incremented.rowcount == 1:
                session.commit()
                return
            reset = session.execute(
                update(ReportSharePasswordAttempt)
                .where(
                    ReportSharePasswordAttempt.share_id == share_id,
                    ReportSharePasswordAttempt.client_key == client_key,
                    ReportSharePasswordAttempt.expires_at <= now,
                )
                .values(failure_count=1, expires_at=expires_at, updated_at=now)
            )
            if reset.rowcount == 1:
                session.commit()
                return
            attempt = session.scalar(
                select(ReportSharePasswordAttempt).where(
                    ReportSharePasswordAttempt.share_id == share_id,
                    ReportSharePasswordAttempt.client_key == client_key,
                )
            )
            if attempt is not None and _as_utc(attempt.expires_at) > now and attempt.failure_count >= limit:
                return
            try:
                session.add(
                    ReportSharePasswordAttempt(
                        share_id=share_id,
                        client_key=client_key,
                        failure_count=1,
                        expires_at=expires_at,
                        updated_at=now,
                    )
                )
                session.commit()
            except IntegrityError:
                session.rollback()
                # A concurrent request won the insert; consume against that row.
                self.record_password_failure(
                    share_id=share_id, client_key=client_key, now=now, window=window, limit=limit
                )


class MongoReportRepository:
    def __init__(self, store: MongoDocumentStore) -> None:
        self._store = store

    def create_report(self, values: dict[str, Any]) -> dict[str, Any]:
        return self._store.insert_document("reports", values)

    def get_report(self, report_id: str) -> dict[str, Any] | None:
        return self._store.get_document("reports", report_id)

    def list_reports(self, run_id: str) -> list[dict[str, Any]]:
        return self._store.list_documents("reports", query={"run_id": run_id}, sort=[("generated_at", -1)])

    def delete_report(self, report_id: str) -> bool:
        shares = self._store.list_documents("report_shares", query={"report_id": report_id})
        share_ids = [str(share["id"]) for share in shares]
        if share_ids:
            self._store.delete_documents("report_share_password_attempts", {"share_id": {"$in": share_ids}})
        self._store.delete_documents("report_shares", {"report_id": report_id})
        return bool(self._store.delete_documents("reports", {"id": report_id}))

    def create_share(self, values: dict[str, Any]) -> dict[str, Any]:
        return self._store.insert_document("report_shares", values)

    def get_share(self, share_id: str) -> dict[str, Any] | None:
        return self._store.get_document("report_shares", share_id)

    def find_share_by_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        shares = self._store.list_documents("report_shares", query={"token_hash": token_hash})
        return shares[0] if shares else None

    def list_shares(self, report_id: str) -> list[dict[str, Any]]:
        return self._store.list_documents("report_shares", query={"report_id": report_id}, sort=[("created_at", -1)])

    def update_share(self, share_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        return self._store.update_document("report_shares", share_id, values)

    def password_attempt_limit_reached(self, *, share_id: str, client_key: str, now: datetime, limit: int) -> bool:
        return (
            self._store.report_share_password_attempt_limit_reached(
                share_id=share_id, client_key=client_key, now=now, limit=limit
            )
            >= limit
        )

    def record_password_failure(
        self, *, share_id: str, client_key: str, now: datetime, window: timedelta, limit: int
    ) -> None:
        self._store.record_report_share_password_failure(
            share_id=share_id, client_key=client_key, now=now, window=window, limit=limit
        )


def _detached(asset: MediaAsset) -> MediaAsset:
    values = {column.name: getattr(asset, column.name) for column in MediaAsset.__table__.columns}
    return MediaAsset(**values)


def _detached_model(item: Any) -> Any:
    values = {column.name: getattr(item, column.name) for column in item.__table__.columns}
    return type(item)(**values)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
