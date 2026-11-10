"""B11: DTO tạo task (không cần DB)."""
import importlib.util, json, sys
from pathlib import Path
import pytest
from pydantic import ValidationError

A = Path(__file__).resolve().parents[1] / "app"
spec = importlib.util.spec_from_file_location("task_schema_t", A / "schemas/task.py")
m = importlib.util.module_from_spec(spec); sys.modules["task_schema_t"] = m; spec.loader.exec_module(m)
Create = m.CreateTaskRequest


def test_minimal_and_trim():
    t = Create(title="  Viết API  ")
    assert t.title == "Viết API" and t.description is None and t.due_date is None and t.assignee_id is None


def test_assignee_id_is_integer():
    assert Create(title="a", assignee_id="12").assignee_id == 12
    assert Create(title="a", assignee_id="  ").assignee_id is None
    with pytest.raises(ValidationError):
        Create(title="a", assignee_id="not-an-id")


def test_title_bounds():
    for bad in ("", "   "):
        with pytest.raises(ValidationError):
            Create(title=bad)
    with pytest.raises(ValidationError):
        Create(title="x" * 201)
    assert Create(title="x" * 200)


def test_description_limit_and_blank_to_none():
    assert Create(title="a", description="  ").description is None
    with pytest.raises(ValidationError):
        Create(title="a", description="x" * 5001)


def test_due_date():
    assert Create(title="a", due_date="2026-12-31").due_date == "2026-12-31"
    assert Create(title="a", due_date="").due_date is None
    for bad in ("31/12/2026", "2026-02-30", "abc"):
        with pytest.raises(ValidationError):
            Create(title="a", due_date=bad)


def test_errors_json_serializable():
    with pytest.raises(ValidationError) as e:
        Create(title="", due_date="x")
    json.dumps(e.value.errors(include_url=False))
