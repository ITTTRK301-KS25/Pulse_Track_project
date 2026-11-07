"""B06 tạo dự án, B07 danh sách/chi tiết, B08 sửa/lưu trữ/khôi phục."""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectMember
from app.models.user import User
from app.services import project_access as access


def _iso(dt: datetime | None) -> str | None:
    """MySQL trả datetime không kèm múi giờ; mọi mốc thời gian lưu UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def project_to_dict(p: Project, role: str | None = None, member_count: int | None = None) -> dict:
    d = {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "start_date": p.start_date.isoformat() if p.start_date else None,
        "end_date": p.end_date.isoformat() if p.end_date else None,
        "timezone": p.timezone,
        "archived_at": _iso(p.archived_at),
        "created_by": p.created_by,
        "created_at": _iso(p.created_at),
        "my_role": role,
    }
    if member_count is not None:
        d["member_count"] = member_count
    return d


# ---------- B06 ----------
def create_project(db: Session, user: User, *, name, description, start_date, end_date, timezone_name) -> dict:
    """Tạo dự án và gán người tạo làm OWNER trong cùng một transaction."""
    project = Project(name=name, description=description, start_date=start_date, end_date=end_date,
                      timezone=timezone_name, created_by=user.id)
    db.add(project)
    try:
        db.flush()
        db.add(ProjectMember(project_id=project.id, user_id=user.id, role=access.OWNER))
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(project)
    return project_to_dict(project, access.OWNER, 1)


# ---------- B07 ----------
def list_projects(db: Session, user: User, status_filter: str = "active") -> list[dict]:
    q = (select(Project, ProjectMember.role)
         .join(ProjectMember, ProjectMember.project_id == Project.id)
         .where(ProjectMember.user_id == user.id)
         .order_by(Project.created_at.desc(), Project.id))
    if status_filter == "active":
        q = q.where(Project.archived_at.is_(None))
    elif status_filter == "archived":
        q = q.where(Project.archived_at.is_not(None))
    rows = db.execute(q).all()
    counts: dict[str, int] = {}
    if rows:
        ids = [p.id for p, _ in rows]
        counts = dict(db.execute(
            select(ProjectMember.project_id, func.count())
            .where(ProjectMember.project_id.in_(ids)).group_by(ProjectMember.project_id)).all())
    return [project_to_dict(p, role, counts.get(p.id, 0)) for p, role in rows]


def get_project(db: Session, user: User, project_id: str) -> dict:
    project, role = access.get_project_and_role(db, project_id, user)
    count = db.scalar(select(func.count()).select_from(ProjectMember).where(ProjectMember.project_id == project_id))
    return project_to_dict(project, role, count)


# ---------- B08 ----------
def update_project(db: Session, user: User, project_id: str, changes: dict) -> dict:
    project, role = access.get_project_and_role(db, project_id, user, lock=True)
    access.require(role, "project.edit")
    access.require_active(project)
    start = changes.get("start_date", project.start_date)
    end = changes.get("end_date", project.end_date)
    if start and end and start > end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Ngày bắt đầu phải trước hoặc bằng ngày kết thúc")
    for key, value in changes.items():
        setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return project_to_dict(project, role)


def set_archived(db: Session, user: User, project_id: str, archive: bool) -> dict:
    """Chỉ đổi archived_at; không đụng tới dữ liệu và múi giờ gốc."""
    project, role = access.get_project_and_role(db, project_id, user, lock=True)
    access.require(role, "project.edit")
    if archive and project.archived_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Dự án đã được lưu trữ")
    if not archive and project.archived_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Dự án đang hoạt động")
    project.archived_at = datetime.now(timezone.utc) if archive else None
    db.commit()
    db.refresh(project)
    return project_to_dict(project, role)
