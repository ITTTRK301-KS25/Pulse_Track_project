"""A03: sửa và hủy bản nháp AI Planner (chỉ OWNER, chỉ khi DRAFT). Không bao giờ tạo hay đổi Task."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import ai_draft_state as rules
from app.models.ai_draft import AIDraft
from app.models.user import User
from app.services import project_access as access


def draft_to_dict(draft: AIDraft) -> dict:
    return {
        "draft_id": draft.id,
        "project_id": draft.project_id,
        "type": draft.draft_type,
        "status": draft.status,
        "version": draft.version,
        "suggestions": (draft.draft_payload or {}).get("items", []),
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }


def _load_for_owner(db: Session, user: User, draft_id: int) -> AIDraft:
    """Tìm draft PROJECT_PLAN, khóa dự án, kiểm OWNER + dự án active, rồi đọc lại draft sau khi giữ khóa."""
    draft = db.get(AIDraft, draft_id)
    if draft is None or draft.draft_type != "PROJECT_PLAN":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy bản nháp")
    project, role = access.get_project_and_role(db, draft.project_id, user, lock=True)
    access.require(role, "project.edit")      # chỉ OWNER
    access.require_active(project)
    # Đọc lại có khóa (FOR UPDATE) để lấy dữ liệu mới nhất; đọc thường trên MySQL có thể thấy ảnh chụp cũ.
    db.refresh(draft, with_for_update=True)
    return draft


def update_draft(db: Session, user: User, draft_id: int, suggestions: list[dict],
                 expected_version: int | None = None) -> dict:
    draft = _load_for_owner(db, user, draft_id)
    reason = rules.edit_block_reason(draft.status)
    if reason:
        raise HTTPException(status.HTTP_409_CONFLICT, reason)
    if rules.is_stale(draft.version, expected_version):
        raise HTTPException(status.HTTP_409_CONFLICT, rules.MSG_STALE)
    if rules.same_items((draft.draft_payload or {}).get("items"), suggestions):
        data = draft_to_dict(draft)
        db.rollback()                          # không đổi gì, nhả khóa
        return data
    try:
        draft.draft_payload = {"items": suggestions}
        draft.version = draft.version + 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(draft)
    return draft_to_dict(draft)


def discard_draft(db: Session, user: User, draft_id: int) -> dict:
    draft = _load_for_owner(db, user, draft_id)
    reason = rules.edit_block_reason(draft.status)
    if reason:
        raise HTTPException(status.HTTP_409_CONFLICT, reason)
    try:
        draft.status = rules.DISCARDED
        draft.version = draft.version + 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(draft)
    return draft_to_dict(draft)
