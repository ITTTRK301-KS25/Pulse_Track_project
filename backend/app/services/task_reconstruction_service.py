"""M01: tái dựng trạng thái Task từ lịch sử tại cuối tuần báo cáo."""
from collections import defaultdict
from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.history_rules import replay
from app.core.weekly_period import week_bounds
from app.models.project import Project
from app.models.task_history import TaskHistory


def reconstruct_project_tasks(
    db: Session,
    project_id: int,
    week_start: date,
    now: datetime | None = None,
) -> dict:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy dự án")
    try:
        start_at, end_at = week_bounds(week_start, project.timezone, now)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None

    rows = db.scalars(
        select(TaskHistory)
        .where(
            TaskHistory.project_id == project_id,
            TaskHistory.occurred_at < end_at,
        )
        .order_by(TaskHistory.occurred_at, TaskHistory.event_seq)
    ).all()

    events_by_task: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        events_by_task[row.task_id].append({
            "event_seq": row.event_seq,
            "event_type": row.event_type,
            "occurred_at": row.occurred_at,
            "before_value": row.before_value,
            "after_value": row.after_value,
        })

    states = {}
    warnings = []
    for task_id, events in events_by_task.items():
        state, task_warnings = replay(events, until=end_at)
        if state is not None:
            states[task_id] = state
        if task_warnings:
            warnings.append({"task_id": task_id, "messages": task_warnings})

    return {
        "project_id": project_id,
        "week_start": week_start.isoformat(),
        "timezone": project.timezone,
        "start_at": start_at.isoformat().replace("+00:00", "Z"),
        "end_at": end_at.isoformat().replace("+00:00", "Z"),
        "states": states,
        "warnings": warnings,
    }
