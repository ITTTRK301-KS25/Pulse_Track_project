"""M02–M05: calculate_weekly_metrics với DB thật (SQLite trong bộ nhớ)."""
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

from app.database.db import Base
from app.models.project import Project
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User
from app.services.metrics_service import calculate_weekly_metrics

NOW = datetime(2026, 11, 30, tzinfo=timezone.utc)
WEEK = date(2026, 10, 19)                       # giờ VN: 2026-10-18T17:00Z .. 2026-10-25T17:00Z


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


def snap(**kw):
    return {"title": "T", "description": None, "status": "TODO", "due_date": None, "assignee_id": None,
            "parent_id": None, **kw}


def add(db, task, actor, etype, when, before, after):
    db.add(TaskHistory(task_id=task.id, project_id=task.project_id, actor_id=actor, event_type=etype,
                       occurred_at=when, before_value=before, after_value=after))


@pytest.fixture()
def world(db):
    owner = User(email="o@example.com", password_hash="h", display_name="O")
    db.add(owner)
    db.flush()
    p = Project(name="P", timezone="Asia/Ho_Chi_Minh", created_by=owner.id)
    db.add(p)
    db.flush()
    return owner, p


def test_metrics_come_from_history_not_current_task_rows(db, world):
    owner, p = world
    t1 = Task(project_id=p.id, title="A", status="TODO", created_by=owner.id)     # bảng tasks nói TODO...
    t2 = Task(project_id=p.id, title="B", status="DONE", created_by=owner.id)     # ...và DONE, nhưng lịch sử mới là sự thật
    db.add_all([t1, t2])
    db.flush()
    long_ago = datetime(2026, 10, 1, tzinfo=timezone.utc)
    add(db, t1, owner.id, "CREATE", long_ago, None, snap(due_date="2026-10-30"))
    add(db, t1, owner.id, "STATUS_CHANGE", datetime(2026, 10, 20, 3, tzinfo=timezone.utc),
        {"status": "TODO"}, {"status": "DONE"})
    add(db, t2, owner.id, "CREATE", long_ago, None, snap(due_date="2026-10-22"))
    db.commit()
    r = calculate_weekly_metrics(db, p.id, WEEK, NOW)
    assert r["metrics"] == {"MET-01": 1, "MET-02": 1, "MET-03": 1, "MET-04": 1, "MET-05": 1, "MET-06": 100.0}
    assert r["details"]["MET-01"] == [t1.id] and r["details"]["MET-02"] == [t2.id]
    assert r["start_at"] == "2026-10-18T17:00:00Z" and r["end_at"] == "2026-10-25T17:00:00Z"
    assert r["warnings"] == [] and r["complete"] is True


def test_events_at_or_after_end_are_ignored(db, world):
    owner, p = world
    t = Task(project_id=p.id, title="A", created_by=owner.id)
    db.add(t)
    db.flush()
    add(db, t, owner.id, "CREATE", datetime(2026, 10, 1, tzinfo=timezone.utc), None, snap())
    add(db, t, owner.id, "STATUS_CHANGE", datetime(2026, 10, 25, 17, tzinfo=timezone.utc),
        {"status": "TODO"}, {"status": "DONE"})
    db.commit()
    r = calculate_weekly_metrics(db, p.id, WEEK, NOW)
    assert (r["metrics"]["MET-01"], r["metrics"]["MET-02"]) == (0, 1)


def test_missing_project_404(db):
    with pytest.raises(HTTPException) as e:
        calculate_weekly_metrics(db, 999, WEEK, NOW)
    assert e.value.status_code == 404


@pytest.mark.parametrize("week,now", [
    (date(2026, 10, 20), NOW),                                          # không phải thứ Hai
    (date(2026, 11, 23), datetime(2026, 11, 25, tzinfo=timezone.utc)),  # tuần chưa kết thúc
])
def test_invalid_or_unfinished_week_422(db, world, week, now):
    _, p = world
    with pytest.raises(HTTPException) as e:
        calculate_weekly_metrics(db, p.id, week, now)
    assert e.value.status_code == 422


def test_other_projects_history_not_mixed_in(db, world):
    owner, p = world
    p2 = Project(name="Q", timezone="Asia/Ho_Chi_Minh", created_by=owner.id)
    db.add(p2)
    db.flush()
    t = Task(project_id=p2.id, title="X", created_by=owner.id)
    db.add(t)
    db.flush()
    add(db, t, owner.id, "CREATE", datetime(2026, 10, 1, tzinfo=timezone.utc), None, snap())
    db.commit()
    assert calculate_weekly_metrics(db, p.id, WEEK, NOW)["metrics"]["MET-02"] == 0
