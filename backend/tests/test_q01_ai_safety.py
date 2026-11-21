"""Q01 – Kiểm thử An toàn AI & Validation Schema.

Phạm vi (theo mô tả Q01): (1) prompt/yêu cầu gửi AI không chứa secret, (2) AI trả sai schema bị từ chối, (3) AI không tự ý sửa
số liệu thống kê. Chỉ KIỂM THỬ code hiện có trên master, không sửa code của nhóm. Không cần DB, không gọi mạng: AI được giả lập
bằng transport kịch bản (đi qua đúng AIAdapter + schema thật của A02/A05/A09).

LƯU Ý: SRS/SDD trong repo chỉ nhắc "AI-01..AI-08" ở bảng truy vết mà KHÔNG định nghĩa từng mã, nên các ca bên dưới đánh số
Q01-xx; cột ánh xạ sang AI-0x trong báo cáo chỉ là đề xuất, cần nhóm xác nhận.
"""
import ast
import json
import logging
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from pydantic import ValidationError

from app.ai import errors as E
from app.ai.adapter import AIAdapter
from app.ai.config import from_mapping
from app.ai.redact import redact
from app.ai.transport import HttpResponse
from app.schemas.breakdown import BreakdownOutput
from app.schemas.planner import PlannerOutput
from app.schemas.weekly_report import WeeklyNarrativeOutput

APP = Path(__file__).resolve().parents[1] / "app"
KEY = "sk-ant-SECRET-key-0123456789abcdef"
DB_PASSWORD = "p4ssw0rd-NOT-FOR-AI"
USER_PROMPT = "Mục tiêu bí mật của khách hàng ZETA-PROJECT-7731"


def cfg(provider="anthropic", **kw):
    m = {"AI_PROVIDER": provider, "AI_API_KEY": KEY, "AI_MODEL": "m", "AI_RETRY_BACKOFF_SECONDS": "0", **kw}
    return from_mapping(m)


class Script:
    """Transport giả: trả lần lượt các phản hồi đã định sẵn và ghi lại mọi request gửi đi."""

    def __init__(self, *steps):
        self.steps, self.requests = list(steps), []

    def __call__(self, request, timeout):
        self.requests.append(request)
        s = self.steps.pop(0)
        if isinstance(s, Exception):
            raise s
        return s


def anthropic_ok(text):
    return HttpResponse(200, {}, json.dumps({"content": [{"type": "text", "text": text}]}).encode())


def openai_ok(text):
    return HttpResponse(200, {}, json.dumps({"choices": [{"message": {"content": text}}]}).encode())


def run(schema, text, provider="anthropic", **kw):
    ok = anthropic_ok if provider == "anthropic" else openai_ok
    t = Script(ok(text))
    a = AIAdapter(cfg(provider, **kw), transport=t, sleep=lambda _s: None)
    return a.complete_json("PLANNER", "Hệ thống: chỉ trả JSON", USER_PROMPT, schema), t


def bad(schema, text, feature="PLANNER"):
    t = Script(anthropic_ok(text))
    a = AIAdapter(cfg(), transport=t, sleep=lambda _s: None)
    with pytest.raises(E.AIError) as e:
        a.complete_json(feature, "Hệ thống", USER_PROMPT, schema)
    return e.value, t


# ============================ Nhóm 1: Secret không lọt vào prompt / log / lỗi ============================
@pytest.mark.parametrize("provider", ["anthropic", "openai_compatible"])
def test_q01_01_api_key_only_in_auth_header_never_in_body_or_url(provider):
    _, t = run(PlannerOutput, '{"items":[{"title":"A"}]}', provider)
    req = t.requests[0]
    assert KEY not in req.url
    assert KEY not in (req.body.decode() if isinstance(req.body, bytes) else str(req.body))
    assert any(KEY in str(v) for v in req.headers.values())        # key có mặt ĐÚNG chỗ: header xác thực
    body = json.loads(req.body.decode() if isinstance(req.body, bytes) else req.body)
    assert USER_PROMPT in json.dumps(body, ensure_ascii=False)     # prompt người dùng có mặt trong body, key thì không


def test_q01_02_secret_never_in_logs_even_on_failure(caplog):
    with caplog.at_level(logging.DEBUG):
        run(PlannerOutput, '{"items":[{"title":"A"}]}')
        bad(PlannerOutput, "không phải json")
        t = Script(HttpResponse(401, {}, json.dumps({"error": f"invalid key {KEY}"}).encode()))
        a = AIAdapter(cfg(), transport=t, sleep=lambda _s: None)
        with pytest.raises(E.AIError):
            a.complete_json("PLANNER", "s", USER_PROMPT, PlannerOutput)
    assert KEY not in caplog.text
    assert "ZETA-PROJECT-7731" not in caplog.text                  # nội dung prompt của người dùng cũng không vào log


def test_q01_03_provider_error_body_echoing_key_is_not_leaked_to_client():
    t = Script(HttpResponse(400, {}, json.dumps({"error": f"bad request for key {KEY}"}).encode()))
    a = AIAdapter(cfg(), transport=t, sleep=lambda _s: None)
    with pytest.raises(E.AIError) as e:
        a.complete_json("PLANNER", "s", USER_PROMPT, PlannerOutput)
    for text in (e.value.message, e.value.code, str(e.value)):
        assert KEY not in text and "bad request" not in text


@pytest.mark.parametrize("raw", [
    f"lỗi với khóa {KEY}", "Authorization: Bearer abc.def-123", "x-api-key: topsecretvalue", "api_key=hunter2hunter2",
    "token sk-abcdefghijk12345",
])
def test_q01_04_redact_masks_credentials(raw):
    out = redact(raw, (KEY,))
    assert KEY not in out and "abc.def-123" not in out and "topsecretvalue" not in out
    assert "hunter2hunter2" not in out and "sk-abcdefghijk12345" not in out


SERVICES_BUILDING_PROMPTS = ("planner_service.py", "breakdown_service.py", "weekly_report_service.py")
FORBIDDEN = ("SECRET_KEY", "AI_API_KEY", "api_key", "password", "password_hash", "token_hash", "settings.", "os.environ", "getenv",
             "DATABASE_URL")


@pytest.mark.parametrize("name", SERVICES_BUILDING_PROMPTS)
def test_q01_05_prompt_builders_do_not_touch_secrets(name):
    src = (APP / "services" / name).read_text(encoding="utf-8")
    for word in FORBIDDEN:
        assert word not in src, f"{name} chứa '{word}': dịch vụ dựng prompt không được đọc secret/cấu hình"


def _prompt_calls(name):
    """Các lời gọi .complete_json(...) trong service: trả danh sách (feature, node tham số prompt người dùng)."""
    tree = ast.parse((APP / "services" / name).read_text(encoding="utf-8"))
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "complete_json":
            out.append(n)
    return out


@pytest.mark.parametrize("name,feature", [("planner_service.py", "PLANNER"), ("breakdown_service.py", "BREAKDOWN"),
                                          ("weekly_report_service.py", "REPORT")])
def test_q01_06_each_ai_feature_makes_exactly_one_adapter_call_with_its_type(name, feature):
    calls = _prompt_calls(name)
    assert len(calls) == 1
    assert calls[0].args[0].value == feature


def test_q01_07_user_prompt_of_planner_contains_only_goal_and_scope():
    src = (APP / "services" / "planner_service.py").read_text(encoding="utf-8")
    m = re.search(r"user_prompt = json\.dumps\(\s*(\{.*?\})\s*,", src, re.S)
    assert m, "không tìm thấy đoạn dựng user_prompt"
    keys = set(re.findall(r'"(\w+)":', m.group(1)))
    assert keys == {"goal", "scope"}


def test_q01_08_env_file_is_ignored_and_example_has_no_real_secret():
    root = Path(__file__).resolve().parents[2]
    gi = root / ".gitignore"
    if gi.exists():
        lines = [x.strip() for x in gi.read_text(encoding="utf-8").splitlines()]
        assert ".env" in lines
    example = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    assert not re.search(r"sk-[A-Za-z0-9_\-]{8,}", example)
    for line in example.splitlines():
        if line.startswith("AI_API_KEY"):
            assert line.split("=", 1)[1].strip() in ("", "<your_api_key>")


# ============================ Nhóm 2: AI trả sai schema bị từ chối ============================
def test_q01_09_valid_output_is_accepted_control_case():
    r, _ = run(PlannerOutput, '{"items":[{"title":"Việc 1","description":"mô tả","due_date":"2026-12-31"}]}')
    assert r.data.items[0].title == "Việc 1" and r.is_mock is False


def test_q01_10_json_wrapped_in_code_fence_is_accepted():
    r, _ = run(PlannerOutput, '```json\n{"items":[{"title":"A"}]}\n```')
    assert len(r.data.items) == 1


T200, T201 = "x" * 200, "x" * 201
PLANNER_BAD = {
    "không phải JSON": "xin chào đây không phải json",
    "JSON là mảng": '[{"title":"A"}]',
    "thiếu khóa items": '{"tasks":[{"title":"A"}]}',
    "items rỗng": '{"items":[]}',
    "21 phần tử (tối đa 20)": json.dumps({"items": [{"title": f"t{i}"} for i in range(21)]}),
    "items là chuỗi": '{"items":"A"}',
    "tiêu đề rỗng": '{"items":[{"title":""}]}',
    "tiêu đề toàn khoảng trắng": '{"items":[{"title":"   "}]}',
    "tiêu đề 201 ký tự": json.dumps({"items": [{"title": T201}]}),
    "mô tả 5001 ký tự": json.dumps({"items": [{"title": "A", "description": "d" * 5001}]}),
    "due_date sai định dạng": '{"items":[{"title":"A","due_date":"31/12/2026"}]}',
    "due_date không tồn tại": '{"items":[{"title":"A","due_date":"2026-02-30"}]}',
    "trường lạ trong item": '{"items":[{"title":"A","status":"DONE"}]}',
    "trường lạ ở gốc": '{"items":[{"title":"A"}],"auto_approve":true}',
    "title sai kiểu": '{"items":[{"title":123}]}',
}


@pytest.mark.parametrize("case", list(PLANNER_BAD))
def test_q01_11_planner_wrong_schema_is_rejected(case):
    err, t = bad(PlannerOutput, PLANNER_BAD[case])
    assert (err.code, err.http_status) == ("AI_BAD_RESPONSE", 502)
    assert len(t.requests) == 1                                    # sai schema không bị gọi lại vô hạn
    assert KEY not in err.message and "ZETA" not in err.message


def test_q01_12_boundary_values_that_must_still_be_accepted():
    ok20 = json.dumps({"items": [{"title": f"t{i}"} for i in range(20)]})
    assert len(run(PlannerOutput, ok20)[0].data.items) == 20
    assert run(PlannerOutput, json.dumps({"items": [{"title": T200, "description": "d" * 5000}]}))[0].data.items[0].title == T200


BREAKDOWN_BAD = {
    "11 subtask (tối đa 10)": json.dumps({"items": [{"title": f"t{i}"} for i in range(11)]}),
    "items rỗng": '{"items":[]}',
    "tiêu đề 201 ký tự": json.dumps({"items": [{"title": T201}]}),
    "subtask lồng nhau (trường lạ)": '{"items":[{"title":"A","subtasks":[{"title":"B"}]}]}',
    "due_date sai": '{"items":[{"title":"A","due_date":"mai"}]}',
    "không phải JSON": "<html>lỗi</html>",
}


@pytest.mark.parametrize("case", list(BREAKDOWN_BAD))
def test_q01_13_breakdown_wrong_schema_is_rejected(case):
    err, _ = bad(BreakdownOutput, BREAKDOWN_BAD[case], "BREAKDOWN")
    assert err.code == "AI_BAD_RESPONSE" and err.http_status == 502


def test_q01_14_breakdown_accepts_exactly_10_items():
    ok10 = json.dumps({"items": [{"title": f"t{i}"} for i in range(10)]})
    assert len(run(BreakdownOutput, ok10)[0].data.items) == 10


REPORT_BAD = {
    "thiếu narrative": "{}",
    "narrative ngắn hơn 20 ký tự": '{"narrative":"ngắn"}',
    "narrative dài hơn 6000 ký tự": json.dumps({"narrative": "n" * 6001}),
    "narrative sai kiểu": '{"narrative":["a","b"]}',
    "không phải JSON": "Báo cáo tuần này tốt.",
}


@pytest.mark.parametrize("case", list(REPORT_BAD))
def test_q01_15_report_narrative_wrong_schema_is_rejected(case):
    err, _ = bad(WeeklyNarrativeOutput, REPORT_BAD[case], "REPORT")
    assert err.code == "AI_BAD_RESPONSE" and err.http_status == 502


def test_q01_16_report_narrative_boundaries_accepted():
    for n in (20, 6000):
        r, _ = run(WeeklyNarrativeOutput, json.dumps({"narrative": "n" * n}))
        assert len(r.data.narrative) == n


def _literal_assigned(name, var):
    tree = ast.parse((APP / "services" / name).read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == var for t in n.targets):
            return ast.literal_eval(n.value)
    raise AssertionError(f"không thấy {var} trong {name}")


def test_q01_17_mock_payloads_conform_to_their_schemas():
    PlannerOutput.model_validate(_literal_assigned("planner_service.py", "_MOCK_PAYLOAD"))
    BreakdownOutput.model_validate(_literal_assigned("breakdown_service.py", "_MOCK_PAYLOAD"))
    WeeklyNarrativeOutput.model_validate(_literal_assigned("weekly_report_service.py", "mock_payload"))


def test_q01_18_mock_output_is_labelled_and_only_in_demo_test():
    c = from_mapping({"AI_MOCK_MODE": "true", "APP_ENV": "test"})
    r = AIAdapter(c).complete_json("PLANNER", "s", "u", PlannerOutput,
                                   mock_payload=_literal_assigned("planner_service.py", "_MOCK_PAYLOAD"))
    assert r.is_mock is True and r.label == "MOCK"
    with pytest.raises(Exception):
        from_mapping({"AI_MOCK_MODE": "true", "APP_ENV": "production"})


def test_q01_19_adapter_rejects_unknown_feature_and_oversized_or_empty_prompt():
    a = AIAdapter(cfg(), transport=Script(), sleep=lambda _s: None)
    for feature, system, user in (("HACK", "s", "u"), ("PLANNER", "", "u"), ("PLANNER", "s", "   "), ("PLANNER", "s", "x" * 200000)):
        with pytest.raises(E.AIError) as e:
            a.complete_json(feature, system, user, PlannerOutput)
        assert e.value.code == "AI_INVALID_REQUEST"


# ============================ Nhóm 3: AI không tự ý sửa số liệu thống kê ============================
def test_q01_20_narrative_schema_cannot_carry_metrics_so_ai_cannot_override_numbers():
    with pytest.raises(ValidationError):
        WeeklyNarrativeOutput.model_validate({"narrative": "n" * 30, "metrics": {"MET-01": 99}})
    with pytest.raises(ValidationError):
        WeeklyNarrativeOutput.model_validate({"narrative": "n" * 30, "MET-01": 99})
    err, _ = bad(WeeklyNarrativeOutput, json.dumps({"narrative": "n" * 30, "MET-06": 100}), "REPORT")
    assert err.code == "AI_BAD_RESPONSE"


def _report_tree():
    return ast.parse((APP / "services" / "weekly_report_service.py").read_text(encoding="utf-8"))


def test_q01_21_preview_metrics_come_only_from_backend_engine():
    tree = _report_tree()
    # 1) snapshot["metrics"] lấy từ calculate_weekly_metrics, không từ AI
    src = (APP / "services" / "weekly_report_service.py").read_text(encoding="utf-8")
    assert 'values = metrics_result["metrics"]' in src
    assert re.search(r'"metrics":\s*values', src)
    # 2) kết quả AI chỉ được dùng cho narrative / request_id / is_mock
    used = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "ai_result":
            used.add(n.attr)
        if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Attribute)
                and isinstance(n.value.value, ast.Name) and n.value.value.id == "ai_result"):
            used.add(f"{n.value.attr}.{n.attr}")
    assert used <= {"data", "request_id", "is_mock", "data.narrative"}, used
    assert "data.narrative" in used


def test_q01_22_ai_failure_never_replaces_or_drops_metrics():
    src = (APP / "services" / "weekly_report_service.py").read_text(encoding="utf-8")
    assert "except AIError" in src and "ai_error = " in src       # AI lỗi: ghi lỗi, tiếp tục với metrics của backend
    assert '"metrics": format_metrics(values)' in src


@pytest.mark.parametrize("name", ["weekly_report_save_service.py", "weekly_report_read_service.py"])
def test_q01_23_saving_and_reading_reports_never_call_ai_again(name):
    src = (APP / "services" / name).read_text(encoding="utf-8")
    assert "get_ai_adapter" not in src and "complete_json" not in src


def test_q01_24_metrics_engine_is_pure_history_and_does_not_import_ai():
    for f in ("core/metrics.py", "services/metrics_service.py"):
        src = (APP / f).read_text(encoding="utf-8")
        assert "app.ai" not in src and "get_ai_adapter" not in src


def test_q01_25_ai_transport_response_cannot_change_stored_metrics_via_adapter():
    """Dù AI 'cố' đưa số liệu vào phản hồi, dữ liệu qua schema narrative chỉ còn đúng một trường text."""
    r, _ = run(WeeklyNarrativeOutput, json.dumps({"narrative": "Hoàn thành 3 công việc, tỷ lệ đúng hạn tốt."}))
    assert set(r.data.model_dump()) == {"narrative"}


def test_q01_26_report_system_prompt_forbids_changing_metrics():
    prompt = _literal_assigned("weekly_report_service.py", "SYSTEM_PROMPT")
    assert "Không thay đổi" in prompt and "MET" in prompt
    assert "Không tự tạo thêm số liệu" in prompt


# ---- Các ca dưới đây ghi nhận LỖ HỔNG ĐÃ BIẾT trên master (xfail = chưa đạt, không làm đỏ bộ test). Khi nhóm vá xong sẽ tự chuyển XPASS. ----
@pytest.mark.xfail(reason="A08: get_ai_adapter() chưa chuyển lỗi cấu hình AI thành AIError, service chỉ bắt AIError nên sẽ ra 500", strict=False)
def test_q01_27_bad_ai_configuration_becomes_controlled_error(monkeypatch):
    from app.ai import adapter as adapter_mod
    from app.ai.config import AIConfigError

    def broken():
        raise AIConfigError("AI_MOCK_MODE chỉ được bật khi APP_ENV là demo hoặc test")
    monkeypatch.setattr(adapter_mod, "load_ai_config", broken)
    adapter_mod.get_ai_adapter.cache_clear()
    try:
        with pytest.raises(E.AIError):
            adapter_mod.get_ai_adapter()
    finally:
        adapter_mod.get_ai_adapter.cache_clear()


@pytest.mark.xfail(reason="A08: lỗi bất ngờ trong lúc gọi AI (không phải AIError) chưa được chuẩn hóa nên lọt ra thành 500", strict=False)
def test_q01_28_unexpected_exception_during_call_becomes_controlled_error():
    a = AIAdapter(cfg(), transport=Script(RuntimeError(f"boom {KEY}")), sleep=lambda _s: None)
    with pytest.raises(E.AIError) as e:
        a.complete_json("PLANNER", "s", USER_PROMPT, PlannerOutput)
    assert KEY not in e.value.message
