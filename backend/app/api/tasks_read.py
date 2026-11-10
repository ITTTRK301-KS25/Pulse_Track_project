from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.services import task_service
from app.services.response import create_response

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
def get_task(
    req: Request,
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = task_service.get_task(db, user, task_id)
    return create_response(req, 200, "OK", data, None)
