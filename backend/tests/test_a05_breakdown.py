"""A05: AI Breakdown tạo bản nháp TASK_BREAKDOWN với DB thật (SQLite) và adapter giả."""
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

from app.ai import errors as E
from app.ai.adapter import AIResult
from app.database.db import Base
from app.models.ai_draft import AIDraft
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.task import Task
from app.models.user import User
from app.schemas.breakdown import BreakdownRequest
from app.services import breakdown_service as svc

REQ = BreakdownRequest(objective="Chia task này thành các bước nhỏ dễ làm")
OUT = {"items": [{"title": "Bước 1", "description": "mô tả", "due_date": None}, {"title": "Bước 2"}]}


class FakeAdapter:
    def __init__(self, error=None, before_return=None):
        self.calls, self.error, self.before_return = [], error, before_return

    def complete_json(self, feature, system, user, schema, **kw):
        self.calls.append((feature, system, user, schema, kw))
        if self.error:
            raise self.error
        if self.before_return:
            self.before_return()
        return AIResult(data=schema.model_validate(OUT), request_id="req-1", feature=feature, latency_ms=5, attempts=1)


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
    parent = Task(project_id=p.id, title="Task cha", description="Mô tả task cha", created_by=owner.id)
    db.add(parent)
    db.flush()
    child = Task(project_id=p.id, parent_id=parent.id, title="Subtask", created_by=owner.id)
    db.add(child)
    db.commit()
    return dict(owner=owner, member=member, viewer=viewer, outsider=outsider, p=p, parent=parent, child=child)


@pytest.fixture()
def fake(monkeypatch):
    f = FakeAdapter()
    monkeypatch.setattr(svc, "get_ai_adapter", lambda: f)
    return f


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def _code(fn, *a, **k):
    with pytest.raises(HTTPException) as e:
        fn(*a, **k)
    return e.value.status_code


@pytest.mark.parametrize("who", ["owner", "member"])
def test_owner_and_member_get_draft_without_creating_subtasks(db, w, fake, who):
    r = svc.create_breakdown_draft(db, w[who], w["parent"].id, REQ)
    assert r["type"] == "TASK_BREAKDOWN" and r["status"] == "DRAFT" and r["version"] == 1
    assert r["parent_task_id"] == w["parent"].id and r["project_id"] == w["p"].id
    assert r["subtasks"] == [{"title": "Bước 1", "description": "mô tả", "due_date": None},
                             {"title": "Bước 2", "description": None, "due_date": None}]
    assert r["request_id"] == "req-1" and r["is_mock"] is False
    d = db.get(AIDraft, r["draft_id"])
    assert d.draft_type == "TASK_BREAKDOWN" and d.status == "DRAFT" and d.created_by == w[who].id
    assert d.parent_task_id == w["parent"].id and d.input_payload == {"objective": REQ.objective}
    assert d.draft_payload == {"items": r["subtasks"]}
    assert _count(db, Task) == 2                      # chỉ còn task cha + subtask cũ: không tạo subtask mới


def test_adapter_is_called_for_breakdown_with_task_context(db, w, fake):
    svc.create_breakdown_draft(db, w["owner"], w["parent"].id, REQ)
    feature, system, user, schema, kw = fake.calls[0]
    assert feature == "BREAKDOWN" and "Task cha" in user and REQ.objective in user
    assert kw.get("mock_payload") is not None


def test_long_description_is_truncated_in_prompt(db, w, fake):
    w["parent"].description = "x" * 5000
    db.commit()
    svc.create_breakdown_draft(db, w["owner"], w["parent"].id, REQ)
    assert len(fake.calls[0][2]) < 4000                # không vượt giới hạn độ dài prompt của adapter


@pytest.mark.parametrize("who", ["viewer", "outsider"])
def test_viewer_and_outsider_rejected(db, w, fake, who):
    assert _code(svc.create_breakdown_draft, db, w[who], w["parent"].id, REQ) == 403
    assert fake.calls == [] and _count(db, AIDraft) == 0


def test_subtask_parent_is_422(db, w, fake):
    assert _code(svc.create_breakdown_draft, db, w["owner"], w["child"].id, REQ) == 422
    assert fake.calls == [] and _count(db, AIDraft) == 0


def test_archived_task_and_archived_project_are_409(db, w, fake):
    w["parent"].archived_at = datetime.now(timezone.utc)
    db.commit()
    assert _code(svc.create_breakdown_draft, db, w["owner"], w["parent"].id, REQ) == 409
    w["parent"].archived_at = None
    w["p"].archived_at = datetime.now(timezone.utc)
    db.commit()
    assert _code(svc.create_breakdown_draft, db, w["owner"], w["parent"].id, REQ) == 409
    assert fake.calls == [] and _count(db, AIDraft) == 0


def test_missing_task_is_404(db, w, fake):
    assert _code(svc.create_breakdown_draft, db, w["owner"], 99999, REQ) == 404


@pytest.mark.parametrize("err,code", [(E.timeout(), 504), (E.rate_limited(), 429), (E.unavailable(), 503),
                                      (E.bad_response(), 502), (E.not_configured(), 503)])
def test_ai_errors_become_controlled_http_errors_and_save_nothing(db, w, monkeypatch, err, code):
    monkeypatch.setattr(svc, "get_ai_adapter", lambda: FakeAdapter(error=err))
    assert _code(svc.create_breakdown_draft, db, w["owner"], w["parent"].id, REQ) == code
    assert _count(db, AIDraft) == 0 and _count(db, Task) == 2


def test_task_archived_while_ai_is_running_is_rechecked(db, w, monkeypatch):
    def archive():
        w["parent"].archived_at = datetime.now(timezone.utc)
        db.commit()
    monkeypatch.setattr(svc, "get_ai_adapter", lambda: FakeAdapter(before_return=archive))
    assert _code(svc.create_breakdown_draft, db, w["owner"], w["parent"].id, REQ) == 409
    assert _count(db, AIDraft) == 0
