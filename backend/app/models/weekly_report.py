
"""A10 - Bao cao tuan da luu."""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from app.database.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "week_start",
            name="uq_weekly_report_project_week",
        ),
        UniqueConstraint(
            "preview_id",
            name="uq_weekly_report_preview",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    week_start = Column(Date, nullable=False)

    preview_id = Column(String(160), nullable=False)

    snapshot_hash = Column(String(64), nullable=False)

    snapshot = Column(JSON, nullable=False)

    metrics = Column(JSON, nullable=False)

    ai_narrative = Column(Text, nullable=False)

    timezone = Column(String(100), nullable=False)

    is_mock = Column(Integer, nullable=False, default=0)

    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
