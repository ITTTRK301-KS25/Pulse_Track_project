import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.core import security


@pytest.mark.parametrize("password", ["short", "x" * 73, "é" * 37])
def test_validate_password_rejects_invalid_lengths(password):
    with pytest.raises(ValueError):
        security.validate_password(password)


def test_password_hash_and_verification():
    password_hash = security.hash_password("correct-horse")

    assert security.verify_password("correct-horse", password_hash)
    assert not security.verify_password("wrong-password", password_hash)
    assert not security.verify_password("x" * 73, password_hash)
    assert not security.verify_password("correct-horse", "invalid-hash")


def test_session_tokens_are_random_and_stored_as_hashes():
    first = security.generate_session_token()
    second = security.generate_session_token()

    assert first != second
    assert len(security.hash_session_token(first)) == 64
    assert security.hash_session_token(first) != first
