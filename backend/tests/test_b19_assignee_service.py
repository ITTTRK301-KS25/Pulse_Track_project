"""B19: validate_assignee với DB thật (SQLite trong bộ nhớ) và qua create_task / update_task / create_subtask."""
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.assignee_rules import ASSIGNEE_MSG
from app.database.db import Base
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.task_history import TaskHistory
from app.models.user import User
from app.services.assignee_service import validate_assignee
from app.services.member_manage_service import remove_member
from app.services.subtask_service import create_subtask
from app.services.task_service import create_task
from app.services.task_update_service import update_task


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
def world(db):
    owner, member, viewer, outsider = (_user(db, n) for n in ("owner", "member", "viewer", "outsider"))
    p = Project(name="P1", timezone="UTC", created_by=owner.id)
    other = Project(name="P2", timezone="UTC", created_by=outsider.id)
    db.add_all([p, other])
    db.flush()
    db.add_all([
        ProjectMember(project_id=p.id, user_id=owner.id, role="OWNER"),
        ProjectMember(project_id=p.id, user_id=member.id, role="MEMBER"),
        ProjectMember(project_id=p.id, user_id=viewer.id, role="VIEWER"),
        ProjectMember(project_id=other.id, user_id=outsider.id, role="OWNER"),
    ])
    db.commit()
    return dict(owner=owner, member=member, viewer=viewer, outsider=outsider, p=p, other=other)


def _bad(db, pid, uid):
    with pytest.raises(HTTPException) as e:
        validate_assignee(db, pid, uid)
    assert e.value.status_code == 422
    assert e.value.detail == ASSIGNEE_MSG


def test_valid_none_owner_member(db, world):
    pid = world["p"].id
    validate_assignee(db, pid, None)
    validate_assignee(db, pid, world["owner"].id)
    validate_assignee(db, pid, world["member"].id)


def test_viewer_outsider_nonexistent_rejected(db, world):
    pid = world["p"].id
    _bad(db, pid, world["viewer"].id)
    _bad(db, pid, world["outsider"].id)      # là user thật nhưng thuộc dự án khác
    _bad(db, pid, 999999)                    # không tồn tại


def test_ex_member_rejected_after_removal(db, world):
    pid = world["p"].id
    validate_assignee(db, pid, world["member"].id)
    remove_member(db, world["owner"], pid, world["member"].id)
    _bad(db, pid, world["member"].id)


def test_create_task_uses_validator_and_writes_nothing_on_error(db, world):
    pid = world["p"].id
    with pytest.raises(HTTPException) as e:
        create_task(db, world["owner"], pid, "T", None, None, world["viewer"].id)
    assert e.value.status_code == 422
    assert db.query(TaskHistory).count() == 0
    ok = create_task(db, world["owner"], pid, "T", None, None, world["member"].id)
    assert ok["assignee_id"] == world["member"].id


def test_update_task_validates_only_on_change(db, world):
    pid = world["p"].id
    t = create_task(db, world["owner"], pid, "T", None, None, world["member"].id)
    # đổi sang VIEWER -> 422, không tăng version, không sinh event mới
    with pytest.raises(HTTPException) as e:
        update_task(db, world["owner"], t["id"], 1, {"assignee_id": world["viewer"].id})
    assert e.value.status_code == 422
    assert db.query(TaskHistory).count() == 1
    # người được giao bị xóa khỏi dự án, sửa tiêu đề (không đổi assignee) vẫn OK
    remove_member(db, world["owner"], pid, world["member"].id)
    r = update_task(db, world["owner"], t["id"], 1, {"title": "T2"})
    assert r["title"] == "T2" and r["version"] == 2
    # bỏ giao (None) luôn hợp lệ
    r = update_task(db, world["owner"], t["id"], 2, {"assignee_id": None})
    assert r["assignee_id"] is None


def test_create_subtask_uses_validator(db, world):
    pid = world["p"].id
    t = create_task(db, world["owner"], pid, "T", None, None, None)
    with pytest.raises(HTTPException) as e:
        create_subtask(db, world["owner"], t["id"], "S", None, None, world["outsider"].id)
    assert e.value.status_code == 422
    s = create_subtask(db, world["owner"], t["id"], "S", None, None, world["owner"].id)
    assert s["assignee_id"] == world["owner"].id
