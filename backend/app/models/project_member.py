from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from app.database.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        CheckConstraint("role IN ('OWNER','MEMBER','VIEWER')", name="ck_project_members_role"),
        Index("ix_project_members_user_id", "user_id"),
    )

    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    role = Column(String(20), nullable=False, default="MEMBER")
    joined_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    project = relationship("Project", back_populates="members")