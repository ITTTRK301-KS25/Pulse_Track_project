"""Người thực hiện phải là OWNER hoặc MEMBER hiện hành của cùng dự án.

Chỉ kiểm tra khi gán hoặc đổi; để trống (None) luôn hợp lệ.
"""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project_member import ProjectMember

ASSIGNABLE_ROLES = ("OWNER", "MEMBER")
ASSIGNEE_MSG = "Người thực hiện phải là OWNER hoặc MEMBER của dự án"


def validate_assignee(db: Session, project_id: int, assignee_id: int | None) -> None:
    if assignee_id is None:
        return
    role = db.scalar(select(ProjectMember.role).where(
        ProjectMember.project_id == project_id, ProjectMember.user_id == assignee_id))
    if role not in ASSIGNABLE_ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, ASSIGNEE_MSG)
