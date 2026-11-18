"""M01: tái dựng trạng thái cuối tuần từ TaskHistory."""
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.weekly_period import week_bounds
from app.database.db import Base
from app.models.project import Project
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User
from app.services.task_reconstruction_service import reconstruct_project_tasks


def test_week_bounds_uses_project_timezone_and_exclusive_next_monday():
    start, end = week_bounds(
        date(2026, 11, 9),
        "Asia/Ho_Chi_Minh",
        datetime(2026, 11, 17, tzinfo=timezone.utc),
    )
    assert start == datetime(2026, 11, 8, 17, tzinfo=timezone.utc)
    assert end == datetime(2026, 11, 15, 17, tzinfo=timezone.utc)


def test_week_bounds_accounts_for_timezone_offset_changes():
    start, end = week_bounds(
        date(2026, 3, 2),
        "America/New_York",
        datetime(2026, 3, 10, tzinfo=timezone.utc),
    )
    assert start == datetime(2026, 3, 2, 5, tzinfo=timezone.utc)
    assert end == datetime(2026, 3, 9, 4, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "week_start,timezone_name,now",
    [
        (date(2026, 11, 10), "UTC", datetime(2026, 11, 20, tzinfo=timezone.utc)),
        (date(2026, 11, 9), "Not/AZone", datetime(2026, 11, 20, tzinfo=timezone.utc)),
        (date(2026, 11, 9), "UTC", datetime(2026, 11, 10, tzinfo=timezone.utc)),
    ],
)
def test_week_bounds_rejects_invalid_or_incomplete_week(week_start, timezone_name, now):
    with pytest.raises(ValueError):
        week_bounds(week_start, timezone_name, now)


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


def _event(db, task, actor_id, kind, occurred_at, before, after):
    db.add(TaskHistory(
        task_id=task.id,
        project_id=task.project_id,
        actor_id=actor_id,
        event_type=kind,
        occurred_at=occurred_at,
        before_value=before,
        after_value=after,
    ))


def test_reconstruction_uses_history_and_excludes_events_at_end(db):
    actor = User(email="owner@example.com", password_hash="h", display_name="Owner")
    db.add(actor)
    db.flush()
    project = Project(name="Project", timezone="Asia/Ho_Chi_Minh", created_by=actor.id)
    db.add(project)
    db.flush()
    before_week = Task(
        project_id=project.id,
        title="Before week",
        status="DONE",
        created_by=actor.id,
    )
    during_week = Task(
        project_id=project.id,
        title="During week",
        status="DONE",
        due_date=date(2026, 11, 12),
        created_by=actor.id,
    )
    at_end = Task(project_id=project.id, title="At end", created_by=actor.id)
    db.add_all([before_week, during_week, at_end])
    db.flush()

    snapshot = {
        "title": "Before week",
        "description": None,
        "status": "TODO",
        "due_date": None,
        "assignee_id": None,
        "parent_id": None,
    }
    _event(db, before_week, actor.id, "CREATE", datetime(2026, 11, 1, tzinfo=timezone.utc),
           None, snapshot)
    _event(db, before_week, actor.id, "STATUS_CHANGE", datetime(2026, 11, 8, 17, tzinfo=timezone.utc),
           {"status": "TODO"}, {"status": "IN_PROGRESS"})
    _event(db, before_week, actor.id, "STATUS_CHANGE", datetime(2026, 11, 15, 17, tzinfo=timezone.utc),
           {"status": "IN_PROGRESS"}, {"status": "DONE"})

    during_snapshot = {**snapshot, "title": "During week"}
    _event(db, during_week, actor.id, "CREATE", datetime(2026, 11, 10, tzinfo=timezone.utc),
           None, during_snapshot)
    _event(db, during_week, actor.id, "DUE_CHANGE", datetime(2026, 11, 11, tzinfo=timezone.utc),
           {"due_date": None}, {"due_date": "2026-11-12"})
    _event(db, during_week, actor.id, "ARCHIVE", datetime(2026, 11, 12, tzinfo=timezone.utc),
           {"archived_at": None}, {"archived_at": "2026-11-12T00:00:00Z"})
    _event(db, during_week, actor.id, "RESTORE", datetime(2026, 11, 13, tzinfo=timezone.utc),
           {"archived_at": "2026-11-12T00:00:00Z"}, {"archived_at": None})

    end_snapshot = {**snapshot, "title": "At end"}
    _event(db, at_end, actor.id, "CREATE", datetime(2026, 11, 15, 17, tzinfo=timezone.utc),
           None, end_snapshot)
    db.commit()

    # Current ORM values intentionally disagree with the historical state.
    before_week.status = "DONE"
    db.commit()
    result = reconstruct_project_tasks(
        db,
        project.id,
        date(2026, 11, 9),
        datetime(2026, 11, 17, tzinfo=timezone.utc),
    )

    assert result["start_at"] == "2026-11-08T17:00:00Z"
    assert result["end_at"] == "2026-11-15T17:00:00Z"
    assert result["states"][before_week.id]["status"] == "IN_PROGRESS"
    assert result["states"][during_week.id]["due_date"] == "2026-11-12"
    assert result["states"][during_week.id]["archived_at"] is None
    assert at_end.id not in result["states"]
    assert result["warnings"] == []


def test_reconstruction_rejects_missing_project(db):
    with pytest.raises(HTTPException) as error:
        reconstruct_project_tasks(
            db, 999, date(2026, 11, 9), datetime(2026, 11, 20, tzinfo=timezone.utc)
        )
    assert error.value.status_code == 404
