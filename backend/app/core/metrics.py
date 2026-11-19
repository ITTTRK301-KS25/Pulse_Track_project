"""M02–M04: tính MET-01..MET-06 từ TaskHistory (hàm thuần, không cần DB). M05 kiểm chứng bằng bộ dữ liệu mẫu.

Định nghĩa (SDD mục 5, tuần là [start_at, end_at), end_at loại trừ):
- MET-01: số Task CHA khác nhau có >= 1 STATUS_CHANGE sang DONE với start_at <= occurred_at < end_at.
          "Cha" xét tại thời điểm sự kiện (parent_id sau khi phát lại đến sự kiện đó). DONE nhiều lần vẫn tính 1.
- MET-02: Task cha đã tạo, chưa archived và status khác DONE tại end_at- (trạng thái cuối kỳ).
- MET-03: trong MET-02, due_date cuối kỳ khác NULL và < NGÀY ĐỊA PHƯƠNG của end_at (due_date là ngày:
          chỉ quá hạn sau khi hết ngày hạn; hạn Chủ nhật cuối tuần là quá hạn lúc 00:00 thứ Hai).
- MET-04: Task cha đã tạo, chưa archived tại end_at-, due_date cuối kỳ nằm trong [ngày địa phương của start_at,
          ngày địa phương của end_at); không phân biệt trạng thái; đếm theo Task nên đổi hạn không đếm lặp.
- MET-05: trong MET-01, Task có >= 1 sự kiện DONE (trong tuần, khi là Task cha) mà tại sự kiện đó due_date hiệu lực khác NULL
          và NGÀY ĐỊA PHƯƠNG của sự kiện <= due_date. Mỗi Task đếm một lần.
- MET-06: MET-05 / (số Task MET-01 có due_date hiệu lực ở ít nhất một sự kiện DONE) x 100, làm tròn 2 chữ số;
          mẫu số 0 -> null kèm cảnh báo NO_DUE_DATE_DONE (không chia cho 0).
Subtask (parent_id khác NULL) không bao giờ được đếm. Chỉ dùng lịch sử, không đọc bảng tasks hiện tại.

Quy ước thiếu dữ liệu (chờ nhóm xác nhận ở M05): Task có sự kiện nhưng thiếu CREATE KHÔNG tái dựng được -> loại khỏi
các số đếm, kèm cảnh báo MISSING_CREATE ghi rõ chỉ số bị ảnh hưởng, kết quả `complete=False`. Không suy diễn từ bảng tasks.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.history_rules import _ts, replay, sort_events

MISSING_CREATE = "MISSING_CREATE"
EVENT_BEFORE_CREATE = "EVENT_BEFORE_CREATE"
METRICS = ("MET-01", "MET-02", "MET-03", "MET-04", "MET-05")
NO_DUE_DATE_DONE = "NO_DUE_DATE_DONE"


def local_date(moment: datetime, tz_name: str) -> date:
    """Ngày địa phương (theo múi giờ IANA của dự án) của một mốc thời gian."""
    return _ts(moment).astimezone(ZoneInfo(tz_name)).date()


def _due(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _is_done_event(e: dict) -> bool:
    return e["event_type"] == "STATUS_CHANGE" and (e.get("after_value") or {}).get("status") == "DONE"


def task_facts(task_id: int, events: list[dict], start_at: datetime, end_at: datetime,
               start_day: date, end_day: date, tz_name: str) -> tuple[dict | None, list[dict]]:
    """Các sự thật của một Task trong tuần. Trả (facts | None, warnings).
    facts: {done_in_week, done_with_due, done_on_time, open_at_end, overdue_at_end, due_in_week}. None nếu Task chưa tồn tại / không tái dựng được."""
    ordered = sort_events(events)
    creates = [e for e in ordered if e["event_type"] == "CREATE"]
    if not creates:
        if not any(_ts(e["occurred_at"]) < end_at for e in ordered):
            return None, []
        done_in_week = any(_is_done_event(e) and start_at <= _ts(e["occurred_at"]) < end_at for e in ordered)
        affects = (["MET-01", "MET-05", "MET-06"] if done_in_week else []) + ["MET-02", "MET-03", "MET-04"]
        return None, [{"task_id": task_id, "code": MISSING_CREATE, "affects": affects,
                       "message": "Thiếu sự kiện CREATE nên không tái dựng được, không suy diễn từ bảng tasks"}]
    if _ts(creates[0]["occurred_at"]) >= end_at:
        return None, []                                           # tạo từ cuối kỳ trở đi: chưa tồn tại

    warnings = []
    state_end, raw = replay(ordered, until=end_at)
    for w in raw:
        warnings.append({"task_id": task_id, "code": EVENT_BEFORE_CREATE, "affects": [], "message": w})
    if state_end is None:
        return None, warnings

    done_in_week = done_with_due = done_on_time = False
    for i, e in enumerate(ordered):
        t = _ts(e["occurred_at"])
        if t >= end_at:
            break
        if t < start_at or not _is_done_event(e):
            continue
        state_then, _ = replay(ordered[:i + 1])                   # trạng thái ngay sau sự kiện DONE này
        if state_then is None or state_then.get("parent_id") is not None:
            continue                                              # tại sự kiện này là subtask: không tính
        done_in_week = True
        due_then = _due(state_then.get("due_date"))               # hạn hiệu lực tại sự kiện (không phải hạn hiện tại)
        if due_then is not None:
            done_with_due = True
            if local_date(t, tz_name) <= due_then:
                done_on_time = True

    is_parent = state_end.get("parent_id") is None
    alive = is_parent and state_end.get("archived_at") is None
    due = _due(state_end.get("due_date"))
    open_at_end = alive and state_end.get("status") != "DONE"
    return {
        "done_in_week": done_in_week,
        "done_with_due": done_with_due,
        "done_on_time": done_on_time,
        "open_at_end": open_at_end,
        "overdue_at_end": bool(open_at_end and due is not None and due < end_day),
        "due_in_week": bool(alive and due is not None and start_day <= due < end_day),
    }, warnings


def compute_metrics(events: list[dict], start_at: datetime, end_at: datetime, tz_name: str) -> dict:
    """events: mọi sự kiện có occurred_at < end_at của dự án, mỗi phần tử có task_id, event_seq, event_type,
    before_value, after_value, occurred_at. Trả {"metrics", "details", "warnings", "complete"}."""
    start_at, end_at = _ts(start_at), _ts(end_at)
    start_day, end_day = local_date(start_at, tz_name), local_date(end_at, tz_name)
    by_task: dict[int, list[dict]] = {}
    for e in events:
        by_task.setdefault(e["task_id"], []).append(e)

    ids = {k: [] for k in METRICS}
    with_due: list[int] = []
    warnings: list[dict] = []
    for task_id in sorted(by_task):
        facts, w = task_facts(task_id, by_task[task_id], start_at, end_at, start_day, end_day, tz_name)
        warnings.extend(w)
        if facts is None:
            continue
        if facts["done_in_week"]:
            ids["MET-01"].append(task_id)
        if facts["open_at_end"]:
            ids["MET-02"].append(task_id)
        if facts["overdue_at_end"]:
            ids["MET-03"].append(task_id)
        if facts["due_in_week"]:
            ids["MET-04"].append(task_id)
        if facts["done_on_time"]:
            ids["MET-05"].append(task_id)
        if facts["done_with_due"]:
            with_due.append(task_id)
    metrics = {k: len(v) for k, v in ids.items()}
    metrics["MET-06"] = None
    if with_due:
        metrics["MET-06"] = round(len(ids["MET-05"]) * 100 / len(with_due), 2)
    else:
        warnings.append({"task_id": None, "code": NO_DUE_DATE_DONE, "affects": ["MET-06"],
                         "message": "MET-06 là null: không có Task hoàn thành nào có hạn (mẫu số 0)"})
    return {
        "metrics": metrics,
        "details": {**ids, "MET-06_denominator": with_due},
        "warnings": warnings,
        "complete": not any(x["code"] == MISSING_CREATE for x in warnings),
    }
