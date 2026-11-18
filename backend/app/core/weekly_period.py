"""Hàm tính khoảng tuần theo múi giờ IANA của dự án."""
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def week_bounds(
    week_start: date,
    timezone_name: str,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Trả đầu tuần và đầu tuần kế tiếp dưới dạng UTC; chỉ nhận tuần đã kết thúc."""
    if isinstance(week_start, datetime) or week_start.weekday() != 0:
        raise ValueError("week_start phải là ngày thứ Hai")
    try:
        project_tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        raise ValueError("Múi giờ dự án không hợp lệ") from None

    start_local = datetime.combine(week_start, time.min, tzinfo=project_tz)
    next_week = date.fromordinal(week_start.toordinal() + 7)
    end_local = datetime.combine(next_week, time.min, tzinfo=project_tz)
    start_at = start_local.astimezone(timezone.utc)
    end_at = end_local.astimezone(timezone.utc)

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if end_at > current.astimezone(timezone.utc):
        raise ValueError("Chỉ có thể tái dựng tuần đã kết thúc")
    return start_at, end_at
