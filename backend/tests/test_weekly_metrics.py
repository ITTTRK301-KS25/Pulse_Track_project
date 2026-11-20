
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.history_rules import replay
from app.core.weekly_period import week_bounds
from app.services.weekly_metrics_service import (
    _due_date,
    _last_completion_in_week,
)


UTC = timezone.utc
TZ = ZoneInfo("Asia/Ho_Chi_Minh")

START = datetime(2026, 11, 9, 0, 0, tzinfo=TZ).astimezone(UTC)
END = datetime(2026, 11, 16, 0, 0, tzinfo=TZ).astimezone(UTC)


def event(seq, kind, when, after, before=None):
    return {
        "event_seq": seq,
        "event_type": kind,
        "occurred_at": datetime.fromisoformat(when),
        "before_value": before,
        "after_value": after,
    }


def create_task(due="2026-11-12"):
    return event(
        1,
        "CREATE",
        "2026-11-09T08:00:00+07:00",
        {
            "title": "Test Task",
            "description": "",
            "status": "TODO",
            "due_date": due,
            "assignee_id": None,
            "parent_id": None,
        },
    )


def status_event(seq, when, before, after):
    return event(
        seq,
        "STATUS_CHANGE",
        when,
        {"status": after},
        {"status": before},
    )


def test_week_bounds():
    start, end = week_bounds(
        date(2026, 11, 9),
        "Asia/Ho_Chi_Minh",
        now=datetime(2026, 11, 20, tzinfo=UTC),
    )

    assert start == START
    assert end == END


def test_reject_unfinished_week():
    with pytest.raises(ValueError):
        week_bounds(
            date(2026, 11, 16),
            "Asia/Ho_Chi_Minh",
            now=datetime(2026, 11, 20, tzinfo=UTC),
        )


def test_reject_non_monday():
    with pytest.raises(ValueError):
        week_bounds(
            date(2026, 11, 10),
            "Asia/Ho_Chi_Minh",
            now=datetime(2026, 11, 20, tzinfo=UTC),
        )


def test_task_completed_on_time():
    history = [
        create_task(),
        status_event(
            2,
            "2026-11-12T10:00:00+07:00",
            "TODO",
            "DONE",
        ),
    ]

    completion = _last_completion_in_week(
        history, START, END
    )

    assert completion is not None
    assert _due_date(completion["due_date"], TZ) == date(
        2026, 11, 12
    )
    assert completion["completed_at"].astimezone(
        TZ
    ).date() == date(2026, 11, 12)


def test_task_completed_late():
    history = [
        create_task(),
        status_event(
            2,
            "2026-11-13T10:00:00+07:00",
            "TODO",
            "DONE",
        ),
    ]

    completion = _last_completion_in_week(
        history, START, END
    )

    completed_date = completion[
        "completed_at"
    ].astimezone(TZ).date()

    due_date = _due_date(
        completion["due_date"], TZ
    )

    assert completed_date > due_date


def test_reopened_then_completed_late():
    history = [
        create_task(),
        status_event(
            2,
            "2026-11-12T09:00:00+07:00",
            "TODO",
            "DONE",
        ),
        status_event(
            3,
            "2026-11-12T11:00:00+07:00",
            "DONE",
            "IN_PROGRESS",
        ),
        status_event(
            4,
            "2026-11-14T09:00:00+07:00",
            "IN_PROGRESS",
            "DONE",
        ),
    ]

    completion = _last_completion_in_week(
        history, START, END
    )

    assert completion["completed_at"].astimezone(
        TZ
    ).date() == date(2026, 11, 14)

    assert completion["completed_at"].astimezone(
        TZ
    ).date() > _due_date(
        completion["due_date"], TZ
    )


def test_due_date_snapshot():
    history = [
        create_task("2026-11-12"),
        status_event(
            2,
            "2026-11-12T09:00:00+07:00",
            "TODO",
            "DONE",
        ),
        event(
            3,
            "DUE_CHANGE",
            "2026-11-13T09:00:00+07:00",
            {"due_date": "2026-11-20"},
            {"due_date": "2026-11-12"},
        ),
    ]

    completion = _last_completion_in_week(
        history, START, END
    )

    assert completion["due_date"] == "2026-11-12"

    state, warnings = replay(history, until=END)

    assert warnings == []
    assert state["due_date"] == "2026-11-20"


def test_no_completion():
    history = [create_task()]

    assert _last_completion_in_week(
        history, START, END
    ) is None


def test_completion_outside_week():
    history = [
        create_task(),
        status_event(
            2,
            "2026-11-16T10:00:00+07:00",
            "TODO",
            "DONE",
        ),
    ]

    assert _last_completion_in_week(
        history, START, END
    ) is None


def test_due_date_timezone():
    result = _due_date(
        "2026-11-15T18:00:00Z",
        TZ,
    )

    assert result == date(2026, 11, 16)


def test_sunday_is_not_overdue():
    sunday = date(2026, 11, 15)

    assert (date(2026, 11, 15) < sunday) is False
    assert (date(2026, 11, 14) < sunday) is True
