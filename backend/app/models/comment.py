"""B15: bảng comments (THIẾT KẾ HỆ THỐNG mục 3.6). Bình luận chỉ thêm và đọc, không sửa/xóa trong phạm vi MVP."""
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String

from app.database.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        CheckConstraint("length(trim(content)) BETWEEN 1 AND 2000", name="ck_comments_content"),
        Index("ix_comments_task_time", "task_id", "created_at", "id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)   # giữ tác giả lịch sử
    content = Column(String(2000), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
