"""B13: quy tắc lưu trữ/khôi phục task (hàm thuần, có test)."""


def next_archive_state(archived: bool, action: str) -> tuple[bool, str | None]:
    """Trả (cần_ghi_thay_đổi, event_type). Lặp lại thao tác đã đúng trạng thái = không làm gì (idempotent)."""
    if action == "archive":
        return (False, None) if archived else (True, "ARCHIVE")
    if action == "restore":
        return (True, "RESTORE") if archived else (False, None)
    raise ValueError("action phải là archive hoặc restore")
