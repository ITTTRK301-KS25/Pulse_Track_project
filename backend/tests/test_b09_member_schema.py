"""B09: test DTO thêm thành viên (không cần DB)."""
import importlib.util, json, sys
from pathlib import Path
import pytest
from pydantic import ValidationError

spec = importlib.util.spec_from_file_location("member_schema_t", Path(__file__).resolve().parents[1] / "app/schemas/member.py")
m = importlib.util.module_from_spec(spec); sys.modules["member_schema_t"] = m; spec.loader.exec_module(m)


def test_email_normalized_and_default_role():
    r = m.AddMemberRequest(email="  Ban@Example.COM ")
    assert r.email == "ban@example.com" and r.role == "MEMBER"


@pytest.mark.parametrize("bad", ["", "abc", "a@b", "@x.com", "a b@x.com"])
def test_bad_email(bad):
    with pytest.raises(ValidationError):
        m.AddMemberRequest(email=bad)


def test_role_validation():
    assert m.AddMemberRequest(email="a@b.co", role="viewer").role == "VIEWER"
    for bad in ["ADMIN", "", "owner2"]:
        with pytest.raises(ValidationError):
            m.AddMemberRequest(email="a@b.co", role=bad)


def test_errors_json_serializable():
    try:
        m.AddMemberRequest(email="x", role="z")
    except ValidationError as e:
        json.dumps(e.errors())
