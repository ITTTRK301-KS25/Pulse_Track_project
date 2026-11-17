"""A05: POST /tasks/{id}/ai/breakdown."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.breakdown import BreakdownRequest
from app.services.breakdown_service import create_breakdown_draft
from app.services.response import create_response

router = APIRouter(prefix="/tasks", tags=["AI Breakdown"])


@router.post("/{task_id}/ai/breakdown")
def create_breakdown(
    req: Request,
    task_id: int,
    body: BreakdownRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = create_breakdown_draft(db, user, task_id, body)
    return create_response(req, 200, "Đã tạo bản nháp AI Breakdown", data, None)
