"""Test phần thuần Python của B03–B05 (không cần DB/FastAPI)."""
import importlib.util
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1] / "app"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


auth = _load("auth_schemas", "schemas/auth.py")


def test_email_is_trimmed_and_lowercased():
    r = auth.RegisterRequest(email="  Alice@Example.COM ", password="12345678", display_name="A")
    assert r.email == "alice@example.com"


@pytest.mark.parametrize("bad", ["abc", "a@b", "@x.com", "a b@x.com", ""])
def test_invalid_email_rejected(bad):
    with pytest.raises(ValidationError):
        auth.RegisterRequest(email=bad, password="12345678", display_name="A")


def test_password_rules():
    with pytest.raises(ValidationError):
        auth.RegisterRequest(email="a@b.co", password="1234567", display_name="A")
    with pytest.raises(ValidationError):
        auth.RegisterRequest(email="a@b.co", password="x" * 73, display_name="A")
    auth.RegisterRequest(email="a@b.co", password="x" * 72, display_name="A")


def test_display_name_rules():
    assert auth.UpdateMeRequest(display_name="  Minh ").display_name == "Minh"
    for bad in ["", "   ", "x" * 101]:
        with pytest.raises(ValidationError):
            auth.UpdateMeRequest(display_name=bad)


def test_login_email_normalized():
    assert auth.LoginRequest(email=" A@B.co ", password="x").email == "a@b.co"


