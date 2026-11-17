"""Thử lại có giới hạn (A01 AC2). Hàm thuần, `sleep` được tiêm vào để test không phải chờ."""
MAX_DELAY_SECONDS = 10.0


def delay_for(attempt: int, backoff: float, retry_after: float | None = None) -> float:
    """Thời gian chờ trước lần thử kế tiếp. attempt = số lần đã thử (>=1). Có trần MAX_DELAY_SECONDS."""
    if retry_after is not None and retry_after >= 0:
        return min(float(retry_after), MAX_DELAY_SECONDS)
    return min(backoff * (2 ** (attempt - 1)), MAX_DELAY_SECONDS)


def parse_retry_after(value: str | None) -> float | None:
    """Retry-After dạng số giây; dạng ngày HTTP bị bỏ qua (dùng backoff)."""
    if value is None:
        return None
    try:
        v = float(value.strip())
    except ValueError:
        return None
    return v if v >= 0 else None
