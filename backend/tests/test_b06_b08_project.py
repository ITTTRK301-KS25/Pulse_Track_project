"""B06/B08: test phần thuần (DTO dự án, ma trận quyền). Không cần DB hay FastAPI."""
import importlib.util, json, sys
from pathlib import Path
import pytest
from pydantic import ValidationError

A = Path(__file__).resolve().parents[1] / "app"
def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, A / rel); m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m; spec.loader.exec_module(m); return m

proj = load("project_schema_t", "schemas/project.py")


def test_default_timezone_and_trim():
    p = proj.ProjectCreate(name="  Dự án  ")
    assert p.name == "Dự án" and p.timezone == "Asia/Ho_Chi_Minh"


@pytest.mark.parametrize("tz", ["Asia/Tokyo", "UTC", "America/New_York"])
def test_valid_timezone(tz):
    assert proj.ProjectCreate(name="x", timezone=tz).timezone == tz


@pytest.mark.parametrize("tz", ["Mars/Base", "../etc/passwd", "", "/etc/localtime"])
def test_invalid_timezone(tz):
    with pytest.raises(ValidationError):
        proj.ProjectCreate(name="x", timezone=tz)


def test_project_create_fields_match_contract():
    for bad in ["", "   ", "x" * 151]:
        with pytest.raises(ValidationError):
            proj.ProjectCreate(name=bad)
    with pytest.raises(ValidationError):
        proj.ProjectCreate(name="x", description="d" * 2001)
    project = proj.ProjectCreate(name="x", description="description", timezone="UTC")
    assert project.model_dump() == {
        "name": "x",
        "description": "description",
        "timezone": "UTC",
    }


def test_update_partial_and_timezone_locked():
    u = proj.ProjectUpdate(name=" Mới ")
    assert u.model_fields_set == {"name"} and u.name == "Mới"
    with pytest.raises(ValidationError):
        proj.ProjectUpdate(timezone="Asia/Tokyo")
    with pytest.raises(ValidationError):
        proj.ProjectUpdate(name=None)


def test_errors_are_json_serializable():
    """Handler 422 của nhóm trả thẳng exc.errors(); phải chuyển được sang JSON."""
    try:
        proj.ProjectCreate(name="", timezone="Mars/Base")
    except ValidationError as e:
        json.dumps(e.errors())
        assert all("ctx" not in x for x in e.errors())
