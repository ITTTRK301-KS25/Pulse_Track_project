"""A03: PATCH /ai/planner/drafts/{id} (sửa) và POST /ai/planner/drafts/{id}/discard (hủy)."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.planner_draft import UpdatePlannerDraftRequest
from app.services import planner_draft_service as service
from app.services.response import create_response

router = APIRouter(prefix="/ai/planner/drafts", tags=["AI Planner"])


@router.patch("/{draft_id}")
def update_planner_draft(
    req: Request,
    draft_id: int,
    body: UpdatePlannerDraftRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    suggestions = [s.model_dump(mode="json") for s in body.suggestions]
    data = service.update_draft(db, user, draft_id, suggestions, body.version)
    return create_response(req, 200, "Đã cập nhật bản nháp", data, None)


@router.post("/{draft_id}/discard")
def discard_planner_draft(
    req: Request,
    draft_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = service.discard_draft(db, user, draft_id)
    return create_response(req, 200, "Đã hủy bản nháp", data, None)
