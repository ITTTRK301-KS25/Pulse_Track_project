"""Quy tắc trạng thái bản nháp AI (hàm thuần, không cần DB). Dùng chung cho A04 và các task sửa/hủy/duyệt draft sau này."""

DRAFT, APPROVED, DISCARDED = "DRAFT", "APPROVED", "DISCARDED"

MSG_APPROVED = "Bản nháp đã được duyệt, không thể sửa, hủy hoặc duyệt lại"
MSG_DISCARDED = "Bản nháp đã bị hủy, không thể sửa hoặc duyệt lại"
MSG_STALE = "Bản nháp đã được thay đổi ở nơi khác, hãy tải lại rồi thử lại"


def edit_block_reason(status: str) -> str | None:
    """None nếu còn thao tác được (chỉ DRAFT); ngược lại trả câu thông báo lỗi 409."""
    if status == DRAFT:
        return None
    if status == APPROVED:
        return MSG_APPROVED
    return MSG_DISCARDED


def is_stale(current_version: int, expected_version: int | None) -> bool:
    return expected_version is not None and expected_version != current_version
