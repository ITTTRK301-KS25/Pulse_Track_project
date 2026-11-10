"""Quy tắc người thực hiện: phải là OWNER hoặc MEMBER hiện hành của CÙNG dự án (SRS/SDD).

Chỉ kiểm tra khi gán hoặc đổi; để trống (None) luôn hợp lệ. Lịch sử giữ nguyên người đã rời dự án.
B12 dùng lại hàm này.
"""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import ProjectMember

ASSIGNABLE_ROLES = ("OWNER", "MEMBER")
ASSIGNEE_MSG = "Người thực hiện phải là OWNER hoặc MEMBER của dự án"


def validate_assignee(db: Session, project_id: str, assignee_id: str | None) -> None:
    if assignee_id is None:
        return
    role = db.scalar(select(ProjectMember.role).where(
        ProjectMember.project_id == project_id, ProjectMember.user_id == assignee_id))
    if role not in ASSIGNABLE_ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, ASSIGNEE_MSG)
