"""Ghi TaskHistory (chỉ thêm). Hàm KHÔNG commit: người gọi commit cùng lúc với thay đổi task (một giao dịch)."""
from app.models.task import Task
from app.models.task_history import TaskHistory


def _iso(dt):
    if dt is None:
        return None
    from datetime import timezone
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def task_snapshot(task: Task) -> dict:
    """Ảnh chụp các trường nghiệp vụ, dùng làm before/after."""
    return {
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "assignee_id": task.assignee_id,
        "parent_id": task.parent_id,
    }


def add_event(db, task: Task, actor_id: str, event_type: str, before, after) -> TaskHistory:
    ev = TaskHistory(task_id=task.id, project_id=task.project_id, actor_id=actor_id,
                     event_type=event_type, before_value=before, after_value=after)
    db.add(ev)
    return ev
