"""B11: bảng tasks (THIẾT KẾ HỆ THỐNG mục 3.5, MySQL 8)."""
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer, String
from app.database.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("status IN ('TODO','IN_PROGRESS','DONE')", name="ck_tasks_status"),
        CheckConstraint("length(trim(title)) BETWEEN 1 AND 200", name="ck_tasks_title"),
        Index("ix_tasks_project_status", "project_id", "status"),
        Index("ix_tasks_assignee", "assignee_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(String(5000), nullable=True)
    status = Column(String(12), nullable=False, default="TODO")
    due_date = Column(Date, nullable=True)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
