"""B13: POST /tasks/{id}/archive và /tasks/{id}/restore."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.services import task_archive_service
from app.services.response import create_response

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/{task_id}/archive")
def archive(req: Request, task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return create_response(req, 200, "Đã lưu trữ task", task_archive_service.archive_task(db, user, task_id), None)


@router.post("/{task_id}/restore")
def restore(req: Request, task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return create_response(req, 200, "Đã khôi phục task", task_archive_service.restore_task(db, user, task_id), None)
