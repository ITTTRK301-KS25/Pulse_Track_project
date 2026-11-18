"""A04: hàm thuần cho idempotency (không cần DB)."""
import hashlib
import json

OP_PLANNER_APPROVE = "PLANNER_APPROVE"
MSG_KEY_REUSED = "Khóa idempotency đã được dùng cho một yêu cầu khác"

REPLAY, CONFLICT, NEW = "REPLAY", "CONFLICT", "NEW"


def payload_hash(payload: dict) -> str:
    """SHA-256 của JSON chuẩn hóa (khóa sắp xếp, không phụ thuộc thứ tự/khoảng trắng)."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def decide(existing_hash: str | None, existing_completed: bool, new_hash: str) -> str:
    """NEW: chưa có bản ghi -> xử lý bình thường.
    REPLAY: cùng khóa + cùng nội dung + đã hoàn tất -> trả lại kết quả đã lưu, không tạo thêm gì.
    CONFLICT: cùng khóa nhưng nội dung khác (hoặc bản ghi chưa hoàn tất) -> 409."""
    if existing_hash is None:
        return NEW
    if existing_hash == new_hash and existing_completed:
        return REPLAY
    return CONFLICT


def resolve_key(header_key: str | None, body_key: str | None) -> tuple[str | None, str | None]:
    """Lấy khóa idempotency từ header `Idempotency-Key` (frontend dùng) hoặc từ body (tương thích bản cũ).
    Trả (khóa, lỗi). Không có khóa -> lỗi; hai nơi cùng gửi mà khác nhau -> lỗi."""
    h = header_key.strip() if header_key else None
    b = body_key.strip() if body_key else None
    if h and b and h != b:
        return None, "Idempotency-Key ở header và body không khớp"
    key = h or b
    if not key:
        return None, "Thiếu Idempotency-Key (gửi trong header Idempotency-Key)"
    return key, None
