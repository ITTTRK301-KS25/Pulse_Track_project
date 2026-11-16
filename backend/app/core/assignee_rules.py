"""B19: quy tắc thuần cho người thực hiện (assignee) — không cần DB.

Người thực hiện phải là OWNER hoặc MEMBER HIỆN HÀNH của cùng dự án.
VIEWER, người ngoài dự án, người đã bị xóa khỏi dự án, user không tồn tại đều không hợp lệ.
Để trống (None) luôn hợp lệ (task chưa giao cho ai).
"""
ASSIGNABLE_ROLES = ("OWNER", "MEMBER")
ASSIGNEE_MSG = "Người thực hiện phải là OWNER hoặc MEMBER của dự án"


def is_assignable(role: str | None) -> bool:
    """role là vai trò hiện tại của user trong dự án (None nếu không có dòng thành viên)."""
    return role in ASSIGNABLE_ROLES


def needs_check(assignee_id: int | None) -> bool:
    """Chỉ cần kiểm khi thật sự gán một người; None (bỏ giao) thì bỏ qua."""
    return assignee_id is not None
