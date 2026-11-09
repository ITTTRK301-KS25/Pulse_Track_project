import bcrypt
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import jwt

from app.core.config import settings

MAX_PASSWORD_BYTES = 72
_TOKEN_TYPE_CLAIM = "token_type"
_GENERATED_CLAIMS = frozenset({"exp", "iat", "jti", _TOKEN_TYPE_CLAIM})
_SUPPORTED_ALGORITHMS = frozenset({"HS256", "HS384", "HS512"})


def hash_password(password: str) -> str:
    validate_password(password)
    password_bytes = password.encode("utf-8")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def validate_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Mật khẩu phải có ít nhất 8 ký tự")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Mật khẩu tối đa {MAX_PASSWORD_BYTES} byte")
    return password


def verify_password(password: str, password_hash: str) -> bool:
    try:
        if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
            return False
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (TypeError, ValueError):
        return False


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _signing_config() -> tuple[str, str]:
    secret_key = settings.SECRET_KEY
    algorithm = settings.ALGORITHM
    if len(secret_key.encode("utf-8")) < 32:
        raise ValueError("SECRET_KEY must be at least 32 bytes")
    if algorithm not in _SUPPORTED_ALGORITHMS:
        raise ValueError("ALGORITHM must be one of HS256, HS384, or HS512")
    return secret_key, algorithm


def _create_token(data: Mapping[str, Any], *, token_type: str, expires_in: int) -> str:
    if not isinstance(data, Mapping) or any(not isinstance(key, str) for key in data):
        raise ValueError("Token data must be a mapping with string keys")
    if not isinstance(data.get("sub"), str) or not data["sub"].strip():
        raise ValueError("Token subject (sub) must be a non-empty string")
    if _GENERATED_CLAIMS.intersection(data):
        raise ValueError("Token data cannot override generated security claims")
    if expires_in <= 0:
        raise ValueError("Token lifetime must be greater than zero")

    now = datetime.now(timezone.utc)
    payload = dict(data)
    payload.update({
        "iat": now,
        "exp": now + timedelta(minutes=expires_in),
        "jti": secrets.token_urlsafe(16),
        _TOKEN_TYPE_CLAIM: token_type,
    })
    secret_key, algorithm = _signing_config()
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def create_access_token(data: Mapping[str, Any]) -> str:
    return _create_token(
        data,
        token_type="access",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )


def create_refresh_token(data: Mapping[str, Any]) -> str:
    return _create_token(
        data,
        token_type="refresh",
        expires_in=settings.REFRESH_TOKEN_EXPIRE_MINUTES,
    )


def _decode_token(token: str, *, expected_type: str) -> dict[str, Any]:
    if not isinstance(token, str) or not token.strip():
        raise jwt.InvalidTokenError("Token must be a non-empty string")

    secret_key, algorithm = _signing_config()
    payload = jwt.decode(
        token,
        secret_key,
        algorithms=[algorithm],
        options={"require": ["exp", "iat", "jti", "sub", _TOKEN_TYPE_CLAIM]},
    )
    if not isinstance(payload.get("sub"), str) or not payload["sub"].strip():
        raise jwt.InvalidTokenError("Token subject (sub) must be a non-empty string")
    if not isinstance(payload.get("jti"), str) or not payload["jti"]:
        raise jwt.InvalidTokenError("Token ID (jti) is invalid")
    if payload.get(_TOKEN_TYPE_CLAIM) != expected_type:
        raise jwt.InvalidTokenError(f"Expected a {expected_type} token")
    return payload


def decode_access_token(token: str) -> dict[str, Any]:
    return _decode_token(token, expected_type="access")


def decode_refresh_token(token: str) -> dict[str, Any]:
    return _decode_token(token, expected_type="refresh")