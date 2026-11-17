"""Lỗi AI có kiểm soát (không chứa secret, không chứa nội dung prompt)."""

# Trạng thái ghi log, khớp ENUM ai_call_status trong thiết kế (A07 sẽ dùng)
LOG_SUCCESS, LOG_ERROR, LOG_TIMEOUT, LOG_RATE_LIMIT = "SUCCESS", "ERROR", "TIMEOUT", "RATE_LIMIT"


class AIError(Exception):
    """Lỗi từ AI đã được chuẩn hóa. `message` là câu an toàn có thể trả cho người dùng."""

    def __init__(self, code: str, message: str, http_status: int, *, log_status: str = LOG_ERROR,
                 retryable: bool = False, request_id: str | None = None, attempts: int = 0,
                 retry_after: float | None = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.http_status = http_status
        self.log_status = log_status
        self.retryable = retryable
        self.request_id = request_id
        self.attempts = attempts
        self.retry_after = retry_after   # giây, từ header Retry-After (nếu có)


def not_configured() -> AIError:
    return AIError("AI_NOT_CONFIGURED", "Dịch vụ AI chưa được cấu hình", 503)


def invalid_request(reason: str) -> AIError:
    return AIError("AI_INVALID_REQUEST", reason, 400)


def mock_missing() -> AIError:
    return AIError("AI_MOCK_MISSING", "Mock mode đang bật nhưng chưa có dữ liệu mẫu cho chức năng này", 500)


def timeout() -> AIError:
    return AIError("AI_TIMEOUT", "Dịch vụ AI phản hồi quá lâu, vui lòng thử lại sau", 504,
                   log_status=LOG_TIMEOUT, retryable=True)


def rate_limited() -> AIError:
    return AIError("AI_RATE_LIMIT", "Dịch vụ AI đang bị giới hạn tần suất, vui lòng thử lại sau", 429,
                   log_status=LOG_RATE_LIMIT, retryable=True)


def unavailable() -> AIError:
    return AIError("AI_UNAVAILABLE", "Dịch vụ AI tạm thời không khả dụng, vui lòng thử lại sau", 503, retryable=True)


def rejected() -> AIError:
    return AIError("AI_REJECTED", "Dịch vụ AI từ chối yêu cầu", 502)


def bad_response() -> AIError:
    return AIError("AI_BAD_RESPONSE", "AI trả về dữ liệu không đúng định dạng yêu cầu", 502)
