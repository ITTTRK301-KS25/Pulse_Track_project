"""Kiểm tra quyền theo dự án ở backend. Các task sau (Task, Thành viên, Comment, AI...) dùng lại các hàm này.

- Không thuộc dự án và dự án không tồn tại đều trả 403 như nhau, để không lộ dữ liệu.
- Dự án đã lưu trữ chỉ đọc: gọi require_active(project) trước mọi thao tác ghi (409).
"""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectMember
from app.models.user import User

OWNER, MEMBER, VIEWER = "OWNER", "MEMBER", "VIEWER"

PERMISSIONS = {
    "project.read": (OWNER, MEMBER, VIEWER),
    "project.edit": (OWNER,),            # sửa tên/mô tả, archive, restore
    "member.manage": (OWNER,),
    "task.write": (OWNER, MEMBER),
    "comment.write": (OWNER, MEMBER),
}


def can(role: str | None, action: str) -> bool:
    return role is not None and role in PERMISSIONS.get(action, ())


def get_project_and_role(db: Session, project_id: str, user: User, *, lock: bool = False) -> tuple[Project, str]:
    q = select(Project).where(Project.id == project_id)
    if lock:
        q = q.with_for_update()
    project = db.scalar(q)
    role = None
    if project is not None:
        role = db.scalar(select(ProjectMember.role).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user.id))
    if project is None or role is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bạn không thuộc dự án này")
    return project, role


def require(role: str, action: str) -> None:
    if not can(role, action):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bạn không có quyền thực hiện thao tác này")


def require_active(project: Project) -> None:
    if project.archived_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Dự án đã lưu trữ, chỉ được đọc")
