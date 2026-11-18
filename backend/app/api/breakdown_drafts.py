"""A06: sửa, hủy và duyệt bản nháp AI Breakdown."""
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core import idempotency as idem
from app.database.db import get_db
from app.models.user import User
from app.schemas.breakdown_draft import (
    ApproveBreakdownDraftRequest,
    UpdateBreakdownDraftRequest,
)
from app.schemas.planner_approve import check_idempotency_key
from app.services import breakdown_draft_service as service
from app.services.response import create_response

router = APIRouter(prefix="/ai/breakdown/drafts", tags=["AI Breakdown"])


@router.patch("/{draft_id}")
def update_breakdown_draft(
    req: Request,
    draft_id: int,
    body: UpdateBreakdownDraftRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subtasks = [item.model_dump(mode="json") for item in body.subtasks]
    data = service.update_draft(db, user, draft_id, subtasks, body.version)
    return create_response(req, 200, "Đã cập nhật bản nháp", data, None)


@router.post("/{draft_id}/discard")
def discard_breakdown_draft(
    req: Request,
    draft_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = service.discard_draft(db, user, draft_id)
    return create_response(req, 200, "Đã hủy bản nháp", data, None)


@router.post("/{draft_id}/approve")
def approve_breakdown_draft(
    req: Request,
    draft_id: int,
    body: ApproveBreakdownDraftRequest | None = None,
    idempotency_key_header: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    body = body or ApproveBreakdownDraftRequest()
    if body.draft_id is not None and body.draft_id != draft_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "draft_id trong body không khớp đường dẫn")
    key, error = idem.resolve_key(idempotency_key_header, body.idempotency_key)
    if error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error)
    try:
        key = check_idempotency_key(key)
    except Exception:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Idempotency-Key phải dài 8-160 ký tự, chỉ gồm chữ, số và . _ : -",
        ) from None

    data = service.approve_draft(db, user, draft_id, body.expected_version, key)
    return create_response(req, 200, "Đã duyệt bản nháp và tạo subtasks", data, None)
