"""B03: truy cập dữ liệu bảng users. Không chứa logic nghiệp vụ."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get_by_id(db: Session, user_id: str) -> Optional[User]:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> Optional[User]:
    return db.scalar(select(User).where(User.email == email))


def create(db: Session, *, email: str, password_hash: str, display_name: str) -> User:
    """Thêm user mới. Email trùng sẽ ném IntegrityError (do UNIQUE) để service xử lý."""
    user = User(email=email, password_hash=password_hash, display_name=display_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_display_name(db: Session, user: User, display_name: str) -> User:
    user.display_name = display_name
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user
