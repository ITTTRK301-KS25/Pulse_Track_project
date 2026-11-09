import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jwt
import pytest

from app.core import security


@pytest.mark.parametrize(
    "password",
    ["short", "x" * 73, "é" * 37],
)
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


@pytest.fixture(autouse=True)
def use_test_signing_key(monkeypatch):
    monkeypatch.setattr(security.settings, "SECRET_KEY", "s" * 32)


def test_access_token_has_required_claims_and_round_trips():
    token = security.create_access_token({"sub": "user-123"})

    payload = security.decode_access_token(token)

    assert payload["sub"] == "user-123"
    assert payload["token_type"] == "access"
    assert payload["exp"] > payload["iat"]
    assert payload["jti"]


def test_refresh_token_has_distinct_type_and_lifetime(monkeypatch):
    monkeypatch.setattr(security.settings, "REFRESH_TOKEN_EXPIRE_MINUTES", 60)
    token = security.create_refresh_token({"sub": "user-123"})
    payload = security.decode_refresh_token(token)

    assert payload["token_type"] == "refresh"
    assert payload["exp"] - payload["iat"] == 60 * 60
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_access_token(token)


@pytest.mark.parametrize("data", [{}, {"sub": ""}, {"sub": 123}])
def test_token_creation_requires_nonempty_string_subject(data):
    with pytest.raises(ValueError):
        security.create_access_token(data)


@pytest.mark.parametrize("claim", ["exp", "iat", "jti", "token_type"])
def test_token_creation_rejects_reserved_claims(claim):
    with pytest.raises(ValueError):
        security.create_access_token({"sub": "user-123", claim: "caller-value"})


def test_token_decoder_rejects_expired_token(monkeypatch):
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "user-123",
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
            "jti": "expired-token",
            "token_type": "access",
        },
        security.settings.SECRET_KEY,
        algorithm=security.settings.ALGORITHM,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        security.decode_access_token(token)


@pytest.mark.parametrize("token", ["", "not-a-jwt"])
def test_token_decoder_rejects_empty_or_malformed_token(token):
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_access_token(token)
