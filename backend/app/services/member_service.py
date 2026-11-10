"""B09: danh sách và thêm thành viên dự án.

- Chỉ OWNER được thêm (kiểm tra ở backend); mọi thành viên được xem danh sách.
- Email phải thuộc một tài khoản đã đăng ký (404 nếu không có).
- Chống trùng membership: đã là thành viên -> 409; hai yêu cầu song song vẫn an toàn nhờ khóa chính (project_id, user_id).
- Dự án đã lưu trữ chỉ đọc (409).
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import case, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.project_member import ProjectMember
from app.models.user import User
from app.repositories import user_repository
from app.services import project_access as access


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def member_to_dict(m: ProjectMember, u: User) -> dict:
    return {
        "user_id": u.id,
        "email": u.email,
        "display_name": u.display_name,
        "role": m.role,
        "joined_at": _iso(m.joined_at),
    }


def list_members(db: Session, user: User, project_id: int) -> list[dict]:
    access.get_project_and_role(db, project_id, user)
    order_role = case((ProjectMember.role == "OWNER", 0), (ProjectMember.role == "MEMBER", 1), else_=2)
    rows = db.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(order_role, ProjectMember.joined_at, User.display_name)
    ).all()
    return [member_to_dict(m, u) for m, u in rows]


def lookup_account(db: Session, actor: User, project_id: int, email: str) -> dict:
    project, my_role = access.get_project_and_role(db, project_id, actor)
    access.require(my_role, "member.manage")
    access.require_active(project)

    target = user_repository.get_by_email(db, email.strip().lower())
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy tài khoản với email này")
    return {"email": target.email, "display_name": target.display_name}


def add_member(db: Session, actor: User, project_id: int, *, email: str, role: str) -> dict:
    project, my_role = access.get_project_and_role(db, project_id, actor, lock=True)
    access.require(my_role, "member.manage")
    access.require_active(project)

    target = user_repository.get_by_email(db, email)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy tài khoản với email này")

    exists = db.scalar(select(ProjectMember).where(
        ProjectMember.project_id == project_id, ProjectMember.user_id == target.id))
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Người này đã là thành viên của dự án")

    member = ProjectMember(project_id=project_id, user_id=target.id, role=role)
    db.add(member)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Người này đã là thành viên của dự án")
    db.refresh(member)
    return member_to_dict(member, target)
