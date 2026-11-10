"""B14: quy tắc subtask một cấp (hàm thuần, có test)."""

OK = None
PARENT_IS_SUBTASK = "parent_is_subtask"
PARENT_ARCHIVED = "parent_archived"


def check_parent(parent_parent_id, parent_archived_at) -> str | None:
    """Trả mã lỗi nếu task cha không hợp lệ, None nếu hợp lệ.

    - Task cha không được là subtask (có parent_id) -> không cho cấp ba (422).
    - Task cha đã lưu trữ -> không tạo thêm subtask (409).
    """
    if parent_parent_id is not None:
        return PARENT_IS_SUBTASK
    if parent_archived_at is not None:
        return PARENT_ARCHIVED
    return OK
