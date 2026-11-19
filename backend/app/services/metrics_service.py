"""M02–M04: tính MET-01..MET-06 của một tuần đã kết thúc từ TaskHistory (chỉ đọc DB, không ghi).

Nội bộ: SDD chỉ có một API công khai là POST /projects/{id}/reports/preview (A09). Quyền OWNER do endpoint đó kiểm tra.
Dùng lại week_bounds (M01): chỉ nhận thứ Hai, múi giờ IANA của dự án, và chỉ tuần đã kết thúc.
"""
from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.metrics import compute_metrics
from app.core.weekly_period import week_bounds
from app.models.project import Project
from app.models.task_history import TaskHistory


def calculate_weekly_metrics(db: Session, project_id: int, week_start: date, now: datetime | None = None) -> dict:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy dự án")
    try:
        start_at, end_at = week_bounds(week_start, project.timezone, now)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None

    rows = db.scalars(
        select(TaskHistory)
        .where(TaskHistory.project_id == project_id, TaskHistory.occurred_at < end_at)
        .order_by(TaskHistory.occurred_at, TaskHistory.event_seq)
    ).all()
    events = [{
        "task_id": r.task_id, "event_seq": r.event_seq, "event_type": r.event_type,
        "before_value": r.before_value, "after_value": r.after_value, "occurred_at": r.occurred_at,
    } for r in rows]

    result = compute_metrics(events, start_at, end_at, project.timezone)
    return {
        "project_id": project_id,
        "week_start": week_start.isoformat(),
        "timezone": project.timezone,
        "start_at": start_at.isoformat().replace("+00:00", "Z"),
        "end_at": end_at.isoformat().replace("+00:00", "Z"),
        **result,
    }
