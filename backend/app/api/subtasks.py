"""B14: POST /tasks/{id}/subtasks và PATCH /tasks/{id}/status."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.task import CreateTaskRequest
from app.schemas.task_status import SetStatusRequest
from app.services import subtask_service
from app.services.response import create_response

router = APIRouter(prefix="/tasks", tags=["subtasks"])


@router.post("/{task_id}/subtasks", status_code=201)
def create_subtask(req: Request, task_id: str, body: CreateTaskRequest,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = subtask_service.create_subtask(db, user, task_id, body.title, body.description,
                                          body.due_date, body.assignee_id)
    return create_response(req, 201, "Đã tạo subtask", data, None)


@router.patch("/{task_id}/status")
def set_status(req: Request, task_id: str, body: SetStatusRequest,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = subtask_service.set_status(db, user, task_id, body.status, body.version)
    return create_response(req, 200, "Đã đổi trạng thái", data, None)
