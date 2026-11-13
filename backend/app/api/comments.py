"""B15: POST và B16: GET /projects/{project_id}/tasks/{task_id}/comments."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.comment import CreateCommentRequest
from app.services import comment_service
from app.services.response import create_response

router = APIRouter(prefix="/projects/{project_id}/tasks/{task_id}/comments", tags=["comments"])


@router.post("", status_code=201)
def create_comment(req: Request, project_id: int, task_id: int, body: CreateCommentRequest,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = comment_service.create_comment(db, user, project_id, task_id, body.content)
    return create_response(req, 201, "Đã thêm bình luận", data, None)


@router.get("")
def list_comments(req: Request, project_id: int, task_id: int,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = comment_service.list_comments(db, user, project_id, task_id)
    return create_response(req, 200, "OK", data, None)
