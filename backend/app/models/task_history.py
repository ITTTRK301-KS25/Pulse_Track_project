"""B11: bảng task_history, chỉ thêm, không sửa/xóa (THIẾT KẾ HỆ THỐNG mục 3.x).

event_seq là khóa chính tự tăng để có thứ tự phát lại ổn định cho chỉ số MET-01..06.
event_id là UUID dùng làm mã sự kiện.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, JSON, String

from app.database.db import Base

EVENT_TYPES = ("CREATE", "STATUS_CHANGE", "DUE_CHANGE", "ASSIGNEE_CHANGE",
               "PARENT_CHANGE", "ARCHIVE", "RESTORE", "DETAIL_CHANGE")


class TaskHistory(Base):
    __tablename__ = "task_history"
    __table_args__ = (Index("ix_task_history_task", "task_id", "event_seq"),
                      Index("ix_task_history_project", "project_id", "event_seq"))

    event_seq = Column(BigInteger().with_variant(BigInteger, "mysql"), primary_key=True, autoincrement=True)
    event_id = Column(String(36), nullable=False, unique=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    actor_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    event_type = Column(String(20), nullable=False)
    before_value = Column(JSON, nullable=True)
    after_value = Column(JSON, nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
