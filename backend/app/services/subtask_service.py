"""B14: tạo subtask (tối đa một cấp) và đổi trạng thái nhanh.

Tạo subtask dưới task cha {task_id}:
- Task cha không tồn tại -> 404; người ngoài dự án / VIEWER -> 403; dự án đã lưu trữ -> 409.
- Task cha là subtask (cấp ba) -> 422; task cha đã lưu trữ -> 409.
- Subtask luôn cùng dự án với task cha, status TODO, version 1. Người thực hiện (nếu có) phải là OWNER/MEMBER.
- Task + sự kiện CREATE (có parent_id) ghi trong một giao dịch, dòng dự án khóa FOR UPDATE.

Đổi trạng thái nhanh dùng lại đúng logic B12 (khóa lạc quan + lịch sử STATUS_CHANGE).
"""
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import subtask_rules
from app.models.task import Task
from app.models.user import User
from app.services import project_access as access
from app.services import task_update_service
from app.services.assignee_service import validate_assignee
from app.services.task_history_service import add_event, task_snapshot
from app.services.task_service import task_to_dict


def create_subtask(db: Session, user: User, parent_id: str, title: str, description: str | None,
                   due_date: str | None, assignee_id: str | None) -> dict:
    parent = db.get(Task, parent_id)
    if parent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy task cha")
    project, role = access.get_project_and_role(db, parent.project_id, user, lock=True)
    access.require(role, "task.write")
    access.require_active(project)
    db.refresh(parent)
    err = subtask_rules.check_parent(parent.parent_id, parent.archived_at)
    if err == subtask_rules.PARENT_IS_SUBTASK:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Subtask không thể có subtask con (chỉ một cấp)")
    if err == subtask_rules.PARENT_ARCHIVED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Task cha đã lưu trữ, không thể thêm subtask")
    validate_assignee(db, parent.project_id, assignee_id)
    try:
        sub = Task(project_id=parent.project_id, parent_id=parent.id, title=title, description=description,
                   status="TODO", due_date=date.fromisoformat(due_date) if due_date else None,
                   assignee_id=assignee_id, version=1, created_by=user.id)
        db.add(sub)
        db.flush()
        add_event(db, sub, user.id, "CREATE", None, task_snapshot(sub))
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(sub)
    return task_to_dict(sub)


def set_status(db: Session, user: User, task_id: str, new_status: str, version: int) -> dict:
    return task_update_service.update_task(db, user, task_id, version, {"status": new_status})
