
"""Metrics Engine M01-M04: tính MET-01 đến MET-06 từ TaskHistory."""

from collections import defaultdict
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.history_rules import replay, sort_events
from app.core.weekly_period import week_bounds
from app.models.project import Project
from app.models.task_history import TaskHistory


def _utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _due_date(value, project_tz):
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(project_tz).date()
        return value.date()

    if isinstance(value, date):
        return value

    raw = str(value)

    if "T" in raw or " " in raw:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed.astimezone(project_tz).date()
        return parsed.date()

    return date.fromisoformat(raw[:10])


def _history_to_dict(event):
    return {
        "event_seq": event.event_seq,
        "event_type": event.event_type,
        "occurred_at": event.occurred_at,
        "before_value": event.before_value,
        "after_value": event.after_value,
    }


def _last_completion_in_week(history, start_at, end_at):
    """
    Trả về lần chuyển sang DONE cuối cùng trong tuần.

    Lưu lại due_date tại đúng thời điểm hoàn thành.
    Không sử dụng due_date hiện tại để đánh giá quá khứ.
    """
    rolling = None
    last_completion = None

    for event in sort_events(history):
        event_at = _utc(event["occurred_at"])

        if event_at >= end_at:
            break

        event_type = event["event_type"]
        after = event.get("after_value") or {}

        if event_type == "CREATE":
            rolling = {
                **after,
                "archived_at": None,
            }

            # CREATE không phải STATUS_CHANGE sang DONE.
            continue

        if rolling is None:
            continue

        if event_type == "STATUS_CHANGE":
            old_status = rolling.get("status")
            new_status = after.get("status")

            if (
                old_status != "DONE"
                and new_status == "DONE"
                and start_at <= event_at < end_at
                and rolling.get("parent_id") is None
                and rolling.get("archived_at") is None
            ):
                last_completion = {
                    "completed_at": event_at,
                    "due_date": rolling.get("due_date"),
                }

            rolling.update(after)

        elif event_type in (
            "DUE_CHANGE",
            "ASSIGNEE_CHANGE",
            "PARENT_CHANGE",
            "DETAIL_CHANGE",
        ):
            rolling.update(after)

        elif event_type in ("ARCHIVE", "RESTORE"):
            rolling["archived_at"] = after.get("archived_at")

    return last_completion


def calculate_weekly_metrics(
    db: Session,
    project_id: int,
    week_start: date,
    now: datetime | None = None,
):
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy dự án",
        )

    try:
        start_at, end_at = week_bounds(
            week_start,
            project.timezone,
            now,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from None

    project_tz = ZoneInfo(project.timezone)

    events = db.scalars(
        select(TaskHistory)
        .where(
            TaskHistory.project_id == project_id,
            TaskHistory.occurred_at < end_at,
        )
        .order_by(
            TaskHistory.occurred_at,
            TaskHistory.event_seq,
        )
    ).all()

    grouped = defaultdict(list)

    for event in events:
        grouped[event.task_id].append(
            _history_to_dict(event)
        )

    completed_ids = set()
    on_time_ids = set()
    open_ids = set()
    overdue_ids = set()
    due_this_week_ids = set()
    warnings = []

    next_monday = week_start + timedelta(days=7)
    sunday = next_monday - timedelta(days=1)

    for task_id, history in grouped.items():
        state, task_warnings = replay(
            history,
            until=end_at,
        )

        if task_warnings:
            warnings.append({
                "task_id": task_id,
                "messages": task_warnings,
            })

        if state is None:
            continue

        # Chỉ tính Task cha.
        if state.get("parent_id") is not None:
            continue

        archived = state.get("archived_at") is not None
        status = state.get("status")
        due = _due_date(
            state.get("due_date"),
            project_tz,
        )

        # MET-02: Task đang mở cuối tuần.
        if not archived and status != "DONE":
            open_ids.add(task_id)

            # MET-03: Quá hạn tại cuối Chủ nhật.
            # Hạn Chủ nhật chưa được coi là quá hạn.
            if due is not None and due < sunday:
                overdue_ids.add(task_id)

        # MET-04: Task active có hạn trong tuần.
        if (
            not archived
            and due is not None
            and week_start <= due < next_monday
        ):
            due_this_week_ids.add(task_id)

        completion = _last_completion_in_week(
            history,
            start_at,
            end_at,
        )

        if completion is None:
            continue

        # MET-01: Mỗi Task hoàn thành tối đa một lần/tuần.
        completed_ids.add(task_id)

        # MET-05: Chỉ xét lần hoàn thành cuối cùng.
        completion_due = _due_date(
            completion["due_date"],
            project_tz,
        )

        completion_date = completion[
            "completed_at"
        ].astimezone(project_tz).date()

        if (
            completion_due is not None
            and completion_date <= completion_due
        ):
            on_time_ids.add(task_id)

    met01 = len(completed_ids)
    met02 = len(open_ids)
    met03 = len(overdue_ids)
    met04 = len(due_this_week_ids)
    met05 = len(on_time_ids & completed_ids)

    met06 = (
        round(met05 / met01 * 100, 2)
        if met01 > 0
        else 0.0
    )

    return {
        "project_id": project_id,
        "week_start": week_start.isoformat(),
        "timezone": project.timezone,
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat(),
        "metrics": {
            "MET-01": met01,
            "MET-02": met02,
            "MET-03": met03,
            "MET-04": met04,
            "MET-05": met05,
            "MET-06": met06,
        },
        "warnings": warnings,
    }
