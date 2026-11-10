"""B10: quy tắc OWNER cuối cùng + DTO đổi vai trò (không cần DB)."""
import importlib.util, sys
from pathlib import Path
import pytest
from pydantic import ValidationError

A = Path(__file__).resolve().parents[1] / "app"
def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, A / rel); m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m; spec.loader.exec_module(m); return m

rules = load("member_rules_t", "core/member_rules.py")
upd = load("member_update_t", "schemas/member_update.py")


def test_last_owner_cannot_be_demoted_or_removed():
    assert rules.would_leave_no_owner(1, "OWNER", "MEMBER")
    assert rules.would_leave_no_owner(1, "OWNER", "VIEWER")
    assert rules.would_leave_no_owner(1, "OWNER", None)


def test_other_owner_exists_is_allowed():
    assert not rules.would_leave_no_owner(2, "OWNER", "MEMBER")
    assert not rules.would_leave_no_owner(2, "OWNER", None)


def test_non_owner_changes_never_blocked():
    assert not rules.would_leave_no_owner(1, "MEMBER", "VIEWER")
    assert not rules.would_leave_no_owner(1, "VIEWER", None)
    assert not rules.would_leave_no_owner(1, "MEMBER", "OWNER")
    assert not rules.would_leave_no_owner(1, "OWNER", "OWNER")   # giữ nguyên vai trò


def test_role_dto():
    assert upd.ChangeRoleRequest(role=" viewer ").role == "VIEWER"
    for bad in ["", "ADMIN", "x"]:
        with pytest.raises(ValidationError):
            upd.ChangeRoleRequest(role=bad)
