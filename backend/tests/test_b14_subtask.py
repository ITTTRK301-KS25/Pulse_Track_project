"""B14: quy tắc subtask một cấp + DTO đổi trạng thái (không cần DB)."""
import importlib.util, json, sys
from pathlib import Path
import pytest
from pydantic import ValidationError

A = Path(__file__).resolve().parents[1] / "app"
def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, A / rel); m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m; spec.loader.exec_module(m); return m

R = load("subtask_rules_t", "core/subtask_rules.py")
S = load("task_status_t", "schemas/task_status.py").SetStatusRequest


def test_normal_parent_is_ok():
    assert R.check_parent(None, None) is None


def test_parent_is_subtask_is_rejected():
    assert R.check_parent("some-parent-id", None) == R.PARENT_IS_SUBTASK


def test_archived_parent_is_rejected():
    assert R.check_parent(None, "2026-11-10T00:00:00Z") == R.PARENT_ARCHIVED


def test_subtask_check_comes_before_archived():
    assert R.check_parent("p", "2026-11-10") == R.PARENT_IS_SUBTASK


def test_status_request():
    assert S(status="done", version=2).status == "DONE"
    for bad in ({"status": "DOING", "version": 1}, {"status": "DONE", "version": 0}, {"status": "DONE"}, {"version": 1}):
        with pytest.raises(ValidationError):
            S(**bad)


def test_status_errors_json_serializable():
    with pytest.raises(ValidationError) as e:
        S(status="x", version=0)
    json.dumps(e.value.errors(include_url=False))
