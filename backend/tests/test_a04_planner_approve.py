"""A04: duyệt bản nháp AI Planner với DB thật (SQLite trong bộ nhớ)."""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import ai_draft_state as S
from app.database.db import Base
from app.models.ai_draft import AIDraft
from app.models.draft_created_task import DraftCreatedTask
from app.models.idempotency_record import IdempotencyRecord
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User
from app.services import planner_approve_service as svc

ITEMS = [{"title": "Thiết kế CSDL", "description": "Chốt bảng", "due_date": "2026-12-01"},
         {"title": "Làm API", "description": None, "due_date": None}]
KEY = "approve-key-0001"


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False)()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def _user(db, name):
    u = User(email=f"{name}@example.com", password_hash="h", display_name=name)
    db.add(u)
    db.flush()
    return u


@pytest.fixture()
def w(db):
    owner, member, viewer, outsider = (_user(db, n) for n in ("owner", "member", "viewer", "outsider"))
    p = Project(name="P", timezone="UTC", created_by=owner.id)
    db.add(p)
    db.flush()
    db.add_all([ProjectMember(project_id=p.id, user_id=owner.id, role="OWNER"),
                ProjectMember(project_id=p.id, user_id=member.id, role="MEMBER"),
                ProjectMember(project_id=p.id, user_id=viewer.id, role="VIEWER")])
    existing = Task(project_id=p.id, title="Task có sẵn", created_by=owner.id)
    draft = AIDraft(project_id=p.id, draft_type="PROJECT_PLAN", status="DRAFT",
                    input_payload={"goal": "Mục tiêu dài đủ mười ký tự", "scope": ""},
                    draft_payload={"items": ITEMS}, version=1, created_by=owner.id)
    db.add_all([existing, draft])
    db.commit()
    return dict(owner=owner, member=member, viewer=viewer, outsider=outsider, p=p, draft=draft)


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def _code(fn, *a, **k):
    with pytest.raises(HTTPException) as e:
        fn(*a, **k)
    return e.value.status_code


def _nothing_created(db):
    assert _count(db, Task) == 1 and _count(db, DraftCreatedTask) == 0
    assert _count(db, IdempotencyRecord) == 0 and _count(db, TaskHistory) == 0


# ---------- thành công ----------
def test_approve_creates_tasks_links_and_marks_approved(db, w):
    r = svc.approve_draft(db, w["owner"], w["draft"].id, 1, KEY)
    assert r["status"] == "APPROVED" and r["version"] == 2 and len(r["task_ids"]) == 2
    assert [t["title"] for t in r["tasks"]] == ["Thiết kế CSDL", "Làm API"]
    assert r["tasks"][0]["due_date"] == "2026-12-01" and r["tasks"][1]["due_date"] is None
    assert all(t["status"] == "TODO" and t["version"] == 1 and t["assignee_id"] is None and t["archived_at"] is None
               for t in r["tasks"])
    assert _count(db, Task) == 3
    new = db.scalars(select(Task).where(Task.id.in_(r["task_ids"]))).all()
    assert all(t.project_id == w["p"].id and t.created_by == w["owner"].id and t.parent_id is None for t in new)
    links = db.scalars(select(DraftCreatedTask).where(DraftCreatedTask.draft_id == w["draft"].id)).all()
    assert sorted(l.task_id for l in links) == sorted(r["task_ids"])
    events = db.scalars(select(TaskHistory).order_by(TaskHistory.event_seq)).all()
    assert [e.event_type for e in events] == ["CREATE", "CREATE"] and all(e.actor_id == w["owner"].id for e in events)
    assert events[0].after_value["title"] == "Thiết kế CSDL" and events[0].before_value is None
    db.refresh(w["draft"])
    assert w["draft"].status == "APPROVED" and w["draft"].version == 2
    assert w["draft"].approved_by == w["owner"].id and w["draft"].approved_at is not None
    rec = db.scalars(select(IdempotencyRecord)).one()
    assert rec.idempotency_key == KEY and rec.completed_at is not None and rec.response_payload["task_ids"] == r["task_ids"]


# ---------- idempotency ----------
def test_same_key_same_payload_replays_without_duplicates(db, w):
    first = svc.approve_draft(db, w["owner"], w["draft"].id, 1, KEY)
    again = svc.approve_draft(db, w["owner"], w["draft"].id, 1, KEY)
    assert again == first
    assert _count(db, Task) == 3 and _count(db, DraftCreatedTask) == 2 and _count(db, TaskHistory) == 2
    assert _count(db, IdempotencyRecord) == 1


def test_same_key_different_payload_is_409(db, w):
    svc.approve_draft(db, w["owner"], w["draft"].id, 1, KEY)
    assert _code(svc.approve_draft, db, w["owner"], w["draft"].id, 2, KEY) == 409      # khác expected_version
    other = AIDraft(project_id=w["p"].id, draft_type="PROJECT_PLAN", status="DRAFT", input_payload={},
                    draft_payload={"items": ITEMS}, version=1, created_by=w["owner"].id)
    db.add(other)
    db.commit()
    assert _code(svc.approve_draft, db, w["owner"], other.id, 1, KEY) == 409           # khác draft
    db.refresh(other)
    assert other.status == "DRAFT" and _count(db, Task) == 3


def test_new_key_on_approved_draft_is_409_not_duplicate(db, w):
    svc.approve_draft(db, w["owner"], w["draft"].id, 1, KEY)
    with pytest.raises(HTTPException) as e:
        svc.approve_draft(db, w["owner"], w["draft"].id, 2, "another-key-0002")
    assert e.value.status_code == 409 and e.value.detail == S.MSG_APPROVED
    assert _count(db, Task) == 3


# ---------- trạng thái và version ----------
def test_stale_version_is_409_and_creates_nothing(db, w):
    assert _code(svc.approve_draft, db, w["owner"], w["draft"].id, 5, KEY) == 409
    _nothing_created(db)
    db.refresh(w["draft"])
    assert w["draft"].status == "DRAFT" and w["draft"].version == 1


@pytest.mark.parametrize("final,msg", [("DISCARDED", S.MSG_DISCARDED), ("APPROVED", S.MSG_APPROVED)])
def test_final_draft_cannot_be_approved(db, w, final, msg):
    w["draft"].status = final
    db.commit()
    with pytest.raises(HTTPException) as e:
        svc.approve_draft(db, w["owner"], w["draft"].id, 1, KEY)
    assert e.value.status_code == 409 and e.value.detail == msg
    _nothing_created(db)


@pytest.mark.parametrize("bad", [[], [{"title": ""}], [{"title": "ok", "due_date": "xx"}], None])
def test_invalid_draft_items_are_422_and_create_nothing(db, w, bad):
    w["draft"].draft_payload = {"items": bad}
    db.commit()
    assert _code(svc.approve_draft, db, w["owner"], w["draft"].id, 1, KEY) == 422
    _nothing_created(db)


# ---------- quyền / phạm vi ----------
@pytest.mark.parametrize("who", ["member", "viewer", "outsider"])
def test_only_owner_can_approve(db, w, who):
    assert _code(svc.approve_draft, db, w[who], w["draft"].id, 1, KEY) == 403
    _nothing_created(db)


def test_archived_project_is_409(db, w):
    w["p"].archived_at = datetime.now(timezone.utc)
    db.commit()
    assert _code(svc.approve_draft, db, w["owner"], w["draft"].id, 1, KEY) == 409
    _nothing_created(db)


def test_missing_or_breakdown_draft_is_404(db, w):
    assert _code(svc.approve_draft, db, w["owner"], 99999, 1, KEY) == 404
    task = db.scalars(select(Task)).first()
    bd = AIDraft(project_id=w["p"].id, parent_task_id=task.id, draft_type="TASK_BREAKDOWN", status="DRAFT",
                 input_payload={}, draft_payload={"items": ITEMS}, version=1, created_by=w["owner"].id)
    db.add(bd)
    db.commit()
    assert _code(svc.approve_draft, db, w["owner"], bd.id, 1, KEY) == 404


# ---------- một transaction: lỗi giữa chừng không để lại gì ----------
def test_failure_midway_rolls_everything_back(db, w, monkeypatch):
    real = svc.add_event
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real(*a, **k)

    monkeypatch.setattr(svc, "add_event", flaky)
    with pytest.raises(RuntimeError):
        svc.approve_draft(db, w["owner"], w["draft"].id, 1, KEY)
    _nothing_created(db)
    db.refresh(w["draft"])
    assert w["draft"].status == "DRAFT" and w["draft"].version == 1 and w["draft"].approved_by is None
    monkeypatch.setattr(svc, "add_event", real)          # thử lại cùng khóa sau lỗi: thành công, không trùng
    assert svc.approve_draft(db, w["owner"], w["draft"].id, 1, KEY)["status"] == "APPROVED"
    assert _count(db, Task) == 3
