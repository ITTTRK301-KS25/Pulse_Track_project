"""B06: bảng projects và project_members (THIẾT KẾ HỆ THỐNG, MySQL 8)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import relationship

from app.database.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("start_date IS NULL OR end_date IS NULL OR start_date <= end_date", name="ck_projects_dates"),
        CheckConstraint("CHAR_LENGTH(TRIM(name)) BETWEEN 1 AND 150", name="ck_projects_name"),
    )

    id = Column(String(36), primary_key=True, default=_new_id)
    name = Column(String(150), nullable=False)
    description = Column(String(2000), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    timezone = Column(String(64), nullable=False, default="Asia/Ho_Chi_Minh")  # IANA, cố định sau khi tạo
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    archived_at = Column(DateTime(timezone=True), nullable=True)               # có giá trị = đã lưu trữ
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        CheckConstraint("role IN ('OWNER','MEMBER','VIEWER')", name="ck_project_members_role"),
        Index("ix_project_members_user_id", "user_id"),
    )

    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    role = Column(String(10), nullable=False)
    joined_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    project = relationship("Project", back_populates="members")
