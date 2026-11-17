"""A02: persistent drafts returned by AI Planner."""
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, JSON, String

from app.database.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AIDraft(Base):
    __tablename__ = "ai_drafts"
    __table_args__ = (
        CheckConstraint(
            "type IN ('PROJECT_PLAN','TASK_BREAKDOWN')",
            name="ck_ai_drafts_type",
        ),
        CheckConstraint(
            "status IN ('DRAFT','APPROVED','DISCARDED')",
            name="ck_ai_drafts_status",
        ),
        CheckConstraint("version >= 1", name="ck_ai_drafts_version"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    draft_type = Column("type", String(20), nullable=False, default="PROJECT_PLAN")
    status = Column(String(12), nullable=False, default="DRAFT")
    input_payload = Column(JSON, nullable=False)
    draft_payload = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
