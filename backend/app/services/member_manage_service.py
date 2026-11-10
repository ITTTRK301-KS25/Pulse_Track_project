"""B10: đổi vai trò và xóa thành viên.

- Chỉ OWNER thực hiện (kiểm tra ở backend), dự án đã lưu trữ chỉ đọc.
- Không được xóa hoặc hạ quyền OWNER cuối cùng -> 409. Hàng dự án được khóa (FOR UPDATE) trước khi đếm OWNER
  nên hai OWNER cùng tự hạ quyền một lúc cũng không thể để lại dự án không có OWNER.
"""
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.member_rules import would_leave_no_owner
from app.models.project_member import ProjectMember
from app.models.user import User
from app.services import project_access as access
from app.services.member_service import member_to_dict

LAST_OWNER_MSG = "Dự án phải còn ít nhất một OWNER"


def _locked_context(db: Session, actor: User, project_id: int, target_user_id: int):
    project, my_role = access.get_project_and_role(db, project_id, actor, lock=True)
    access.require(my_role, "member.manage")
    access.require_active(project)
    member = db.scalar(select(ProjectMember).where(
        ProjectMember.project_id == project_id, ProjectMember.user_id == target_user_id))
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy thành viên trong dự án")
    owners = db.scalar(select(func.count()).select_from(ProjectMember).where(
        ProjectMember.project_id == project_id, ProjectMember.role == "OWNER"))
    return member, owners


def change_role(db: Session, actor: User, project_id: int, target_user_id: int, new_role: str) -> dict:
    member, owners = _locked_context(db, actor, project_id, target_user_id)
    if member.role != new_role:
        if would_leave_no_owner(owners, member.role, new_role):
            raise HTTPException(status.HTTP_409_CONFLICT, LAST_OWNER_MSG)
        member.role = new_role
        db.commit()
        db.refresh(member)
    user = db.get(User, target_user_id)
    return member_to_dict(member, user)


def remove_member(db: Session, actor: User, project_id: int, target_user_id: int) -> None:
    member, owners = _locked_context(db, actor, project_id, target_user_id)
    if would_leave_no_owner(owners, member.role, None):
        raise HTTPException(status.HTTP_409_CONFLICT, LAST_OWNER_MSG)
    db.delete(member)
    db.commit()
