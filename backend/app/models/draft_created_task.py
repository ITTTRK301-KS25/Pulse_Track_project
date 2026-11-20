"""A04: liên kết bản nháp AI đã duyệt với các task thật được tạo (SDD 3.9)."""
from sqlalchemy import Column, ForeignKey, Integer

from app.database.db import Base


class DraftCreatedTask(Base):
    __tablename__ = "draft_created_tasks"

    draft_id = Column(Integer, ForeignKey("ai_drafts.id", ondelete="CASCADE"), primary_key=True)
    # unique: mỗi task chỉ thuộc tối đa một bản nháp
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True, unique=True)
