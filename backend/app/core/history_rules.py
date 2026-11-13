"""B17: quy tắc lịch sử task (hàm thuần, có test) + B18: phân trang.

- validate_event: kiểm một sự kiện đúng cấu trúc theo thiết kế (CREATE có after đầy đủ, các loại còn lại
  chỉ chứa trường đổi, ARCHIVE/RESTORE có archived_at). Dùng làm hàng rào cho các writer (B11–B14).
- replay: tái dựng trạng thái task tại một thời điểm từ CREATE + các sự kiện (nền cho chỉ số MET của nhóm AI/Metrics).
  Thiếu CREATE thì trả (None, cảnh báo), không suy diễn từ bảng tasks hiện tại.
- page_slice: lấy limit + 1 dòng để biết còn trang sau hay không.
Không thêm loại sự kiện ngoài danh mục của thiết kế.
"""
from datetime import datetime, timezone

SNAPSHOT_KEYS = ("title", "description", "status", "due_date", "assignee_id", "parent_id")
EVENT_TYPES = ("CREATE", "STATUS_CHANGE", "DUE_CHANGE", "ASSIGNEE_CHANGE",
               "PARENT_CHANGE", "ARCHIVE", "RESTORE", "DETAIL_CHANGE")
_FIELD_EVENTS = {
    "STATUS_CHANGE": {"status"},
    "DUE_CHANGE": {"due_date"},
    "ASSIGNEE_CHANGE": {"assignee_id"},
    "PARENT_CHANGE": {"parent_id"},
}
STATUSES = ("TODO", "IN_PROGRESS", "DONE")


def validate_event(event_type: str, before, after) -> list[str]:
    """Trả danh sách lỗi (rỗng nếu hợp lệ)."""
    if event_type not in EVENT_TYPES:
        return [f"event_type không thuộc danh mục: {event_type}"]
    errs: list[str] = []
    if event_type == "CREATE":
        if before is not None:
            errs.append("CREATE phải có before_value là null")
        if not isinstance(after, dict) or any(k not in after for k in SNAPSHOT_KEYS):
            errs.append("CREATE phải có after_value đầy đủ " + ", ".join(SNAPSHOT_KEYS))
        elif after.get("status") not in STATUSES:
            errs.append("CREATE có status không hợp lệ")
        return errs
    if not isinstance(before, dict) or not isinstance(after, dict):
        return ["before_value và after_value phải là object"]
    if event_type in _FIELD_EVENTS:
        want = _FIELD_EVENTS[event_type]
        if set(before) != want or set(after) != want:
            errs.append(f"{event_type} chỉ được chứa trường {sorted(want)}")
        elif before == after:
            errs.append(f"{event_type} không có thay đổi thật")
        elif event_type == "STATUS_CHANGE" and (after["status"] not in STATUSES or before["status"] not in STATUSES):
            errs.append("STATUS_CHANGE có status không hợp lệ")
    elif event_type == "DETAIL_CHANGE":
        allowed = {"title", "description"}
        if not before or set(before) != set(after) or not set(after) <= allowed:
            errs.append("DETAIL_CHANGE chỉ gồm title/description, before và after cùng trường")
        elif before == after:
            errs.append("DETAIL_CHANGE không có thay đổi thật")
    else:  # ARCHIVE / RESTORE
        if set(before) != {"archived_at"} or set(after) != {"archived_at"}:
            errs.append(f"{event_type} phải chứa đúng trường archived_at")
        elif event_type == "ARCHIVE" and not (before["archived_at"] is None and after["archived_at"]):
            errs.append("ARCHIVE: before.archived_at phải null và after.archived_at có giá trị")
        elif event_type == "RESTORE" and not (before["archived_at"] and after["archived_at"] is None):
            errs.append("RESTORE: before.archived_at có giá trị và after.archived_at phải null")
    return errs


def _ts(v) -> datetime:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def sort_events(events: list[dict]) -> list[dict]:
    """Thứ tự ổn định: occurred_at, rồi event_seq khi trùng thời điểm."""
    return sorted(events, key=lambda e: (_ts(e["occurred_at"]), e["event_seq"]))


def replay(events: list[dict], until=None) -> tuple[dict | None, list[str]]:
    """Trạng thái task tại thời điểm `until` (loại trừ; None = đến hết) và danh sách cảnh báo.

    Mỗi event: {event_seq, event_type, after_value, occurred_at}.
    Trả (state, warnings); state có thêm khóa archived_at (None nếu đang hoạt động).
    """
    cutoff = _ts(until) if until is not None else None
    state: dict | None = None
    warnings: list[str] = []
    for e in sort_events(events):
        if cutoff is not None and _ts(e["occurred_at"]) >= cutoff:
            break
        t, after = e["event_type"], e.get("after_value")
        if t == "CREATE":
            state = {**after, "archived_at": None}
        elif state is None:
            warnings.append(f"thiếu CREATE trước sự kiện {t} (event_seq={e['event_seq']})")
        elif t in _FIELD_EVENTS or t == "DETAIL_CHANGE":
            state.update(after)
        elif t in ("ARCHIVE", "RESTORE"):
            state["archived_at"] = after.get("archived_at")
    if state is None and not warnings:
        warnings.append("thiếu CREATE: không có dữ liệu để tái dựng")
    return state, warnings


def page_slice(rows: list, limit: int) -> tuple[list, bool]:
    """rows được lấy với limit + 1 dòng. Trả (các dòng của trang, còn trang sau?)."""
    return rows[:limit], len(rows) > limit
