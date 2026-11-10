"""B03: nghiệp vụ User — đăng ký, xác thực mật khẩu, cập nhật hồ sơ.

- Email: trim + lowercase, UNIQUE.
- Mật khẩu: hash bằng bcrypt (đã có trong requirements.txt), tối đa 72 byte.
- Sai email hay sai mật khẩu đều trả cùng một lỗi 401 để không lộ email nào đã đăng ký.
"""
from datetime import timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import security
from app.models.user import User
from app.repositories import user_repository

_dummy_hash: Optional[str] = None


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _get_dummy_hash() -> str:
    """Hash giả để thời gian phản hồi khi email không tồn tại gần bằng khi sai mật khẩu."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = security.hash_password("dummy-password-for-timing")
    return _dummy_hash


def register(db: Session, *, email: str, password: str, display_name: str) -> User:
    email = normalize_email(email)
    display_name = display_name.strip()
    if not 1 <= len(display_name) <= 100:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Tên hiển thị phải từ 1 đến 100 ký tự")

    if user_repository.get_by_email(db, email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email đã được sử dụng")

    try:
        password_hash = security.hash_password(password)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    try:
        return user_repository.create(
            db, email=email, password_hash=password_hash, display_name=display_name
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email đã được sử dụng")


def authenticate(db: Session, *, email: str, password: str) -> User:
    user = user_repository.get_by_email(db, normalize_email(email))
    password_ok = security.verify_password(
        password, user.password_hash if user else _get_dummy_hash()
    )
    if user is None or not password_ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email hoặc mật khẩu không đúng")
    return user


def update_display_name(db: Session, user: User, display_name: str) -> User:
    display_name = display_name.strip()
    if not 1 <= len(display_name) <= 100:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Tên hiển thị phải từ 1 đến 100 ký tự")
    return user_repository.update_display_name(db, user, display_name)


def user_to_dict(user: User) -> dict:
    """Dữ liệu user trả ra API. Tuyệt đối không có password_hash."""
    created_at = user.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "created_at": created_at.astimezone(timezone.utc).isoformat(),
    }
