"""A02: POST /ai/planner."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.planner import PlannerRequest
from app.services.planner_service import create_planner_draft
from app.services.response import create_response

router = APIRouter(prefix="/ai", tags=["AI Planner"])


@router.post("/planner")
def create_planner(
    req: Request,
    body: PlannerRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = create_planner_draft(db, user, body)
    return create_response(req, 200, "Đã tạo bản nháp AI Planner", data, None)
