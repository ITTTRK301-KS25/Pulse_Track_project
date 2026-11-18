"""A06: sửa, hủy và duyệt bản nháp AI Breakdown."""
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import ai_draft_state as rules
from app.core import idempotency as idem
from app.models.ai_draft import AIDraft
from app.models.draft_created_task import DraftCreatedTask
from app.models.idempotency_record import IdempotencyRecord
from app.models.task import Task
from app.models.user import User
from app.schemas.breakdown import BreakdownOutput
from app.services import project_access as access
from app.services.task_history_service import add_event, task_snapshot
from app.services.task_service import task_to_dict

MSG_BAD_ITEMS = "Nội dung bản nháp không hợp lệ, không thể duyệt"
MSG_PARENT_INACTIVE = "Task cha không còn hoạt động, không thể duyệt bản nháp"


def draft_to_dict(draft: AIDraft) -> dict:
    return {
        "draft_id": draft.id,
        "project_id": draft.project_id,
        "parent_task_id": draft.parent_task_id,
        "type": draft.draft_type,
        "status": draft.status,
        "version": draft.version,
        "subtasks": (draft.draft_payload or {}).get("items", []),
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }


def _load_for_member(db: Session, user: User, draft_id: int) -> AIDraft:
    draft = db.get(AIDraft, draft_id)
    if draft is None or draft.draft_type != "TASK_BREAKDOWN":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy bản nháp")

    project, role = access.get_project_and_role(db, draft.project_id, user, lock=True)
    access.require(role, "task.write")
    access.require_active(project)
    db.refresh(draft, with_for_update=True)
    return draft


def update_draft(
    db: Session,
    user: User,
    draft_id: int,
    subtasks: list[dict],
    expected_version: int | None = None,
) -> dict:
    draft = _load_for_member(db, user, draft_id)
    reason = rules.edit_block_reason(draft.status)
    if reason:
        raise HTTPException(status.HTTP_409_CONFLICT, reason)
    if rules.is_stale(draft.version, expected_version):
        raise HTTPException(status.HTTP_409_CONFLICT, rules.MSG_STALE)
    try:
        items = BreakdownOutput.model_validate({"items": subtasks}).items
    except ValidationError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, MSG_BAD_ITEMS) from None

    normalized = [item.model_dump(mode="json") for item in items]
    current = (draft.draft_payload or {}).get("items", [])
    if rules.same_items(current, normalized):
        data = draft_to_dict(draft)
        db.rollback()
        return data

    try:
        draft.draft_payload = {"items": normalized}
        draft.version += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(draft)
    return draft_to_dict(draft)


def discard_draft(db: Session, user: User, draft_id: int) -> dict:
    draft = _load_for_member(db, user, draft_id)
    reason = rules.edit_block_reason(draft.status)
    if reason:
        raise HTTPException(status.HTTP_409_CONFLICT, reason)
    try:
        draft.status = rules.DISCARDED
        draft.version += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(draft)
    return draft_to_dict(draft)


def approve_draft(
    db: Session,
    user: User,
    draft_id: int,
    expected_version: int | None,
    idempotency_key: str,
) -> dict:
    draft = db.get(AIDraft, draft_id)
    if draft is None or draft.draft_type != "TASK_BREAKDOWN":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy bản nháp")

    project_id = draft.project_id
    project, role = access.get_project_and_role(db, project_id, user, lock=True)
    access.require(role, "task.write")

    new_hash = idem.payload_hash({
        "draft_id": draft_id,
        "expected_version": expected_version,
    })
    record = db.scalar(select(IdempotencyRecord).where(
        IdempotencyRecord.project_id == project_id,
        IdempotencyRecord.actor_id == user.id,
        IdempotencyRecord.operation == idem.OP_BREAKDOWN_APPROVE,
        IdempotencyRecord.idempotency_key == idempotency_key,
    ))
    decision = idem.decide(
        record.payload_hash if record else None,
        bool(record and record.completed_at is not None),
        new_hash,
    )
    if decision == idem.REPLAY:
        data = dict(record.response_payload)
        db.rollback()
        return data
    if decision == idem.CONFLICT:
        raise HTTPException(status.HTTP_409_CONFLICT, idem.MSG_KEY_REUSED)

    access.require_active(project)
    db.refresh(draft, with_for_update=True)
    reason = rules.edit_block_reason(draft.status)
    if reason:
        raise HTTPException(status.HTTP_409_CONFLICT, reason)
    if rules.is_stale(draft.version, expected_version):
        raise HTTPException(status.HTTP_409_CONFLICT, rules.MSG_STALE)

    parent = db.get(Task, draft.parent_task_id) if draft.parent_task_id is not None else None
    if (
        parent is None
        or parent.project_id != project_id
        or parent.parent_id is not None
        or parent.archived_at is not None
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, MSG_PARENT_INACTIVE)
    db.refresh(parent, with_for_update=True)
    if parent.archived_at is not None or parent.parent_id is not None or parent.project_id != project_id:
        raise HTTPException(status.HTTP_409_CONFLICT, MSG_PARENT_INACTIVE)

    try:
        items = BreakdownOutput.model_validate(
            {"items": (draft.draft_payload or {}).get("items")}
        ).items
    except ValidationError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, MSG_BAD_ITEMS) from None

    try:
        subtasks = []
        for item in items:
            subtask = Task(
                project_id=project_id,
                parent_id=parent.id,
                title=item.title,
                description=item.description,
                status="TODO",
                due_date=date.fromisoformat(item.due_date) if item.due_date else None,
                assignee_id=None,
                version=1,
                created_by=user.id,
            )
            db.add(subtask)
            db.flush()
            add_event(db, subtask, user.id, "CREATE", None, task_snapshot(subtask))
            db.add(DraftCreatedTask(draft_id=draft.id, task_id=subtask.id))
            subtasks.append(subtask)

        draft.status = rules.APPROVED
        draft.approved_by = user.id
        draft.approved_at = datetime.now(timezone.utc)
        draft.version += 1
        db.flush()
        for subtask in subtasks:
            db.refresh(subtask)

        data = {
            "draft_id": draft.id,
            "project_id": project_id,
            "parent_task_id": parent.id,
            "type": draft.draft_type,
            "status": draft.status,
            "version": draft.version,
            "subtask_ids": [subtask.id for subtask in subtasks],
            "subtasks": [task_to_dict(subtask) for subtask in subtasks],
        }
        db.add(IdempotencyRecord(
            project_id=project_id,
            actor_id=user.id,
            operation=idem.OP_BREAKDOWN_APPROVE,
            idempotency_key=idempotency_key,
            payload_hash=new_hash,
            response_payload=data,
            completed_at=datetime.now(timezone.utc),
        ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return data
