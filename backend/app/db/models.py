from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, func
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
