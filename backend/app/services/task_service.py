"""B11: tạo task trong dự án.

- Chỉ OWNER/MEMBER (VIEWER và người ngoài dự án bị 403), dự án đã lưu trữ chỉ đọc (409).
- status luôn TODO, version = 1. Người thực hiện (nếu có) phải là OWNER/MEMBER của dự án.
- Task và sự kiện CREATE (after = ảnh chụp đầy đủ) được ghi trong MỘT giao dịch.
"""
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.user import User
from app.services import project_access as access
from app.services.assignee_service import validate_assignee
from app.services.task_history_service import _iso, add_event, task_snapshot


def task_to_dict(t: Task) -> dict:
    return {
        "id": t.id,
        "project_id": t.project_id,
        "parent_id": t.parent_id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "assignee_id": t.assignee_id,
        "version": t.version,
        "archived_at": _iso(t.archived_at),
        "created_by": t.created_by,
        "created_at": _iso(t.created_at),
        "updated_at": _iso(t.updated_at),
    }


def create_task(db: Session, user: User, project_id: int, title: str, description: str | None,
                due_date: str | None, assignee_id: int | None) -> dict:
    project, role = access.get_project_and_role(db, project_id, user, lock=True)
    access.require(role, "task.write")
    access.require_active(project)
    validate_assignee(db, project_id, assignee_id)
    try:
        task = Task(project_id=project_id, title=title, description=description, status="TODO",
                    due_date=date.fromisoformat(due_date) if due_date else None,
                    assignee_id=assignee_id, version=1, created_by=user.id)
        db.add(task)
        db.flush()
        add_event(db, task, user.id, "CREATE", None, task_snapshot(task))
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(task)
    return task_to_dict(task)


def list_tasks(
    db: Session,
    user: User,
    project_id: int,
    *,
    status_filter: str | None = None,
    assignee_id: int | None = None,
    keyword: str | None = None,
    due_date: date | None = None,
    archived: bool = False,
) -> list[dict]:
    _, role = access.get_project_and_role(db, project_id, user)
    access.require(role, "project.read")

    query = select(Task).where(Task.project_id == project_id)
    query = query.where(Task.archived_at.is_not(None) if archived else Task.archived_at.is_(None))
    if status_filter is not None:
        query = query.where(Task.status == status_filter)
    if assignee_id is not None:
        query = query.where(Task.assignee_id == assignee_id)
    if due_date is not None:
        query = query.where(Task.due_date == due_date)
    if keyword and keyword.strip():
        term = f"%{keyword.strip()}%"
        query = query.where(or_(Task.title.ilike(term), Task.description.ilike(term)))

    tasks = db.scalars(query.order_by(Task.created_at.desc(), Task.id)).all()
    return [task_to_dict(task) for task in tasks]


def get_task(db: Session, user: User, task_id: int) -> dict:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy task")
    _, role = access.get_project_and_role(db, task.project_id, user)
    access.require(role, "project.read")
    return task_to_dict(task)
