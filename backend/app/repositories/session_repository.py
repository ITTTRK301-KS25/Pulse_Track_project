"""B04: truy cập dữ liệu bảng user_sessions. Không chứa logic nghiệp vụ."""
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import UserSession


def create(db: Session, *, user_id: int, token_hash: str, now: datetime, expires_at: datetime) -> UserSession:
    session = UserSession(
        user_id=user_id,
        token_hash=token_hash,
        created_at=now,
        last_active_at=now,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_by_token_hash(db: Session, token_hash: str) -> Optional[UserSession]:
    return db.scalar(select(UserSession).where(UserSession.token_hash == token_hash))


def touch(db: Session, session: UserSession, now: datetime) -> None:
    session.last_active_at = now
    db.commit()


def revoke(db: Session, session: UserSession, now: datetime) -> None:
    session.revoked_at = now
    db.commit()
