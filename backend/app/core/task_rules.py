"""B12: so sánh giá trị hiện tại với giá trị yêu cầu -> danh sách sự kiện lịch sử. Hàm thuần, có test.

Chỉ trường THỰC SỰ đổi mới sinh sự kiện (gửi lại đúng giá trị cũ thì không ghi gì).
"""
EVENT_BY_FIELD = {
    "status": "STATUS_CHANGE",
    "due_date": "DUE_CHANGE",
    "assignee_id": "ASSIGNEE_CHANGE",
    "title": "DETAIL_CHANGE",
    "description": "DETAIL_CHANGE",
}
ORDER = ("STATUS_CHANGE", "DUE_CHANGE", "ASSIGNEE_CHANGE", "DETAIL_CHANGE")


def changed_fields(current: dict, requested: dict) -> dict:
    """Trả {trường: giá trị mới} cho các trường khác giá trị hiện tại."""
    return {k: v for k, v in requested.items() if k in EVENT_BY_FIELD and current.get(k) != v}


def build_events(current: dict, changes: dict) -> list[tuple[str, dict, dict]]:
    """[(event_type, before, after)]; title+description gộp thành một DETAIL_CHANGE."""
    grouped: dict[str, tuple[dict, dict]] = {}
    for field, new in changes.items():
        etype = EVENT_BY_FIELD[field]
        before, after = grouped.setdefault(etype, ({}, {}))
        before[field] = current.get(field)
        after[field] = new
    return [(t, *grouped[t]) for t in ORDER if t in grouped]


def is_stale(current_version: int, sent_version: int) -> bool:
    return current_version != sent_version
