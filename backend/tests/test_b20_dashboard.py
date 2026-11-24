import os
from datetime import date, datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.db import Base
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User, UserSession
from app.services.dashboard_service import get_dashboard


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(email="viewer@example.test", password_hash="hash", display_name="Viewer")
        session.add(user)
        session.flush()
        project = Project(name="Dashboard", timezone="Asia/Ho_Chi_Minh", created_by=user.id)
        session.add(project)
        session.flush()
        session.add(ProjectMember(project_id=project.id, user_id=user.id, role="VIEWER"))
        session.add_all(
            [
                Task(
                    id=1,
                    project_id=project.id,
                    title="Completed parent",
                    status="DONE",
                    due_date=date(2026, 11, 12),
                    created_by=user.id,
                ),
                Task(
                    id=2,
                    project_id=project.id,
                    title="Overdue parent",
                    status="TODO",
                    due_date=date(2026, 11, 10),
                    created_by=user.id,
                ),
                Task(
                    id=3,
                    project_id=project.id,
                    parent_id=1,
                    title="Subtask",
                    status="TODO",
                    due_date=date(2026, 11, 10),
                    created_by=user.id,
                ),
                Task(
                    id=4,
                    project_id=project.id,
                    title="Archived parent",
                    status="TODO",
                    due_date=date(2026, 11, 8),
                    archived_at=datetime(2026, 11, 10, tzinfo=timezone.utc),
                    created_by=user.id,
                ),
            ]
        )
        session.add_all(
            [
                TaskHistory(
                    task_id=1,
                    project_id=project.id,
                    actor_id=user.id,
                    event_type="CREATE",
                    after_value={
                        "status": "TODO",
                        "due_date": "2026-11-12",
                        "parent_id": None,
                    },
                    occurred_at=datetime(2026, 11, 9, 2, tzinfo=timezone.utc),
                ),
                TaskHistory(
                    task_id=1,
                    project_id=project.id,
                    actor_id=user.id,
                    event_type="STATUS_CHANGE",
                    before_value={"status": "TODO"},
                    after_value={"status": "DONE"},
                    occurred_at=datetime(2026, 11, 11, 4, tzinfo=timezone.utc),
                ),
                TaskHistory(
                    task_id=2,
                    project_id=project.id,
                    actor_id=user.id,
                    event_type="CREATE",
                    after_value={
                        "status": "TODO",
                        "due_date": "2026-11-10",
                        "parent_id": None,
                    },
                    occurred_at=datetime(2026, 11, 9, 3, tzinfo=timezone.utc),
                ),
            ]
        )
        session.commit()
        yield session, user, project
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_dashboard_limits_counts_and_metrics_to_parent_project_tasks(db):
    session, user, project = db

    result = get_dashboard(
        session,
        user,
        project.id,
        now=datetime(2026, 11, 12, 10, tzinfo=timezone.utc),
    )

    assert result["task_counts"] == {
        "TODO": 1,
        "IN_PROGRESS": 0,
        "TESTING_QA": 0,
        "IN_REVIEW": 0,
        "DONE": 1,
        "TOTAL": 2,
    }
    assert result["overdue_tasks"] == 1
    assert result["scope"] == "PARENT_TASKS_ONLY"
    assert result["current_week"]["is_provisional"] is True
    assert result["current_week"]["label"]
    assert result["current_week"]["week_start"] == "2026-11-09"
    assert result["current_week"]["metrics"]["MET-01"] == 1
    assert result["current_week"]["metrics"]["MET-03"] == 1
    assert result["current_week"]["metrics"]["MET-06"] == 100.0


def test_dashboard_requires_project_membership(db):
    session, _, project = db
    outsider = User(id=999, email="outside@example.test", password_hash="hash", display_name="Outside")

    with pytest.raises(HTTPException) as exc:
        get_dashboard(session, outsider, project.id)

    assert exc.value.status_code == 403
