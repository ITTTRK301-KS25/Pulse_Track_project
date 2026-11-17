"""A01: AI Adapter — cấu hình, thử lại có giới hạn, lỗi kiểm soát, không lộ secret, mock mode. Không gọi mạng thật."""
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from pydantic import BaseModel

from app.ai import errors as E
from app.ai.adapter import AIAdapter
from app.ai.config import AIConfigError, from_mapping
from app.ai.redact import redact
from app.ai.retry import delay_for, parse_retry_after
from app.ai.transport import HttpResponse, TransportError, TransportTimeout

KEY = "sk-secret-VERY-private-123456"


class Plan(BaseModel):
    items: list[str]


def cfg(**kw):
    m = {"AI_API_KEY": KEY, "AI_MODEL": "model-x", "AI_RETRY_BACKOFF_SECONDS": "0.5"}
    m.update(kw)
    return from_mapping(m)


class FakeTransport:
    """Trả lần lượt các kết quả; phần tử là HttpResponse hoặc Exception để ném."""
    def __init__(self, *steps):
        self.steps, self.calls = list(steps), []

    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def ok_anthropic(text):
    return HttpResponse(200, {}, json.dumps({"content": [{"type": "text", "text": text}]}).encode())


def ok_openai(text):
    return HttpResponse(200, {}, json.dumps({"choices": [{"message": {"content": text}}]}).encode())


def resp(status, headers=None):
    return HttpResponse(status, headers or {}, b"{}")


def adapter(config, *steps):
    sleeps = []
    t = FakeTransport(*steps)
    return AIAdapter(config, transport=t, sleep=sleeps.append), t, sleeps


GOOD = '{"items": ["a", "b"]}'


# ---------------- cấu hình ----------------
def test_default_config_is_not_configured_and_safe():
    c = from_mapping({})
    assert c.configured is False and c.mock_mode is False
    assert c.timeout_seconds == 20 and c.max_retries == 2 and c.max_attempts == 3


def test_key_not_in_repr():
    assert KEY not in repr(cfg()) and KEY not in str(cfg())


@pytest.mark.parametrize("m", [
    {"AI_PROVIDER": "x"}, {"AI_TIMEOUT_SECONDS": "0"}, {"AI_TIMEOUT_SECONDS": "abc"},
    {"AI_MAX_RETRIES": "6"}, {"AI_MAX_RETRIES": "-1"}, {"AI_MAX_OUTPUT_TOKENS": "5"},
    {"AI_BASE_URL": "http://evil.example.com"}, {"AI_BASE_URL": "ftp://x"}, {"AI_MOCK_MODE": "maybe"},
])
def test_bad_config_rejected(m):
    with pytest.raises(AIConfigError):
        from_mapping(m)


def test_config_error_never_contains_key():
    with pytest.raises(AIConfigError) as e:
        from_mapping({"AI_API_KEY": KEY, "AI_MAX_RETRIES": "99"})
    assert KEY not in str(e.value)


def test_localhost_http_allowed():
    assert from_mapping({"AI_BASE_URL": "http://localhost:8080/v1/"}).base_url == "http://localhost:8080/v1"


def test_mock_mode_only_in_demo_or_test():
    for env in ("dev", "prod", ""):
        with pytest.raises(AIConfigError):
            from_mapping({"AI_MOCK_MODE": "true", "APP_ENV": env})
    assert from_mapping({"AI_MOCK_MODE": "true", "APP_ENV": "demo"}).mock_mode is True
    assert from_mapping({"AI_MOCK_MODE": "1", "APP_ENV": "test"}).mock_mode is True


# ---------------- gọi thành công ----------------
def test_success_anthropic_request_shape_and_result():
    a, t, _ = adapter(cfg(), ok_anthropic(GOOD))
    r = a.complete_json("PLANNER", "sys", "goal", Plan)
    assert r.data.items == ["a", "b"] and r.attempts == 1 and r.is_mock is False and r.label is None
    req, timeout = t.calls[0]
    assert req.url == "https://api.anthropic.com/v1/messages" and timeout == 20
    assert req.headers["x-api-key"] == KEY
    body = json.loads(req.body)
    assert body["model"] == "model-x" and body["system"] == "sys" and KEY not in req.body.decode()


def test_success_openai_compatible():
    a, t, _ = adapter(cfg(AI_PROVIDER="openai_compatible", AI_BASE_URL="https://llm.example.com/v1"), ok_openai(GOOD))
    assert a.complete_json("BREAKDOWN", "sys", "task", Plan).data.items == ["a", "b"]
    req, _ = t.calls[0]
    assert req.url == "https://llm.example.com/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer " + KEY


def test_json_in_code_fence_or_with_prose_is_accepted():
    a, *_ = adapter(cfg(), ok_anthropic("```json\n" + GOOD + "\n```"))
    assert a.complete_json("PLANNER", "s", "u", Plan).data.items == ["a", "b"]
    a, *_ = adapter(cfg(), ok_anthropic("Đây là kết quả: " + GOOD + " cảm ơn"))
    assert a.complete_json("PLANNER", "s", "u", Plan).data.items == ["a", "b"]


# ---------------- thử lại có giới hạn ----------------
def test_retries_transient_then_succeeds_with_backoff():
    a, t, sleeps = adapter(cfg(), resp(503), TransportTimeout(), ok_anthropic(GOOD))
    r = a.complete_json("PLANNER", "s", "u", Plan)
    assert r.attempts == 3 and len(t.calls) == 3
    assert sleeps == [0.5, 1.0]


def test_retry_is_bounded_never_infinite():
    a, t, sleeps = adapter(cfg(AI_MAX_RETRIES="2"), resp(503), resp(503), resp(503), resp(503), resp(503))
    with pytest.raises(E.AIError) as e:
        a.complete_json("PLANNER", "s", "u", Plan)
    assert len(t.calls) == 3 and e.value.code == "AI_UNAVAILABLE" and e.value.attempts == 3
    assert len(sleeps) == 2


def test_zero_retries_means_single_call():
    a, t, sleeps = adapter(cfg(AI_MAX_RETRIES="0"), resp(503), resp(503))
    with pytest.raises(E.AIError):
        a.complete_json("PLANNER", "s", "u", Plan)
    assert len(t.calls) == 1 and sleeps == []


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_non_transient_http_errors_not_retried(status):
    a, t, _ = adapter(cfg(), resp(status), ok_anthropic(GOOD))
    with pytest.raises(E.AIError) as e:
        a.complete_json("PLANNER", "s", "u", Plan)
    assert len(t.calls) == 1 and e.value.code == "AI_REJECTED" and e.value.http_status == 502


def test_bad_json_and_bad_schema_not_retried():
    for text in ("khong phai json", '{"items": "oops"}', "[1,2]"):
        a, t, _ = adapter(cfg(), ok_anthropic(text), ok_anthropic(GOOD))
        with pytest.raises(E.AIError) as e:
            a.complete_json("PLANNER", "s", "u", Plan)
        assert len(t.calls) == 1 and e.value.code == "AI_BAD_RESPONSE"


def test_unexpected_provider_body_is_bad_response():
    a, *_ = adapter(cfg(), HttpResponse(200, {}, b"<html>"))
    with pytest.raises(E.AIError) as e:
        a.complete_json("PLANNER", "s", "u", Plan)
    assert e.value.code == "AI_BAD_RESPONSE"


def test_rate_limit_uses_retry_after_capped_then_controlled_error():
    a, t, sleeps = adapter(cfg(AI_MAX_RETRIES="1"), resp(429, {"retry-after": "3"}), resp(429, {"retry-after": "999"}))
    with pytest.raises(E.AIError) as e:
        a.complete_json("PLANNER", "s", "u", Plan)
    assert e.value.code == "AI_RATE_LIMIT" and e.value.http_status == 429 and e.value.log_status == "RATE_LIMIT"
    assert sleeps == [3.0]
    assert delay_for(1, 0.5, 999) == 10.0


def test_timeout_error_mapping():
    a, t, _ = adapter(cfg(AI_MAX_RETRIES="0"), TransportTimeout())
    with pytest.raises(E.AIError) as e:
        a.complete_json("REPORT", "s", "u", Plan)
    assert (e.value.code, e.value.http_status, e.value.log_status) == ("AI_TIMEOUT", 504, "TIMEOUT")


def test_connection_error_is_unavailable_and_retried():
    a, t, _ = adapter(cfg(), TransportError("ConnectionRefusedError"), ok_anthropic(GOOD))
    assert a.complete_json("PLANNER", "s", "u", Plan).attempts == 2


def test_delay_helpers():
    assert [delay_for(n, 0.5) for n in (1, 2, 3, 10)] == [0.5, 1.0, 2.0, 10.0]
    assert parse_retry_after("2") == 2.0 and parse_retry_after("Wed, 21 Oct") is None and parse_retry_after(None) is None


# ---------------- không rò secret / prompt ----------------
def test_no_secret_or_prompt_in_errors_logs_and_records(caplog):
    secret_prompt = "BI-MAT-PROMPT-XYZ"
    records = []
    a, t, _ = adapter(cfg(AI_MAX_RETRIES="0"), HttpResponse(401, {}, ("bad key " + KEY).encode()))
    with caplog.at_level(logging.DEBUG, logger="app.ai"):
        with pytest.raises(E.AIError) as e:
            a.complete_json("PLANNER", "sys", secret_prompt, Plan, recorder=records.append)
    blob = " ".join([str(e.value), e.value.message, repr(e.value), caplog.text, repr(records)])
    assert KEY not in blob and secret_prompt not in blob


def test_redact():
    s = redact(f"loi {KEY} va Bearer abc.def-ghi va x-api-key: zzz", (KEY,))
    assert KEY not in s and "abc.def" not in s and "zzz" not in s


# ---------------- chưa cấu hình / kiểm yêu cầu ----------------
def test_not_configured_returns_controlled_error_without_network():
    a, t, _ = adapter(from_mapping({}), ok_anthropic(GOOD))
    with pytest.raises(E.AIError) as e:
        a.complete_json("PLANNER", "s", "u", Plan, mock_payload={"items": ["x"]})   # có mock_payload cũng KHÔNG tự dùng
    assert e.value.code == "AI_NOT_CONFIGURED" and e.value.http_status == 503 and t.calls == []


@pytest.mark.parametrize("feature,system,user", [
    ("UNKNOWN", "s", "u"), ("PLANNER", "", "u"), ("PLANNER", "s", "   "),
    ("PLANNER", "s", "x" * 4001), ("PLANNER", "x" * 4001, "u"),
])
def test_request_validation(feature, system, user):
    a, t, _ = adapter(cfg(), ok_anthropic(GOOD))
    with pytest.raises(E.AIError) as e:
        a.complete_json(feature, system, user, Plan)
    assert e.value.code == "AI_INVALID_REQUEST" and t.calls == []


# ---------------- mock mode ----------------
def mock_cfg():
    return from_mapping({"AI_MOCK_MODE": "true", "APP_ENV": "demo"})


def test_mock_mode_returns_labelled_validated_data_without_network():
    a, t, _ = adapter(mock_cfg())
    r = a.complete_json("PLANNER", "s", "u", Plan, mock_payload={"items": ["demo"]})
    assert r.is_mock is True and r.label == "MOCK" and r.data.items == ["demo"] and t.calls == []


def test_mock_payload_still_validated_and_required():
    a, *_ = adapter(mock_cfg())
    with pytest.raises(E.AIError) as e:
        a.complete_json("PLANNER", "s", "u", Plan, mock_payload={"items": 5})
    assert e.value.code == "AI_BAD_RESPONSE"
    with pytest.raises(E.AIError) as e:
        a.complete_json("PLANNER", "s", "u", Plan)
    assert e.value.code == "AI_MOCK_MISSING"


def test_real_failure_never_falls_back_to_mock():
    a, t, _ = adapter(cfg(AI_MAX_RETRIES="0"), resp(503))
    with pytest.raises(E.AIError):
        a.complete_json("PLANNER", "s", "u", Plan, mock_payload={"items": ["fake"]})


# ---------------- bản ghi cho A07 ----------------
def test_recorder_gets_success_and_failure_metadata():
    recs = []
    a, *_ = adapter(cfg(), ok_anthropic(GOOD))
    r = a.complete_json("REPORT", "s", "u", Plan, request_id="req-1", recorder=recs.append)
    assert recs[0].request_id == "req-1" == r.request_id
    assert (recs[0].type, recs[0].status, recs[0].error_code, recs[0].is_mock) == ("REPORT", "SUCCESS", None, False)
    a, *_ = adapter(cfg(AI_MAX_RETRIES="0"), TransportTimeout())
    with pytest.raises(E.AIError):
        a.complete_json("REPORT", "s", "u", Plan, request_id="req-2", recorder=recs.append)
    assert (recs[1].status, recs[1].error_code, recs[1].request_id) == ("TIMEOUT", "AI_TIMEOUT", "req-2")


def test_recorder_exception_does_not_break_call():
    def boom(_):
        raise RuntimeError("db down")
    a, *_ = adapter(cfg(), ok_anthropic(GOOD))
    assert a.complete_json("PLANNER", "s", "u", Plan, recorder=boom).data.items == ["a", "b"]


def test_request_id_generated_when_missing():
    a, *_ = adapter(cfg(), ok_anthropic(GOOD))
    assert len(a.complete_json("PLANNER", "s", "u", Plan).request_id) >= 16


# ---------------- không có endpoint mới ----------------
def test_no_public_endpoint_for_adapter():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    assert not any("ai" in p.name and p.suffix == ".py" for p in (app_dir / "api").glob("*.py"))
    assert "app.ai" not in (app_dir / "main.py").read_text(encoding="utf-8")


def test_http_mapping():
    pytest.importorskip("fastapi")
    from app.ai.http import to_http_exception
    ex = to_http_exception(E.rate_limited())
    assert ex.status_code == 429 and ex.detail == E.rate_limited().message


def test_load_ai_config_reads_env(monkeypatch, tmp_path):
    pytest.importorskip("pydantic_settings")
    from app.ai.config import load_ai_config
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("AI_API_KEY=k123\nAI_MODEL=m1\nAI_MAX_RETRIES=1\n", encoding="utf-8")
    c = load_ai_config()
    assert c.configured and c.model == "m1" and c.max_retries == 1 and "k123" not in repr(c)
