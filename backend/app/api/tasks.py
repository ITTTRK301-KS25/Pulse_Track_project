"""B11: POST /projects/{project_id}/tasks."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.task import CreateTaskRequest
from app.services import task_service
from app.services.response import create_response

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])


@router.post("", status_code=201)
def create_task(req: Request, project_id: int, body: CreateTaskRequest,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = task_service.create_task(db, user, project_id, body.title, body.description,
                                    body.due_date, body.assignee_id)
    return create_response(req, 201, "Đã tạo task", data, None)


@router.get("")
def list_tasks(
    req: Request,
    project_id: int,
    status: Literal["TODO", "IN_PROGRESS", "DONE"] | None = None,
    assignee_id: int | None = None,
    keyword: str | None = None,
    due_date: date | None = None,
    archived: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = task_service.list_tasks(
        db,
        user,
        project_id,
        status_filter=status,
        assignee_id=assignee_id,
        keyword=keyword,
        due_date=due_date,
        archived=archived,
    )
    return create_response(req, 200, "OK", data, None)
