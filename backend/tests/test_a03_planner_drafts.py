"""A03: sửa/hủy bản nháp AI Planner với DB thật (SQLite trong bộ nhớ)."""
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

from app.core import ai_draft_state as rules
from app.database.db import Base
from app.models.ai_draft import AIDraft
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.task import Task
from app.models.user import User
from app.services import planner_draft_service as svc

OLD = [{"title": "Gợi ý cũ", "description": None, "due_date": None}]
NEW = [{"title": "Gợi ý mới 1", "description": "mô tả", "due_date": "2026-12-31"},
       {"title": "Gợi ý mới 2", "description": None, "due_date": None}]


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
    task = Task(project_id=p.id, title="Task có sẵn", created_by=owner.id)
    draft = AIDraft(project_id=p.id, draft_type="PROJECT_PLAN", status="DRAFT",
                    input_payload={"goal": "Mục tiêu dài đủ mười ký tự", "scope": ""},
                    draft_payload={"items": OLD}, version=1, created_by=owner.id)
    db.add_all([task, draft])
    db.commit()
    return dict(owner=owner, member=member, viewer=viewer, outsider=outsider, p=p, task=task, draft=draft)


def _tasks(db):
    return [(t.id, t.title, t.status, t.version, t.archived_at) for t in db.scalars(select(Task).order_by(Task.id))]


def _code(fn, *a, **k):
    with pytest.raises(HTTPException) as e:
        fn(*a, **k)
    return e.value.status_code


# ---------- sửa ----------
def test_owner_updates_draft_content(db, w):
    before = _tasks(db)
    r = svc.update_draft(db, w["owner"], w["draft"].id, NEW)
    assert r["status"] == "DRAFT" and r["version"] == 2 and r["suggestions"] == NEW
    db.refresh(w["draft"])
    assert w["draft"].draft_payload == {"items": NEW}
    assert w["draft"].input_payload["goal"].startswith("Mục tiêu")     # đầu vào ban đầu giữ nguyên
    assert _tasks(db) == before                                        # không tạo/đổi Task


@pytest.mark.parametrize("who", ["member", "viewer", "outsider"])
def test_only_owner_can_update_and_discard(db, w, who):
    assert _code(svc.update_draft, db, w[who], w["draft"].id, NEW) == 403
    assert _code(svc.discard_draft, db, w[who], w["draft"].id) == 403
    db.refresh(w["draft"])
    assert w["draft"].status == "DRAFT" and w["draft"].version == 1 and w["draft"].draft_payload == {"items": OLD}


def test_missing_or_non_planner_draft_is_404(db, w):
    assert _code(svc.update_draft, db, w["owner"], 99999, NEW) == 404
    assert _code(svc.discard_draft, db, w["owner"], 99999) == 404
    other = AIDraft(project_id=w["p"].id, draft_type="TASK_BREAKDOWN", status="DRAFT", parent_task_id=w["task"].id,
                    input_payload={}, draft_payload={"items": OLD}, version=1, created_by=w["owner"].id)
    db.add(other)
    db.commit()
    assert _code(svc.update_draft, db, w["owner"], other.id, NEW) == 404
    assert _code(svc.discard_draft, db, w["owner"], other.id) == 404


def test_version_check(db, w):
    assert _code(svc.update_draft, db, w["owner"], w["draft"].id, NEW, 5) == 409
    db.refresh(w["draft"])
    assert w["draft"].version == 1 and w["draft"].draft_payload == {"items": OLD}
    assert svc.update_draft(db, w["owner"], w["draft"].id, NEW, 1)["version"] == 2
    assert _code(svc.update_draft, db, w["owner"], w["draft"].id, OLD, 1) == 409   # version 1 đã cũ


def test_identical_content_does_not_bump_version(db, w):
    r = svc.update_draft(db, w["owner"], w["draft"].id, OLD)
    assert r["version"] == 1
    db.refresh(w["draft"])
    assert w["draft"].version == 1


# ---------- hủy ----------
def test_discard_marks_discarded_and_never_touches_tasks(db, w):
    before = _tasks(db)
    r = svc.discard_draft(db, w["owner"], w["draft"].id)
    assert r["status"] == "DISCARDED" and r["version"] == 2
    db.refresh(w["draft"])
    assert w["draft"].status == "DISCARDED"
    assert _tasks(db) == before
    assert db.scalar(select(func.count()).select_from(Task)) == 1


# ---------- trạng thái cuối không sửa / hủy / duyệt lại ----------
@pytest.mark.parametrize("final,msg", [("DISCARDED", rules.MSG_DISCARDED), ("APPROVED", rules.MSG_APPROVED)])
def test_final_states_are_read_only(db, w, final, msg):
    w["draft"].status = final
    db.commit()
    for call in (lambda: svc.update_draft(db, w["owner"], w["draft"].id, NEW),
                 lambda: svc.discard_draft(db, w["owner"], w["draft"].id)):
        with pytest.raises(HTTPException) as e:
            call()
        assert e.value.status_code == 409 and e.value.detail == msg
    db.refresh(w["draft"])
    assert w["draft"].status == final and w["draft"].version == 1 and w["draft"].draft_payload == {"items": OLD}


def test_discard_twice_second_is_409(db, w):
    svc.discard_draft(db, w["owner"], w["draft"].id)
    assert _code(svc.discard_draft, db, w["owner"], w["draft"].id) == 409


# ---------- dự án đã lưu trữ ----------
def test_archived_project_blocks_update_and_discard(db, w):
    w["p"].archived_at = datetime.now(timezone.utc)
    db.commit()
    assert _code(svc.update_draft, db, w["owner"], w["draft"].id, NEW) == 409
    assert _code(svc.discard_draft, db, w["owner"], w["draft"].id) == 409
    db.refresh(w["draft"])
    assert w["draft"].status == "DRAFT" and w["draft"].version == 1


# ---------- dữ liệu trả về ----------
def test_response_shape(db, w):
    r = svc.update_draft(db, w["owner"], w["draft"].id, NEW)
    assert set(r) == {"draft_id", "project_id", "type", "status", "version", "suggestions", "updated_at"}
    assert r["draft_id"] == w["draft"].id and r["project_id"] == w["p"].id and r["type"] == "PROJECT_PLAN"
