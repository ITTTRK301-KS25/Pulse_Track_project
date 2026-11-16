"""Người thực hiện phải là OWNER hoặc MEMBER hiện hành của cùng dự án (B19).

Đây là NƠI DUY NHẤT kiểm assignee; được dùng chung bởi
  - task_service.create_task        (B11)
  - task_update_service.update_task (B12, chỉ gọi khi assignee thật sự đổi)
  - subtask_service.create_subtask  (B14)
Không có endpoint riêng cho assignee. Lỗi: 422 với thông báo ASSIGNEE_MSG.
Quy tắc thuần nằm ở app/core/assignee_rules.py.
"""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.assignee_rules import ASSIGNABLE_ROLES, ASSIGNEE_MSG, is_assignable, needs_check  # noqa: F401
from app.models.project_member import ProjectMember


def validate_assignee(db: Session, project_id: int, assignee_id: int | None) -> None:
    if not needs_check(assignee_id):
        return
    role = db.scalar(select(ProjectMember.role).where(
        ProjectMember.project_id == project_id, ProjectMember.user_id == assignee_id))
    if not is_assignable(role):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, ASSIGNEE_MSG)
