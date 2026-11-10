from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import case, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.project import ProjectMember
from app.models.user import User
from app.repositories import user_repository
from app.services import project_access as access
from app.services.user_service import normalize_email


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def member_to_dict(member: ProjectMember, user: User) -> dict:
    return {
        "user_id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": member.role,
        "joined_at": _iso(member.joined_at),
    }


def list_members(db: Session, current_user: User, project_id: str) -> list[dict]:
    access.get_project_and_role(db, project_id, current_user)
    role_order = case(
        (ProjectMember.role == "OWNER", 0),
        (ProjectMember.role == "MEMBER", 1),
        else_=2,
    )
    rows = db.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(role_order, ProjectMember.joined_at, User.display_name)
    ).all()
    return [member_to_dict(member, user) for member, user in rows]


def lookup_user(db: Session, current_user: User, project_id: str, email: str) -> dict:
    project, current_role = access.get_project_and_role(db, project_id, current_user)
    access.require(current_role, "member.manage")
    access.require_active(project)

    target = user_repository.get_by_email(db, normalize_email(email))
    if target is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Không tìm thấy tài khoản với email này",
        )
    return {
        "user_id": target.id,
        "email": target.email,
        "display_name": target.display_name,
    }


def add_member(
    db: Session,
    current_user: User,
    project_id: str,
    *,
    email: str,
    role: str,
) -> dict:
    project, current_role = access.get_project_and_role(
        db, project_id, current_user, lock=True
    )
    access.require(current_role, "member.manage")
    access.require_active(project)

    target = user_repository.get_by_email(db, normalize_email(email))
    if target is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Không tìm thấy tài khoản với email này",
        )

    member = ProjectMember(project_id=project_id, user_id=target.id, role=role)
    db.add(member)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Người này đã là thành viên của dự án",
        ) from exc

    db.refresh(member)
    return member_to_dict(member, target)
