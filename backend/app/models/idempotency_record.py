"""A04: bản ghi chống xử lý trùng (SDD 3.10). Dùng chung cho duyệt Planner (A04) và Breakdown (A06)."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint

from app.database.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("project_id", "actor_id", "operation", "idempotency_key", name="uq_idempotency_scope"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    operation = Column(String(40), nullable=False)
    idempotency_key = Column(String(160), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    response_payload = Column(JSON, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
