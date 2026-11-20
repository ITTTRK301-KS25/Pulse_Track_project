"""A04: POST /ai/planner/drafts/{id}/approve."""
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core import idempotency as idem
from app.database.db import get_db
from app.models.user import User
from app.schemas.planner_approve import ApprovePlannerDraftRequest, check_idempotency_key
from app.services import planner_approve_service as service
from app.services.response import create_response

router = APIRouter(prefix="/ai/planner/drafts", tags=["AI Planner"])


@router.post("/{draft_id}/approve")
def approve_planner_draft(
    req: Request,
    draft_id: int,
    body: ApprovePlannerDraftRequest | None = None,
    idempotency_key_header: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    body = body or ApprovePlannerDraftRequest()
    if body.draft_id is not None and body.draft_id != draft_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "draft_id trong body không khớp đường dẫn")
    key, err = idem.resolve_key(idempotency_key_header, body.idempotency_key)
    if err:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, err)
    try:
        key = check_idempotency_key(key)
    except Exception:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Idempotency-Key phải dài 8-160 ký tự, chỉ gồm chữ, số và . _ : -")
    data = service.approve_draft(db, user, draft_id, body.expected_version, key)
    return create_response(req, 200, "Đã duyệt bản nháp và tạo task", data, None)
