"""B13: quy tắc lưu trữ/khôi phục (không cần DB)."""
import importlib.util, sys
from pathlib import Path
import pytest

p = Path(__file__).resolve().parents[1] / "app/core/archive_rules.py"
spec = importlib.util.spec_from_file_location("archive_rules_t", p)
m = importlib.util.module_from_spec(spec); sys.modules["archive_rules_t"] = m; spec.loader.exec_module(m)
f = m.next_archive_state


def test_archive_active_task():
    assert f(False, "archive") == (True, "ARCHIVE")


def test_restore_archived_task():
    assert f(True, "restore") == (True, "RESTORE")


def test_repeated_actions_are_noops():
    assert f(True, "archive") == (False, None)
    assert f(False, "restore") == (False, None)


def test_bad_action():
    with pytest.raises(ValueError):
        f(False, "delete")
