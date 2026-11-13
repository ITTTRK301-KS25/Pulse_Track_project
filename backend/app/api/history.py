"""B18: GET /projects/{project_id}/tasks/{task_id}/history (chỉ đọc; không có API sửa/xóa lịch sử)."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core import history_guard  # noqa: F401  (B17: bật chặn sửa/xóa task_history ở tầng ORM)
from app.database.db import get_db
from app.models.user import User
from app.services import history_query_service
from app.services.response import create_response

router = APIRouter(prefix="/projects/{project_id}/tasks/{task_id}/history", tags=["history"])


@router.get("")
def list_history(req: Request, project_id: int, task_id: int,
                 cursor: int | None = Query(None, ge=1),
                 limit: int = Query(50, ge=1, le=200),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = history_query_service.list_history(db, user, project_id, task_id, cursor, limit)
    return create_response(req, 200, "OK", data, None)
