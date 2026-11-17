"""A01 – AI Adapter: cổng DUY NHẤT để backend gọi LLM.

- AC1: key/model/URL lấy từ cấu hình server; yêu cầu và phản hồi đều được kiểm.
- AC2: timeout + thử lại có giới hạn, chỉ với lỗi tạm thời (timeout, 429, 5xx, mất kết nối);
       JSON sai / 4xx KHÔNG thử lại. Adapter không ghi dữ liệu nghiệp vụ nên không thể tạo bản ghi trùng.
- AC3: mọi lỗi trả về AIError (mã + câu an toàn); không lộ key, không đưa prompt vào log.
- AC4: mock mode chỉ bật khi cấu hình tường minh (demo/test); KHÔNG tự chuyển sang mock khi AI lỗi.

Ví dụ dùng (A02/A05/A09 sẽ gọi):
    result = get_ai_adapter().complete_json("PLANNER", system, user, PlannerOut, recorder=...)
    result.data  # đã validate theo PlannerOut;  result.is_mock cho biết dữ liệu giả
"""
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable

from app.ai import errors as E
from app.ai import providers
from app.ai.config import AIConfig, load_ai_config
from app.ai.redact import redact
from app.ai.retry import delay_for, parse_retry_after
from app.ai.transport import HttpResponse, TransportError, TransportTimeout, urllib_transport

log = logging.getLogger("app.ai")

# type khớp ai_call_logs.type; giới hạn độ dài prompt người dùng theo từng chức năng
FEATURE_MAX_USER_CHARS = {"PLANNER": 4000, "BREAKDOWN": 4000, "REPORT": 12000}
MAX_SYSTEM_CHARS = 4000
_FENCE = re.compile(r"^```[a-zA-Z]*\s*(.*?)\s*```$", re.DOTALL)


@dataclass(frozen=True)
class AICallRecord:
    """Metadata một lần gọi AI để A07 ghi vào ai_call_logs. KHÔNG chứa prompt, phản hồi hay key."""
    request_id: str
    type: str
    status: str            # SUCCESS / ERROR / TIMEOUT / RATE_LIMIT
    error_code: str | None
    latency_ms: int
    attempts: int
    is_mock: bool


@dataclass(frozen=True)
class AIResult:
    data: Any
    request_id: str
    feature: str
    latency_ms: int
    attempts: int
    is_mock: bool = False

    @property
    def label(self) -> str | None:
        return "MOCK" if self.is_mock else None


def _parse_json(text: str) -> Any:
    t = text.strip()
    m = _FENCE.match(t)
    if m:
        t = m.group(1)
    try:
        return json.loads(t)
    except ValueError:
        i, j = t.find("{"), t.rfind("}")
        if 0 <= i < j:
            return json.loads(t[i:j + 1])
        raise


class AIAdapter:
    def __init__(self, config: AIConfig, transport: Callable | None = None,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic):
        self.config = config
        self._transport = transport or urllib_transport
        self._sleep = sleep
        self._clock = clock

    # ---- kiểm yêu cầu ----
    @staticmethod
    def _check_request(feature: str, system: str, user: str) -> None:
        if feature not in FEATURE_MAX_USER_CHARS:
            raise E.invalid_request("Loại chức năng AI không hợp lệ")
        if not isinstance(system, str) or not system.strip() or len(system) > MAX_SYSTEM_CHARS:
            raise E.invalid_request("Chỉ dẫn hệ thống không hợp lệ")
        if not isinstance(user, str) or not user.strip():
            raise E.invalid_request("Nội dung gửi AI không được để trống")
        if len(user) > FEATURE_MAX_USER_CHARS[feature]:
            raise E.invalid_request("Nội dung gửi AI quá dài")

    # ---- một lần gọi HTTP, chuẩn hóa lỗi ----
    def _once(self, request) -> HttpResponse:
        try:
            resp = self._transport(request, self.config.timeout_seconds)
        except TransportTimeout:
            raise E.timeout() from None
        except TransportError:
            raise E.unavailable() from None
        s = resp.status
        if 200 <= s < 300:
            return resp
        if s == 429:
            err = E.rate_limited()
            err.retry_after = parse_retry_after((resp.headers or {}).get("retry-after"))
            raise err
        if s >= 500 or s in (408, 409):
            raise E.unavailable()
        raise E.rejected()

    def complete_json(self, feature: str, system: str, user: str, schema: Any, *,
                      request_id: str | None = None, mock_payload: Any = None,
                      recorder: Callable[[AICallRecord], None] | None = None) -> AIResult:
        rid = request_id or uuid.uuid4().hex
        start = self._clock()
        attempts = 0
        is_mock = False
        try:
            self._check_request(feature, system, user)
            cfg = self.config
            if cfg.mock_mode:
                if mock_payload is None:
                    raise E.mock_missing()
                is_mock = True
                data = self._validate(schema, mock_payload)
            elif not cfg.configured:
                raise E.not_configured()
            else:
                request = providers.build_request(cfg, system, user)
                text = None
                while True:
                    attempts += 1
                    try:
                        resp = self._once(request)
                        text = providers.extract_text(cfg.provider, resp.body)
                        break
                    except ValueError:
                        raise E.bad_response() from None
                    except E.AIError as err:
                        if not err.retryable or attempts >= cfg.max_attempts:
                            raise
                        self._sleep(delay_for(attempts, cfg.retry_backoff_seconds, getattr(err, "retry_after", None)))
                try:
                    payload = _parse_json(text)
                except ValueError:
                    raise E.bad_response() from None
                data = self._validate(schema, payload)
        except E.AIError as err:
            err.request_id, err.attempts = rid, attempts
            self._emit(recorder, AICallRecord(rid, feature, err.log_status, err.code, self._ms(start), attempts, is_mock))
            log.warning("AI call failed request_id=%s type=%s code=%s attempts=%s",
                        rid, feature, err.code, attempts)
            raise
        record = AICallRecord(rid, feature, E.LOG_SUCCESS, None, self._ms(start), attempts, is_mock)
        self._emit(recorder, record)
        return AIResult(data, rid, feature, record.latency_ms, attempts, is_mock)

    @staticmethod
    def _validate(schema: Any, payload: Any) -> Any:
        try:
            return schema.model_validate(payload)
        except Exception:   # mọi lỗi kiểm schema (không đưa nội dung AI vào thông báo)
            raise E.bad_response() from None

    def _ms(self, start: float) -> int:
        return int(max(0.0, self._clock() - start) * 1000)

    @staticmethod
    def _emit(recorder, record: AICallRecord) -> None:
        if recorder is None:
            return
        try:
            recorder(record)
        except Exception as exc:   # ghi log lỗi không được làm hỏng nghiệp vụ
            log.warning("AI recorder failed: %s", redact(type(exc).__name__))


@lru_cache(maxsize=1)
def get_ai_adapter() -> AIAdapter:
    """Tạo adapter từ cấu hình server (chỉ khi cần dùng, nên import không làm backend lỗi khi chưa có cấu hình AI)."""
    return AIAdapter(load_ai_config())
