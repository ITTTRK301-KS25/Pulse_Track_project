"""B11: tạo task trong dự án.

- Chỉ OWNER/MEMBER (VIEWER và người ngoài dự án bị 403), dự án đã lưu trữ chỉ đọc (409).
- status luôn TODO, version = 1. Người thực hiện (nếu có) phải là OWNER/MEMBER của dự án.
- Task và sự kiện CREATE (after = ảnh chụp đầy đủ) được ghi trong MỘT giao dịch.
"""
from datetime import date

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


def create_task(db: Session, user: User, project_id: str, title: str, description: str | None,
                due_date: str | None, assignee_id: str | None) -> dict:
    project, role = access.get_project_and_role(db, project_id, user, lock=True)
    access.require(role, "task.write")
    access.require_active(project)
    validate_assignee(db, project_id, assignee_id)
    try:
        task = Task(project_id=project_id, title=title, description=description, status="TODO",
                    due_date=date.fromisoformat(due_date) if due_date else None,
                    assignee_id=assignee_id, version=1, created_by=user.id)
        db.add(task)
        db.flush()  # có task.id
        add_event(db, task, user.id, "CREATE", None, task_snapshot(task))
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(task)
    return task_to_dict(task)
