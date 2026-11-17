"""A04: POST /ai/planner/drafts/{id}/approve."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.planner_approve import ApprovePlannerDraftRequest
from app.services import planner_approve_service as service
from app.services.response import create_response

router = APIRouter(prefix="/ai/planner/drafts", tags=["AI Planner"])


@router.post("/{draft_id}/approve")
def approve_planner_draft(
    req: Request,
    draft_id: int,
    body: ApprovePlannerDraftRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = service.approve_draft(db, user, draft_id, body.expected_version, body.idempotency_key)
    return create_response(req, 200, "Đã duyệt bản nháp và tạo task", data, None)
