"""A06: sửa, hủy và duyệt AI Breakdown Draft."""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.database.db import Base
from app.models.ai_draft import AIDraft
from app.models.draft_created_task import DraftCreatedTask
from app.models.idempotency_record import IdempotencyRecord
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User
from app.services import breakdown_draft_service as svc


ITEMS = [
    {"title": "Bước một", "description": "Làm phần đầu", "due_date": "2026-11-20"},
    {"title": "Bước hai", "description": None, "due_date": None},
]
KEY = "breakdown-key-01"


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _user(db, name):
    user = User(email=f"{name}@example.com", password_hash="h", display_name=name)
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def workspace(db):
    owner, member, viewer = (_user(db, name) for name in ("owner", "member", "viewer"))
    project = Project(name="Project", timezone="UTC", created_by=owner.id)
    db.add(project)
    db.flush()
    db.add_all([
        ProjectMember(project_id=project.id, user_id=owner.id, role="OWNER"),
        ProjectMember(project_id=project.id, user_id=member.id, role="MEMBER"),
        ProjectMember(project_id=project.id, user_id=viewer.id, role="VIEWER"),
    ])
    parent = Task(project_id=project.id, title="Task cha", created_by=owner.id)
    db.add(parent)
    db.flush()
    draft = AIDraft(
        project_id=project.id,
        parent_task_id=parent.id,
        draft_type="TASK_BREAKDOWN",
        status="DRAFT",
        input_payload={"objective": "Chia nhỏ công việc"},
        draft_payload={"items": ITEMS},
        version=1,
        created_by=owner.id,
    )
    db.add(draft)
    db.commit()
    return {
        "owner": owner,
        "member": member,
        "viewer": viewer,
        "project": project,
        "parent": parent,
        "draft": draft,
    }


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def _code(fn, *args, **kwargs):
    with pytest.raises(HTTPException) as error:
        fn(*args, **kwargs)
    return error.value.status_code


def test_member_can_edit_draft_but_does_not_create_tasks(db, workspace):
    edited = [{"title": "Bước đã sửa", "description": None, "due_date": None}]
    result = svc.update_draft(db, workspace["member"], workspace["draft"].id, edited, 1)

    assert result["status"] == "DRAFT" and result["version"] == 2
    assert result["subtasks"] == edited
    assert _count(db, Task) == 1
    assert _count(db, TaskHistory) == 0


def test_draft_edit_rejects_viewer_and_stale_version(db, workspace):
    assert _code(
        svc.update_draft, db, workspace["viewer"], workspace["draft"].id, ITEMS, 1
    ) == 403
    assert _code(
        svc.update_draft, db, workspace["member"], workspace["draft"].id, ITEMS, 2
    ) == 409
    assert _count(db, Task) == 1


@pytest.mark.parametrize("role", ["owner", "member"])
def test_approve_creates_one_level_subtasks_and_create_history(db, workspace, role):
    result = svc.approve_draft(
        db, workspace[role], workspace["draft"].id, 1, KEY
    )

    assert result["status"] == "APPROVED" and result["version"] == 2
    assert len(result["subtasks"]) == 2
    assert all(item["parent_id"] == workspace["parent"].id for item in result["subtasks"])
    assert all(item["status"] == "TODO" for item in result["subtasks"])
    assert _count(db, Task) == 3
    assert _count(db, DraftCreatedTask) == 2
    assert _count(db, TaskHistory) == 2
    assert _count(db, IdempotencyRecord) == 1


def test_approve_retry_replays_and_changed_payload_conflicts(db, workspace):
    first = svc.approve_draft(db, workspace["owner"], workspace["draft"].id, 1, KEY)
    assert svc.approve_draft(db, workspace["owner"], workspace["draft"].id, 1, KEY) == first
    assert _count(db, Task) == 3

    assert _code(
        svc.approve_draft, db, workspace["owner"], workspace["draft"].id, 2, KEY
    ) == 409
    assert _count(db, Task) == 3


def test_discarded_or_archived_parent_cannot_be_approved(db, workspace):
    svc.discard_draft(db, workspace["member"], workspace["draft"].id)
    assert _code(
        svc.approve_draft, db, workspace["owner"], workspace["draft"].id, 2, KEY
    ) == 409
    assert _count(db, Task) == 1

    workspace["draft"].status = "DRAFT"
    workspace["draft"].version = 3
    workspace["parent"].archived_at = datetime.now(timezone.utc)
    db.commit()
    assert _code(
        svc.approve_draft, db, workspace["owner"], workspace["draft"].id, 3, "new-key-0002"
    ) == 409
    assert _count(db, Task) == 1


def test_failure_during_approval_rolls_back_everything(db, workspace, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("history write failed")

    monkeypatch.setattr(svc, "add_event", fail)
    with pytest.raises(RuntimeError):
        svc.approve_draft(db, workspace["owner"], workspace["draft"].id, 1, KEY)

    assert _count(db, Task) == 1
    assert _count(db, DraftCreatedTask) == 0
    assert _count(db, TaskHistory) == 0
    assert _count(db, IdempotencyRecord) == 0
    db.refresh(workspace["draft"])
    assert workspace["draft"].status == "DRAFT"
