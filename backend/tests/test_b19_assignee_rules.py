"""B19: quy tắc assignee thuần + kiểm tra việc dùng chung và không có endpoint riêng (không cần DB)."""
import importlib.util
import re
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, APP / rel)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


R = load("assignee_rules_t", "core/assignee_rules.py")


@pytest.mark.parametrize("role,ok", [
    ("OWNER", True), ("MEMBER", True),
    ("VIEWER", False),      # chỉ đọc
    (None, False),          # người ngoài / đã bị xóa / không tồn tại -> không có dòng thành viên
    ("owner", False), ("", False), ("ADMIN", False),
])
def test_is_assignable(role, ok):
    assert R.is_assignable(role) is ok


def test_none_assignee_skips_check():
    assert R.needs_check(None) is False
    assert R.needs_check(1) is True
    assert R.needs_check(0) is True   # id 0 vẫn là "có gán", sẽ bị từ chối vì không có thành viên


def test_message_is_vietnamese_contract():
    assert R.ASSIGNEE_MSG == "Người thực hiện phải là OWNER hoặc MEMBER của dự án"


def test_validator_reused_in_b11_b12_b14():
    for rel in ("services/task_service.py", "services/task_update_service.py", "services/subtask_service.py"):
        src = (APP / rel).read_text(encoding="utf-8")
        assert "from app.services.assignee_service import validate_assignee" in src, rel
        assert "validate_assignee(" in src, rel


def test_no_separate_assignee_endpoint():
    for f in (APP / "api").glob("*.py"):
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r'\s*@router\.\w+\(\s*["\']([^"\']*)', line)
            if m:
                assert "assignee" not in m.group(1).lower(), f"{f.name}: {line.strip()}"
    assert not (APP / "api" / "assignee.py").exists()
