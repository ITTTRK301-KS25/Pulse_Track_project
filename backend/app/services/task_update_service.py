"""B12: sửa thông tin task và đổi trạng thái Kanban (khóa lạc quan).

Quy trình (một giao dịch):
1. Khóa dòng dự án (FOR UPDATE) -> các cập nhật cùng dự án xếp hàng, không ghi đè nhau.
2. Kiểm tra quyền (OWNER/MEMBER), dự án và task chưa lưu trữ.
3. version client gửi khác version hiện tại -> 409, KHÔNG ghi gì.
4. Chỉ trường thực sự đổi mới ghi: cập nhật task, version + 1, thêm sự kiện lịch sử tương ứng.
Gửi đúng giá trị cũ cho mọi trường -> 200, không tăng version, không ghi lịch sử.
"""
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.task_rules import build_events, changed_fields, is_stale
from app.models.task import Task
from app.models.user import User
from app.services import project_access as access
from app.services.assignee_service import validate_assignee
from app.services.task_history_service import add_event, task_snapshot
from app.services.task_service import task_to_dict

STALE_MSG = "Task đã được người khác cập nhật, vui lòng tải lại rồi thử lại"


def update_task(
    db: Session,
    user: User,
    task_id: int,
    version: int,
    requested: dict,
    *,
    subtask_only: bool = False,
) -> dict:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy task")
    project, role = access.get_project_and_role(db, task.project_id, user, lock=True)
    access.require(role, "task.write")
    access.require_active(project)
    db.refresh(task)
    if task.archived_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Task đã lưu trữ, chỉ được đọc")
    if subtask_only and task.parent_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Endpoint này chỉ áp dụng cho subtask")
    if is_stale(task.version, version):
        raise HTTPException(status.HTTP_409_CONFLICT, STALE_MSG)

    current = task_snapshot(task)
    changes = changed_fields(current, requested)
    if not changes:
        return task_to_dict(task)
    if "assignee_id" in changes:
        validate_assignee(db, task.project_id, changes["assignee_id"])

    try:
        events = build_events(current, changes)
        for field, value in changes.items():
            if field == "due_date":
                value = date.fromisoformat(value) if value else None
            setattr(task, field, value)
        task.version = task.version + 1
        for etype, before, after in events:
            add_event(db, task, user.id, etype, before, after)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(task)
    return task_to_dict(task)
