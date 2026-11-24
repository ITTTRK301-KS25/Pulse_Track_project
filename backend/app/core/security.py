import bcrypt
import hashlib
import secrets
import re

MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    validate_password(password)
    password_bytes = password.encode("utf-8")

    return bcrypt.hashpw(
        password_bytes, bcrypt.gensalt()
    ).decode("utf-8")


def validate_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Mật khẩu phải có ít nhất 8 ký tự")

    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Mật khẩu tối đa {MAX_PASSWORD_BYTES} byte")

    if re.search(r"\s", password):
        raise ValueError("Mật khẩu không được chứa khoảng trắng")

    if not re.search(r"[A-Z]", password):
        raise ValueError("Mật khẩu phải có ít nhất 1 chữ hoa")

    if not re.search(r"[a-z]", password):
        raise ValueError("Mật khẩu phải có ít nhất 1 chữ thường")

    if not re.search(r"[0-9]", password):
        raise ValueError("Mật khẩu phải có ít nhất 1 chữ số")

    if not re.search(r"[^a-zA-Z0-9\s]", password):
        raise ValueError("Mật khẩu phải có ít nhất 1 ký tự đặc biệt")

    return password


def verify_password(password: str, password_hash: str) -> bool:
    try:
        if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
            return False

        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8")
        )

    except (TypeError, ValueError):
        return False


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()