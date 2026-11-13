import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.db import Base
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User
from app.services.task_service import get_task, list_tasks
from app.services.subtask_service import set_status
from app.services.project_service import project_to_dict
from app.services.task_update_service import update_task


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


def create_task_tree(db):
    user = User(email="owner@example.com", password_hash="hash", display_name="Owner")
    db.add(user)
    db.flush()

    project = Project(name="Project", timezone="UTC", created_by=user.id)
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role="OWNER"))

    parent = Task(project_id=project.id, title="Parent", created_by=user.id)
    db.add(parent)
    db.flush()
    child = Task(project_id=project.id, parent_id=parent.id, title="Child", created_by=user.id)
    db.add(child)
    db.commit()
    return user, parent, child


def test_status_endpoint_rejects_non_subtask_and_updates_subtask(db):
    user, parent, child = create_task_tree(db)

    with pytest.raises(HTTPException) as error:
        set_status(db, user, parent.id, "DONE", 1)
    assert error.value.status_code == 422

    updated = set_status(db, user, child.id, "DONE", 1)
    assert updated["status"] == "DONE"
    assert updated["version"] == 2
    history = db.query(TaskHistory).one()
    assert history.task_id == child.id
    assert history.event_type == "STATUS_CHANGE"


def test_member_cannot_edit_task_or_change_subtask_status(db):
    owner, parent, child = create_task_tree(db)
    member = User(email="member@example.com", password_hash="hash", display_name="Member")
    db.add(member)
    db.flush()
    db.add(ProjectMember(project_id=parent.project_id, user_id=member.id, role="MEMBER"))
    db.commit()

    with pytest.raises(HTTPException) as edit_error:
        update_task(db, member, parent.id, 1, {"title": "Changed"})
    assert edit_error.value.status_code == 403

    with pytest.raises(HTTPException) as status_error:
        set_status(db, member, child.id, "DONE", 1)
    assert status_error.value.status_code == 403

    db.refresh(parent)
    db.refresh(child)
    assert parent.title == "Parent" and parent.version == 1
    assert child.status == "TODO" and child.version == 1
    assert db.query(TaskHistory).count() == 0


def test_task_read_endpoints_apply_filters_and_allow_viewers(db):
    user, parent, child = create_task_tree(db)

    active_tasks = list_tasks(
        db,
        user,
        parent.project_id,
        status_filter="TODO",
        keyword="child",
        archived=False,
    )
    assert [task["id"] for task in active_tasks] == [child.id]

    viewer = User(email="viewer@example.com", password_hash="hash", display_name="Viewer")
    db.add(viewer)
    db.flush()
    db.add(ProjectMember(project_id=parent.project_id, user_id=viewer.id, role="VIEWER"))
    child.archived_at = datetime.now(timezone.utc)
    db.commit()

    active_tasks = list_tasks(db, viewer, parent.project_id, archived=False)
    assert [task["id"] for task in active_tasks] == [parent.id]
    archived_tasks = list_tasks(db, viewer, parent.project_id, archived=True)
    assert [task["id"] for task in archived_tasks] == [child.id]
    assert get_task(db, viewer, child.id)["id"] == child.id


def test_project_response_contains_contract_role_and_status(db):
    user, parent, _ = create_task_tree(db)
    project = db.get(Project, parent.project_id)

    data = project_to_dict(project, "OWNER")
    assert data["role"] == "OWNER"
    assert data["status"] == "active"
