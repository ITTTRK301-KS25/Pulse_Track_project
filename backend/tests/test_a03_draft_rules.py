"""A03: quy tắc bản nháp + schema sửa draft + đăng ký route (không cần DB)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from pydantic import ValidationError

from app.core import ai_draft_state as R
from app.schemas.planner_draft import UpdatePlannerDraftRequest

ROOT = Path(__file__).resolve().parents[1] / "app"


def item(title="Task A", **kw):
    return {"title": title, **kw}


# ---- quy tắc trạng thái ----
def test_only_draft_is_editable():
    assert R.edit_block_reason("DRAFT") is None
    assert R.edit_block_reason("APPROVED") == R.MSG_APPROVED
    assert R.edit_block_reason("DISCARDED") == R.MSG_DISCARDED
    assert R.edit_block_reason("???") is not None


def test_version_check_optional():
    assert R.is_stale(3, None) is False
    assert R.is_stale(3, 3) is False
    assert R.is_stale(3, 2) is True


def test_same_items():
    assert R.same_items([{"a": 1}], [{"a": 1}]) is True
    assert R.same_items([{"a": 1}], [{"a": 2}]) is False
    assert R.same_items(None, []) is True
    assert R.same_items([{"a": 1}], [{"a": 1}, {"a": 2}]) is False


# ---- schema PATCH ----
def test_valid_update_request():
    r = UpdatePlannerDraftRequest(suggestions=[item(), item("Task B", description="  mô tả ", due_date="2026-12-31")], version=2)
    assert r.suggestions[1].description == "mô tả" and r.suggestions[1].due_date == "2026-12-31" and r.version == 2
    assert UpdatePlannerDraftRequest(suggestions=[item()]).version is None


@pytest.mark.parametrize("payload", [
    {"suggestions": []},                                   # phải còn ít nhất 1 gợi ý (muốn bỏ hết thì hủy draft)
    {"suggestions": [item()] * 21},                        # tối đa 20
    {"suggestions": [item("")]},                           # tiêu đề rỗng
    {"suggestions": [item("x" * 201)]},                    # tiêu đề quá dài
    {"suggestions": [item(due_date="31/12/2026")]},        # sai định dạng ngày
    {"suggestions": [item(extra="x")]},                    # trường lạ
    {"suggestions": [item()], "version": 0},               # version >= 1
    {"suggestions": [item()], "version": "2"},             # version phải là số nguyên (strict)
    {"suggestions": [item()], "status": "APPROVED"},       # không cho đổi status qua PATCH
    {},
])
def test_invalid_update_request(payload):
    with pytest.raises(ValidationError):
        UpdatePlannerDraftRequest(**payload)


# ---- đăng ký route, không đụng code người khác ----
def test_routes_registered_in_main():
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "from app.api import planner_drafts as planner_drafts_api" in main
    assert "app.include_router(planner_drafts_api.router)" in main


def test_router_paths_match_api_contract():
    src = (ROOT / "api" / "planner_drafts.py").read_text(encoding="utf-8")
    assert 'prefix="/ai/planner/drafts"' in src
    assert '@router.patch("/{draft_id}")' in src
    assert '@router.post("/{draft_id}/discard")' in src


def test_service_never_touches_tasks():
    src = (ROOT / "services" / "planner_draft_service.py").read_text(encoding="utf-8")
    assert "models.task" not in src and "Task(" not in src and "draft_created_tasks" not in src
