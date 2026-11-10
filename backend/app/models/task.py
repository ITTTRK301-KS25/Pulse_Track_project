"""B11: bảng tasks (THIẾT KẾ HỆ THỐNG mục 3.5, MySQL 8)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from app.database.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("status IN ('TODO','IN_PROGRESS','DONE')", name="ck_tasks_status"),
        CheckConstraint("CHAR_LENGTH(TRIM(title)) BETWEEN 1 AND 200", name="ck_tasks_title"),
        Index("ix_tasks_project_status", "project_id", "status"),
        Index("ix_tasks_assignee", "assignee_id"),
    )

    id = Column(String(36), primary_key=True, default=_new_id)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(String(36), ForeignKey("tasks.id"), nullable=True)      # subtask một cấp (task B14)
    title = Column(String(200), nullable=False)
    description = Column(String(5000), nullable=True)
    status = Column(String(12), nullable=False, default="TODO")
    due_date = Column(Date, nullable=True)
    assignee_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    version = Column(Integer, nullable=False, default=1)                          # khóa lạc quan
    archived_at = Column(DateTime(timezone=True), nullable=True)                  # task B13
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
