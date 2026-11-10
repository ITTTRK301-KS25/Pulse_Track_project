"""B12: PATCH /tasks/{task_id} (sửa thông tin và đổi trạng thái Kanban)."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.task_update import UpdateTaskRequest
from app.services import task_update_service
from app.services.response import create_response

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.patch("/{task_id}")
def update_task(req: Request, task_id: str, body: UpdateTaskRequest,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = task_update_service.update_task(db, user, task_id, body.version, body.requested())
    return create_response(req, 200, "Đã cập nhật task", data, None)
