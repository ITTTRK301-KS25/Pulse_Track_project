"""B20: thống kê task và chỉ số tạm tính của tuần hiện tại."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.metrics import compute_metrics
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.services import project_access as access


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_dashboard(
    db: Session,
    user,
    project_id: int,
    now: datetime | None = None,
) -> dict:
    project, role = access.get_project_and_role(db, project_id, user)
    access.require(role, "project.read")

    try:
        project_tz = ZoneInfo(project.timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Múi giờ dự án không hợp lệ",
        ) from None

    now_utc = _utc(now or datetime.now(timezone.utc))
    today = now_utc.astimezone(project_tz).date()
    week_start = today - timedelta(days=today.weekday())
    start_at = datetime.combine(week_start, time.min, tzinfo=project_tz).astimezone(timezone.utc)

    status_rows = db.execute(
        select(Task.status, func.count())
        .where(
            Task.project_id == project_id,
            Task.parent_id.is_(None),
            Task.archived_at.is_(None),
        )
        .group_by(Task.status)
    ).all()
    task_counts = {
        "TODO": 0,
        "IN_PROGRESS": 0,
        "TESTING_QA": 0,
        "IN_REVIEW": 0,
        "DONE": 0,
    }
    for task_status, count in status_rows:
        if task_status in task_counts:
            task_counts[task_status] = count

    overdue_tasks = db.scalar(
        select(func.count())
        .select_from(Task)
        .where(
            Task.project_id == project_id,
            Task.parent_id.is_(None),
            Task.archived_at.is_(None),
            Task.status != "DONE",
            Task.due_date.is_not(None),
            Task.due_date < today,
        )
    ) or 0

    events = db.scalars(
        select(TaskHistory)
        .where(
            TaskHistory.project_id == project_id,
            TaskHistory.occurred_at < now_utc,
        )
        .order_by(TaskHistory.occurred_at, TaskHistory.event_seq)
    ).all()
    history = [
        {
            "task_id": event.task_id,
            "event_seq": event.event_seq,
            "event_type": event.event_type,
            "before_value": event.before_value,
            "after_value": event.after_value,
            "occurred_at": event.occurred_at,
        }
        for event in events
    ]
    weekly = compute_metrics(history, start_at, now_utc, project.timezone)

    return {
        "project_id": project_id,
        "timezone": project.timezone,
        "scope": "PARENT_TASKS_ONLY",
        "as_of": now_utc.isoformat().replace("+00:00", "Z"),
        "task_counts": {
            **task_counts,
            "TOTAL": sum(task_counts.values()),
        },
        "overdue_tasks": overdue_tasks,
        "current_week": {
            "week_start": week_start.isoformat(),
            "metrics": weekly["metrics"],
            "warnings": weekly["warnings"],
            "complete": weekly["complete"],
            "is_provisional": True,
            "label": "Tạm tính - tuần hiện tại",
        },
    }
