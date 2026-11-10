"""B12: DTO sửa task + quy tắc sinh sự kiện lịch sử/khóa lạc quan (không cần DB)."""
import importlib.util, json, sys
from pathlib import Path
import pytest
from pydantic import ValidationError

A = Path(__file__).resolve().parents[1] / "app"
def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, A / rel); m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m; spec.loader.exec_module(m); return m

# schemas.task_update import "app.schemas.task": nạp giả để test chạy độc lập
import types
pkg = types.ModuleType("app"); pkg.__path__ = []; sys.modules.setdefault("app", pkg)
sp = types.ModuleType("app.schemas"); sp.__path__ = []; sys.modules.setdefault("app.schemas", sp)
sys.modules["app.schemas.task"] = load("task_schema_t2", "schemas/task.py")
U = load("task_update_t", "schemas/task_update.py").UpdateTaskRequest
R = load("task_rules_t", "core/task_rules.py")

CUR = {"title": "A", "description": None, "status": "TODO", "due_date": None, "assignee_id": None, "parent_id": None}


def test_requires_version_and_one_field():
    with pytest.raises(ValidationError):
        U(title="x")
    with pytest.raises(ValidationError):
        U(version=1)
    with pytest.raises(ValidationError):
        U(version=0, title="x")


def test_status_and_null_rules():
    assert U(version=1, status="in_progress").status == "IN_PROGRESS"
    for bad in ("DOING", None):
        with pytest.raises(ValidationError):
            U(version=1, status=bad)
    with pytest.raises(ValidationError):
        U(version=1, title=None)


def test_explicit_null_clears_but_absent_is_kept():
    u = U(version=2, due_date=None, assignee_id=None)
    assert u.requested() == {"due_date": None, "assignee_id": None}
    assert U(version=2, title="B").requested() == {"title": "B"}


def test_errors_json_serializable():
    with pytest.raises(ValidationError) as e:
        U(version=1, status="x", due_date="bad")
    json.dumps(e.value.errors(include_url=False))


def test_only_real_changes_produce_events():
    assert R.changed_fields(CUR, {"status": "TODO", "title": "A"}) == {}
    ch = R.changed_fields(CUR, {"status": "DONE", "title": "A"})
    assert ch == {"status": "DONE"}
    assert R.build_events(CUR, ch) == [("STATUS_CHANGE", {"status": "TODO"}, {"status": "DONE"})]


def test_event_types_and_grouping():
    ch = R.changed_fields(CUR, {"title": "B", "description": "d", "due_date": "2026-12-01", "assignee_id": "u1"})
    ev = R.build_events(CUR, ch)
    assert [e[0] for e in ev] == ["DUE_CHANGE", "ASSIGNEE_CHANGE", "DETAIL_CHANGE"]
    assert ev[2][1] == {"title": "A", "description": None} and ev[2][2] == {"title": "B", "description": "d"}


def test_clear_due_date_is_a_change():
    cur = dict(CUR, due_date="2026-12-01")
    ch = R.changed_fields(cur, {"due_date": None})
    assert R.build_events(cur, ch) == [("DUE_CHANGE", {"due_date": "2026-12-01"}, {"due_date": None})]


def test_stale_version():
    assert R.is_stale(3, 2) and not R.is_stale(3, 3)
