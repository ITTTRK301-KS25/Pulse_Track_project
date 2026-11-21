"""A07: metadata lịch sử gọi AI; không lưu prompt, phản hồi hoặc thông tin xác thực."""
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String

from app.database.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AICallLog(Base):
    __tablename__ = "ai_call_logs"
    __table_args__ = (
        CheckConstraint(
            "type IN ('PLANNER','BREAKDOWN','REPORT')",
            name="ck_ai_call_logs_type",
        ),
        CheckConstraint(
            "status IN ('SUCCESS','ERROR','TIMEOUT','RATE_LIMIT')",
            name="ck_ai_call_logs_status",
        ),
        Index("ix_ai_call_logs_project_created", "project_id", "created_at"),
        Index("ix_ai_call_logs_request_id", "request_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    request_id = Column(String(120), nullable=False)
    type = Column(String(40), nullable=False)
    status = Column(String(20), nullable=False)
    error_code = Column(String(80), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
