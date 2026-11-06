"""B04: Session/Auth Service.

- create_session: sinh token ngẫu nhiên, chỉ lưu SHA-256 của token, expires_at = +24h.
- resolve_session: từ token trong cookie tìm ra (User, UserSession); thiếu/sai/hết hạn/đã revoke -> 401.
- revoke_session: đánh dấu revoked_at khi đăng xuất (gọi lại nhiều lần vẫn an toàn).
Thời gian phiên lấy từ core/auth_cookie.py (SESSION_TTL_HOURS, mặc định 24).
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth_cookie import SESSION_TTL_HOURS
from app.models.user import User, UserSession
from app.repositories import session_repository, user_repository

TOKEN_BYTES = 32
LAST_ACTIVE_UPDATE_SECONDS = 60  # chỉ ghi last_active_at tối đa mỗi 60 giây để tránh ghi DB ở mọi request


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """MySQL trả datetime không múi giờ; giá trị lưu luôn là UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, message)


def create_session(db: Session, user: User) -> str:
    """Tạo phiên mới và trả token thô (chỉ trả cho cookie, không lưu vào DB)."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    now = _now()
    session_repository.create(
        db,
        user_id=user.id,
        token_hash=hash_token(token),
        now=now,
        expires_at=now + timedelta(hours=SESSION_TTL_HOURS),
    )
    return token


def resolve_session(db: Session, token: Optional[str]) -> tuple[User, UserSession]:
    if not token:
        raise _unauthorized("Chưa đăng nhập")

    session = session_repository.get_by_token_hash(db, hash_token(token))
    if session is None:
        raise _unauthorized("Phiên đăng nhập không hợp lệ")
    if session.revoked_at is not None:
        raise _unauthorized("Phiên đăng nhập đã bị thu hồi")

    now = _now()
    if _as_utc(session.expires_at) <= now:
        raise _unauthorized("Phiên đăng nhập đã hết hạn")

    user = user_repository.get_by_id(db, session.user_id)
    if user is None:
        raise _unauthorized("Phiên đăng nhập không hợp lệ")

    if (now - _as_utc(session.last_active_at)).total_seconds() >= LAST_ACTIVE_UPDATE_SECONDS:
        session_repository.touch(db, session, now)
    return user, session


def revoke_session(db: Session, session: UserSession) -> None:
    if session.revoked_at is None:
        session_repository.revoke(db, session, _now())
