"""A04: duyệt bản nháp AI Planner -> tạo Task thật (chỉ OWNER), trong MỘT transaction.

Thứ tự (theo SDD 5): khóa project -> kiểm OWNER/active -> kiểm idempotency -> khóa draft
-> kiểm DRAFT + version -> kiểm schema các item -> tạo task + lịch sử CREATE -> link draft_created_tasks
-> APPROVED -> lưu idempotency response -> commit. Lỗi ở bất kỳ bước nào: rollback, không tạo gì.
"""
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
from app.schemas.planner import PlannerOutput
from app.services import project_access as access
from app.services.task_history_service import add_event, task_snapshot
from app.services.task_service import task_to_dict

MSG_BAD_ITEMS = "Nội dung bản nháp không hợp lệ, không thể duyệt"


def approve_draft(db: Session, user: User, draft_id: int, expected_version: int | None, idempotency_key: str) -> dict:
    draft = db.get(AIDraft, draft_id)
    if draft is None or draft.draft_type != "PROJECT_PLAN":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy bản nháp")
    project_id = draft.project_id

    project, role = access.get_project_and_role(db, project_id, user, lock=True)
    access.require(role, "project.edit")                      # chỉ OWNER
    new_hash = idem.payload_hash({"draft_id": draft_id, "expected_version": expected_version})

    record = db.scalar(select(IdempotencyRecord).where(
        IdempotencyRecord.project_id == project_id, IdempotencyRecord.actor_id == user.id,
        IdempotencyRecord.operation == idem.OP_PLANNER_APPROVE,
        IdempotencyRecord.idempotency_key == idempotency_key))   # project đã khóa nên các lần duyệt của dự án tuần tự
    decision = idem.decide(record.payload_hash if record else None,
                           bool(record and record.completed_at is not None), new_hash)
    if decision == idem.REPLAY:
        data = dict(record.response_payload)
        db.rollback()
        return data
    if decision == idem.CONFLICT:
        raise HTTPException(status.HTTP_409_CONFLICT, idem.MSG_KEY_REUSED)

    access.require_active(project)
    db.refresh(draft, with_for_update=True)                   # đọc lại có khóa để thấy trạng thái mới nhất
    reason = rules.edit_block_reason(draft.status)
    if reason:
        raise HTTPException(status.HTTP_409_CONFLICT, reason)
    if rules.is_stale(draft.version, expected_version):
        raise HTTPException(status.HTTP_409_CONFLICT, rules.MSG_STALE)
    try:
        items = PlannerOutput.model_validate({"items": (draft.draft_payload or {}).get("items")}).items
    except ValidationError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, MSG_BAD_ITEMS) from None

    try:
        tasks = []
        for item in items:
            task = Task(project_id=project_id, title=item.title, description=item.description, status="TODO",
                        due_date=date.fromisoformat(item.due_date) if item.due_date else None,
                        assignee_id=None, version=1, created_by=user.id)
            db.add(task)
            db.flush()
            add_event(db, task, user.id, "CREATE", None, task_snapshot(task))
            db.add(DraftCreatedTask(draft_id=draft.id, task_id=task.id))
            tasks.append(task)
        draft.status = rules.APPROVED
        draft.approved_by = user.id
        draft.approved_at = datetime.now(timezone.utc)
        draft.version = draft.version + 1
        db.flush()
        for t in tasks:
            db.refresh(t)
        data = {
            "draft_id": draft.id, "project_id": project_id, "type": draft.draft_type,
            "status": draft.status, "version": draft.version,
            "task_ids": [t.id for t in tasks], "tasks": [task_to_dict(t) for t in tasks],
        }
        db.add(IdempotencyRecord(project_id=project_id, actor_id=user.id, operation=idem.OP_PLANNER_APPROVE,
                                 idempotency_key=idempotency_key, payload_hash=new_hash,
                                 response_payload=data, completed_at=datetime.now(timezone.utc)))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return data
