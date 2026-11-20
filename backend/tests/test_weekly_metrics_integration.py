
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.weekly_metrics_service import (
    calculate_weekly_metrics,
)


PROJECT_ID = 2
WEEK_START = date(2026, 11, 9)
NOW = datetime(2026, 11, 20, tzinfo=timezone.utc)


def make_event(task_id, seq, kind, when, after, before=None):
    return SimpleNamespace(
        task_id=task_id,
        project_id=PROJECT_ID,
        event_seq=seq,
        event_type=kind,
        occurred_at=datetime.fromisoformat(when),
        after_value=after,
        before_value=before,
    )


def make_task(task_id, due_date, changes=None):
    events = [
        make_event(
            task_id,
            1,
            "CREATE",
            "2026-11-09T08:00:00+07:00",
            {
                "title": f"Task {task_id}",
                "description": "",
                "status": "TODO",
                "due_date": due_date,
                "assignee_id": None,
                "parent_id": None,
            },
        )
    ]

    for index, change in enumerate(changes or [], start=2):
        when, before, after = change

        events.append(
            make_event(
                task_id,
                index,
                "STATUS_CHANGE",
                when,
                {"status": after},
                {"status": before},
            )
        )

    return events


def make_db(events):
    db = MagicMock()

    project = SimpleNamespace(
        id=PROJECT_ID,
        timezone="Asia/Ho_Chi_Minh",
    )

    db.get.return_value = project
    db.scalars.return_value.all.return_value = events

    return db


def sample_history():
    events = []

    # A: Hoan thanh dung han.
    events += make_task(
        1,
        "2026-11-11",
        [
            (
                "2026-11-11T10:00:00+07:00",
                "TODO",
                "DONE",
            )
        ],
    )

    # B: Hoan thanh tre, han truoc tuan.
    events += make_task(
        2,
        "2026-11-08",
        [
            (
                "2026-11-12T10:00:00+07:00",
                "TODO",
                "DONE",
            )
        ],
    )

    # C: Hoan thanh dung han.
    events += make_task(
        3,
        "2026-11-14",
        [
            (
                "2026-11-13T10:00:00+07:00",
                "TODO",
                "DONE",
            )
        ],
    )

    # D: Dang mo, qua han.
    events += make_task(4, "2026-11-07")

    # E: Dang mo, qua han.
    events += make_task(5, "2026-11-10")

    # F: Dang mo, han Chu nhat.
    events += make_task(6, "2026-11-15")

    return events


def test_all_six_metrics():
    db = make_db(sample_history())

    result = calculate_weekly_metrics(
        db=db,
        project_id=PROJECT_ID,
        week_start=WEEK_START,
        now=NOW,
    )

    metrics = result["metrics"]

    assert metrics["MET-01"] == 3
    assert metrics["MET-02"] == 3
    assert metrics["MET-03"] == 2
    assert metrics["MET-04"] == 4
    assert metrics["MET-05"] == 2
    assert metrics["MET-06"] == pytest.approx(66.67)

    assert result["project_id"] == PROJECT_ID
    assert result["week_start"] == "2026-11-09"


def test_empty_week():
    db = make_db([])

    result = calculate_weekly_metrics(
        db=db,
        project_id=PROJECT_ID,
        week_start=WEEK_START,
        now=NOW,
    )

    metrics = result["metrics"]

    assert metrics["MET-01"] == 0
    assert metrics["MET-02"] == 0
    assert metrics["MET-03"] == 0
    assert metrics["MET-04"] == 0
    assert metrics["MET-05"] == 0
    assert metrics["MET-06"] == 0


def test_reopen_then_complete_late():
    events = make_task(
        1,
        "2026-11-12",
        [
            (
                "2026-11-12T09:00:00+07:00",
                "TODO",
                "DONE",
            ),
            (
                "2026-11-12T11:00:00+07:00",
                "DONE",
                "IN_PROGRESS",
            ),
            (
                "2026-11-14T09:00:00+07:00",
                "IN_PROGRESS",
                "DONE",
            ),
        ],
    )

    db = make_db(events)

    result = calculate_weekly_metrics(
        db=db,
        project_id=PROJECT_ID,
        week_start=WEEK_START,
        now=NOW,
    )

    metrics = result["metrics"]

    assert metrics["MET-01"] == 1
    assert metrics["MET-05"] == 0
    assert metrics["MET-06"] == 0


def test_sunday_due_not_overdue():
    events = make_task(
        1,
        "2026-11-15",
    )

    db = make_db(events)

    result = calculate_weekly_metrics(
        db=db,
        project_id=PROJECT_ID,
        week_start=WEEK_START,
        now=NOW,
    )

    metrics = result["metrics"]

    assert metrics["MET-02"] == 1
    assert metrics["MET-03"] == 0
    assert metrics["MET-04"] == 1


def test_missing_project():
    db = make_db([])
    db.get.return_value = None

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        calculate_weekly_metrics(
            db=db,
            project_id=999,
            week_start=WEEK_START,
            now=NOW,
        )

    assert exc.value.status_code == 404
