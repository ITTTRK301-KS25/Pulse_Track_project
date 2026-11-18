"""A04 + A05: quy tắc thuần, schema, đăng ký route (không cần DB)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from pydantic import ValidationError

from app.core import ai_draft_state as S
from app.core import idempotency as I
from app.schemas.breakdown import BreakdownOutput, BreakdownRequest
from app.schemas.planner_approve import ApprovePlannerDraftRequest

ROOT = Path(__file__).resolve().parents[1] / "app"


# ---------- trạng thái draft ----------
def test_only_draft_can_be_acted_on():
    assert S.edit_block_reason("DRAFT") is None
    assert S.edit_block_reason("APPROVED") == S.MSG_APPROVED
    assert S.edit_block_reason("DISCARDED") == S.MSG_DISCARDED


def test_version_staleness():
    assert S.is_stale(2, None) is False and S.is_stale(2, 2) is False and S.is_stale(2, 1) is True


# ---------- idempotency ----------
def test_hash_is_canonical():
    assert I.payload_hash({"a": 1, "b": 2}) == I.payload_hash({"b": 2, "a": 1})
    assert I.payload_hash({"a": 1}) != I.payload_hash({"a": 2})
    assert len(I.payload_hash({"x": "đ"})) == 64


def test_decide():
    h = I.payload_hash({"d": 1})
    assert I.decide(None, False, h) == I.NEW
    assert I.decide(h, True, h) == I.REPLAY
    assert I.decide(h, True, I.payload_hash({"d": 2})) == I.CONFLICT     # cùng khóa, khác nội dung -> 409
    assert I.decide(h, False, h) == I.CONFLICT                           # bản ghi chưa hoàn tất -> không replay


# ---------- schema duyệt ----------
def test_approve_request_valid():
    r = ApprovePlannerDraftRequest(expected_version=1, idempotency_key=" approve-key-0001 ")
    assert r.idempotency_key == "approve-key-0001"


def test_approve_request_all_optional():
    """Frontend F12 gửi body rỗng hoặc {"draft_id": N}, khóa nằm ở header."""
    assert ApprovePlannerDraftRequest().expected_version is None
    assert ApprovePlannerDraftRequest(draft_id=5).draft_id == 5


@pytest.mark.parametrize("payload", [
    {"expected_version": 0},
    {"expected_version": "1"},
    {"draft_id": 0},
    {"idempotency_key": "short"},                                  # < 8 ký tự
    {"idempotency_key": "x" * 161},
    {"idempotency_key": "co dau cach 12345"},
    {"idempotency_key": "approve-key-0001", "status": "APPROVED"},  # trường lạ
])
def test_approve_request_invalid(payload):
    with pytest.raises(ValidationError):
        ApprovePlannerDraftRequest(**payload)


def test_resolve_key():
    assert I.resolve_key("approve-key-0001", None) == ("approve-key-0001", None)
    assert I.resolve_key(None, "approve-key-0001") == ("approve-key-0001", None)
    assert I.resolve_key(" approve-key-0001 ", "approve-key-0001") == ("approve-key-0001", None)
    assert I.resolve_key(None, None)[0] is None and I.resolve_key(None, None)[1]
    assert I.resolve_key("", "  ")[1]
    assert I.resolve_key("approve-key-0001", "approve-key-0002")[1]   # header ≠ body -> lỗi


# ---------- schema breakdown ----------
def test_breakdown_request():
    assert BreakdownRequest(objective="  Chia task thành các bước nhỏ  ").objective == "Chia task thành các bước nhỏ"
    for bad in ("ngắn", " " * 20, "x" * 2001):
        with pytest.raises(ValidationError):
            BreakdownRequest(objective=bad)
    with pytest.raises(ValidationError):
        BreakdownRequest(objective="Mục tiêu hợp lệ đủ dài", extra=1)


def item(**kw):
    return {"title": "Việc nhỏ", **kw}


def test_breakdown_output_schema():
    out = BreakdownOutput.model_validate({"items": [item(description=" mô tả ", due_date="2026-12-31")]})
    assert out.items[0].description == "mô tả" and out.items[0].due_date == "2026-12-31"


@pytest.mark.parametrize("payload", [
    {"items": []}, {"items": [item()] * 11}, {"items": [item(title="")]}, {"items": [item(title="x" * 201)]},
    {"items": [item(due_date="31/12/2026")]}, {"items": [item(extra=1)]}, {"items": "oops"}, {},
])
def test_breakdown_output_rejects_bad_ai_json(payload):
    with pytest.raises(ValidationError):
        BreakdownOutput.model_validate(payload)


# ---------- đăng ký route / hợp đồng API ----------
def test_routes_registered_in_main():
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    for line in ("from app.api import planner_approve as planner_approve_api",
                 "from app.api import breakdown as breakdown_api",
                 "app.include_router(planner_approve_api.router)",
                 "app.include_router(breakdown_api.router)"):
        assert line in main


def test_paths_match_api_contract():
    a = (ROOT / "api" / "planner_approve.py").read_text(encoding="utf-8")
    assert 'prefix="/ai/planner/drafts"' in a and '@router.post("/{draft_id}/approve")' in a
    b = (ROOT / "api" / "breakdown.py").read_text(encoding="utf-8")
    assert 'prefix="/tasks"' in b and '@router.post("/{task_id}/ai/breakdown")' in b


def test_breakdown_service_never_creates_tasks():
    src = (ROOT / "services" / "breakdown_service.py").read_text(encoding="utf-8")
    assert "Task(" not in src and "DraftCreatedTask" not in src and "add_event" not in src
