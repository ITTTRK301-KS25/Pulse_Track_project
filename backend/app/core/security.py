import bcrypt
import hashlib
import secrets

MAX_PASSWORD_BYTES = 72


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
