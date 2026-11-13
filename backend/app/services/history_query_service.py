"""B18: truy vấn lịch sử thay đổi của task (chỉ đọc).

- Mọi thành viên dự án (OWNER/MEMBER/VIEWER) đọc được, kể cả task đã lưu trữ; người ngoài -> 403.
- Task không thuộc dự án trong đường dẫn -> 404.
- Sắp xếp theo occurred_at tăng dần, trùng thời điểm thì theo event_seq tăng dần.
- Phân trang bằng cursor = event_seq của sự kiện cuối trang trước; limit 1..200 (mặc định 50).
"""
from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.history_rules import page_slice
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User
from app.services import project_access as access
from app.services.task_history_service import _iso


def _event_to_dict(e: TaskHistory, actor_name: str | None) -> dict:
    return {
        "event_seq": e.event_seq,
        "task_id": e.task_id,
        "project_id": e.project_id,
        "actor_id": e.actor_id,
        "actor_name": actor_name,
        "event_type": e.event_type,
        "before_value": e.before_value,
        "after_value": e.after_value,
        "occurred_at": _iso(e.occurred_at),
    }


def list_history(db: Session, user: User, project_id: int, task_id: int,
                 cursor: int | None, limit: int) -> dict:
    _, role = access.get_project_and_role(db, project_id, user)
    access.require(role, "project.read")
    task = db.get(Task, task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy task trong dự án này")

    q = (select(TaskHistory, User.display_name)
         .join(User, User.id == TaskHistory.actor_id)
         .where(TaskHistory.task_id == task_id, TaskHistory.project_id == project_id))
    if cursor is not None:
        ref = db.get(TaskHistory, cursor)
        if ref is None or ref.task_id != task_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "cursor không hợp lệ")
        q = q.where(or_(TaskHistory.occurred_at > ref.occurred_at,
                        and_(TaskHistory.occurred_at == ref.occurred_at,
                             TaskHistory.event_seq > ref.event_seq)))
    rows = db.execute(q.order_by(TaskHistory.occurred_at.asc(), TaskHistory.event_seq.asc())
                      .limit(limit + 1)).all()
    page, has_more = page_slice(rows, limit)
    items = [_event_to_dict(e, name) for e, name in page]
    return {"items": items, "next_cursor": items[-1]["event_seq"] if has_more and items else None}
