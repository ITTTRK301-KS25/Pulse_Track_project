"""B10: quy tắc "dự án luôn còn ít nhất một OWNER". Hàm thuần để test độc lập."""

OWNER = "OWNER"


def would_leave_no_owner(owner_count: int, current_role: str, new_role: str | None) -> bool:
    """True nếu thao tác khiến dự án không còn OWNER nào.

    new_role = None nghĩa là xóa thành viên.
    """
    losing_owner = current_role == OWNER and new_role != OWNER
    return losing_owner and owner_count <= 1
