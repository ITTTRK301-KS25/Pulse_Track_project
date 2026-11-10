"""B13: lưu trữ / khôi phục task (xóa mềm bằng archived_at).

- Chỉ OWNER/MEMBER (403 với VIEWER/ngoài dự án); dự án đã lưu trữ chỉ đọc (409).
- Task đổi trạng thái -> version + 1 (người đang sửa task cũ sẽ bị 409 ở B12), ghi sự kiện ARCHIVE/RESTORE
  với before/after = archived_at, tất cả trong một giao dịch, dòng dự án khóa FOR UPDATE.
- Bấm lặp lại (đã lưu trữ rồi lại lưu trữ) -> 200, không ghi gì thêm.
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.archive_rules import next_archive_state
from app.models.task import Task
from app.models.user import User
from app.services import project_access as access
from app.services.task_history_service import _iso, add_event
from app.services.task_service import task_to_dict


def _change(db: Session, user: User, task_id: str, action: str) -> dict:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy task")
    project, role = access.get_project_and_role(db, task.project_id, user, lock=True)
    access.require(role, "task.write")
    access.require_active(project)
    db.refresh(task)
    do, event = next_archive_state(task.archived_at is not None, action)
    if not do:
        return task_to_dict(task)
    try:
        before = {"archived_at": _iso(task.archived_at)}
        task.archived_at = datetime.now(timezone.utc) if action == "archive" else None
        task.version = task.version + 1
        db.flush()
        add_event(db, task, user.id, event, before, {"archived_at": _iso(task.archived_at)})
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(task)
    return task_to_dict(task)


def archive_task(db: Session, user: User, task_id: str) -> dict:
    return _change(db, user, task_id, "archive")


def restore_task(db: Session, user: User, task_id: str) -> dict:
    return _change(db, user, task_id, "restore")
