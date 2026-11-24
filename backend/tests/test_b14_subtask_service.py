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
from app.services.subtask_service import delete_subtask, set_status
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


def test_parent_task_status_follows_assignee_qa_review_owner_flow(db):
    owner, parent, _ = create_task_tree(db)
    member = User(email="assigned@example.com", password_hash="hash", display_name="Assigned")
    other = User(email="other@example.com", password_hash="hash", display_name="Other")
    db.add_all([member, other])
    db.flush()
    db.add_all([
        ProjectMember(project_id=parent.project_id, user_id=member.id, role="MEMBER"),
        ProjectMember(project_id=parent.project_id, user_id=other.id, role="MEMBER"),
    ])
    parent.assignee_id = member.id
    db.commit()

    with pytest.raises(HTTPException) as error:
        update_task(db, other, parent.id, 1, {"status": "IN_PROGRESS"})
    assert error.value.status_code == 403

    started = update_task(db, member, parent.id, 1, {"status": "IN_PROGRESS"})
    assert started["status"] == "IN_PROGRESS"
    testing = update_task(db, member, parent.id, 2, {"status": "TESTING_QA"})
    assert testing["status"] == "TESTING_QA"
    review = update_task(db, member, parent.id, 3, {"status": "IN_REVIEW"})
    assert review["status"] == "IN_REVIEW"

    with pytest.raises(HTTPException) as error:
        update_task(db, member, parent.id, 4, {"status": "DONE"})
    assert error.value.status_code == 403

    done = update_task(db, owner, parent.id, 4, {"status": "DONE"})
    assert done["status"] == "DONE"


def test_parent_task_cannot_skip_qa_or_start_without_assignee(db):
    owner, parent, _ = create_task_tree(db)

    with pytest.raises(HTTPException) as error:
        update_task(db, owner, parent.id, 1, {"status": "DONE"})
    assert error.value.status_code == 409

    with pytest.raises(HTTPException) as error:
        update_task(db, owner, parent.id, 1, {"status": "IN_PROGRESS"})
    assert error.value.status_code == 403


def test_in_progress_can_return_to_backlog_for_assignee_or_owner(db):
    owner, parent, _ = create_task_tree(db)
    member = User(email="assigned-backlog@example.com", password_hash="hash", display_name="Assigned")
    other = User(email="other-backlog@example.com", password_hash="hash", display_name="Other")
    db.add_all([member, other])
    db.flush()
    db.add_all([
        ProjectMember(project_id=parent.project_id, user_id=member.id, role="MEMBER"),
        ProjectMember(project_id=parent.project_id, user_id=other.id, role="MEMBER"),
    ])
    parent.assignee_id = member.id
    db.commit()

    update_task(db, member, parent.id, 1, {"status": "IN_PROGRESS"})
    returned = update_task(db, member, parent.id, 2, {"status": "TODO"})
    assert returned["status"] == "TODO"

    update_task(db, member, parent.id, 3, {"status": "IN_PROGRESS"})
    with pytest.raises(HTTPException) as error:
        update_task(db, other, parent.id, 4, {"status": "TODO"})
    assert error.value.status_code == 403

    returned_by_owner = update_task(db, owner, parent.id, 4, {"status": "TODO"})
    assert returned_by_owner["status"] == "TODO"


def test_qa_and_review_can_return_to_backlog_for_assignee(db):
    owner, parent, _ = create_task_tree(db)
    member = User(email="qa-assigned@example.com", password_hash="hash", display_name="Assigned")
    other = User(email="qa-other@example.com", password_hash="hash", display_name="Other")
    db.add_all([member, other])
    db.flush()
    db.add_all([
        ProjectMember(project_id=parent.project_id, user_id=member.id, role="MEMBER"),
        ProjectMember(project_id=parent.project_id, user_id=other.id, role="MEMBER"),
    ])
    parent.assignee_id = member.id
    db.commit()

    update_task(db, member, parent.id, 1, {"status": "IN_PROGRESS"})
    update_task(db, member, parent.id, 2, {"status": "TESTING_QA"})
    with pytest.raises(HTTPException) as error:
        update_task(db, other, parent.id, 3, {"status": "TODO"})
    assert error.value.status_code == 403
    qa_backlog = update_task(db, member, parent.id, 3, {"status": "TODO"})
    assert qa_backlog["status"] == "TODO"

    update_task(db, member, parent.id, 4, {"status": "IN_PROGRESS"})
    update_task(db, member, parent.id, 5, {"status": "TESTING_QA"})
    update_task(db, member, parent.id, 6, {"status": "IN_REVIEW"})
    review_backlog = update_task(db, member, parent.id, 7, {"status": "TODO"})
    assert review_backlog["status"] == "TODO"


def test_delete_subtask_archives_and_rejects_unrelated_task(db):
    owner, parent, child = create_task_tree(db)
    archived = delete_subtask(db, owner, parent.id, child.id)
    assert archived["archived_at"] is not None
    assert db.query(TaskHistory).filter_by(task_id=child.id, event_type="ARCHIVE").count() == 1

    with pytest.raises(HTTPException) as error:
        delete_subtask(db, owner, child.id, parent.id)
    assert error.value.status_code == 404


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
