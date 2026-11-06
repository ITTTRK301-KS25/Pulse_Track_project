"""Test B04: Session/Auth Service (dùng SQLite trong bộ nhớ, không cần MySQL).
Chạy từ thư mục backend:  python -m pytest tests/test_b04_auth_service.py
Cần B03 đã có trong repo (model User/UserSession, user_service).
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.db import Base
from app.models.user import UserSession
from app.services import auth_service, user_service


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def user(db):
    return user_service.register(db, email="a@example.com", password="12345678", display_name="A")


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def test_create_session_stores_only_token_hash_and_24h_expiry(db, user):
    token = auth_service.create_session(db, user)
    row = db.query(UserSession).one()
    assert row.token_hash == auth_service.hash_token(token)
    assert row.token_hash != token
    ttl = _utc(row.expires_at) - _utc(row.created_at)
    assert ttl == timedelta(hours=24)


def test_resolve_session_returns_user_and_session(db, user):
    token = auth_service.create_session(db, user)
    resolved_user, session = auth_service.resolve_session(db, token)
    assert resolved_user.id == user.id
    assert session.user_id == user.id


@pytest.mark.parametrize("token", [None, "", "token-khong-ton-tai"])
def test_resolve_session_rejects_missing_or_unknown_token(db, user, token):
    with pytest.raises(HTTPException) as e:
        auth_service.resolve_session(db, token)
    assert e.value.status_code == 401


def test_revoke_session_then_resolve_returns_401(db, user):
    token = auth_service.create_session(db, user)
    _, session = auth_service.resolve_session(db, token)
    auth_service.revoke_session(db, session)
    auth_service.revoke_session(db, session)  # gọi lại vẫn an toàn
    assert session.revoked_at is not None
    with pytest.raises(HTTPException) as e:
        auth_service.resolve_session(db, token)
    assert e.value.status_code == 401


def test_expired_session_returns_401(db, user):
    token = auth_service.create_session(db, user)
    row = db.query(UserSession).one()
    now = datetime.now(timezone.utc)
    row.created_at = now - timedelta(hours=48)
    row.expires_at = now - timedelta(hours=24)
    db.commit()
    with pytest.raises(HTTPException) as e:
        auth_service.resolve_session(db, token)
    assert e.value.status_code == 401
