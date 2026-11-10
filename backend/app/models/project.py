"""B06: bảng projects và project_members (THIẾT KẾ HỆ THỐNG, MySQL 8)."""
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, String, Integer
from sqlalchemy.orm import relationship

from app.database.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("length(trim(name)) BETWEEN 1 AND 150", name="ck_projects_name"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    description = Column(String(2000), nullable=True)
    timezone = Column(String(64), nullable=False, default="Asia/Ho_Chi_Minh")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
