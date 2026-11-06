"""Test B03: User model/repository/service (dùng SQLite trong bộ nhớ, không cần MySQL).
Chạy từ thư mục backend:  python -m pytest tests/test_b03_user_service.py
"""
import os
import sys
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
from app.models.user import User
from app.services import user_service


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


def _register(db, email="Alice@Example.com", password="12345678", name="Alice"):
    return user_service.register(db, email=email, password=password, display_name=name)


def test_register_normalizes_email_and_hashes_password(db):
    user = _register(db, email="  Alice@Example.COM ")
    assert user.email == "alice@example.com"
    assert user.password_hash != "12345678"
    assert user.password_hash.startswith("$2")


def test_register_duplicate_email_returns_409_even_with_different_case(db):
    _register(db)
    with pytest.raises(HTTPException) as e:
        _register(db, email=" ALICE@example.com ")
    assert e.value.status_code == 409


def test_authenticate_success(db):
    created = _register(db)
    assert user_service.authenticate(db, email="ALICE@example.com", password="12345678").id == created.id


@pytest.mark.parametrize("email,password", [("alice@example.com", "wrong-pass"), ("nobody@example.com", "12345678")])
def test_authenticate_failure_returns_same_401(db, email, password):
    _register(db)
    with pytest.raises(HTTPException) as e:
        user_service.authenticate(db, email=email, password=password)
    assert e.value.status_code == 401
    assert e.value.detail == "Email hoặc mật khẩu không đúng"


def test_update_display_name(db):
    user = _register(db)
    updated = user_service.update_display_name(db, user, "  Minh  ")
    assert updated.display_name == "Minh"
    with pytest.raises(HTTPException) as e:
        user_service.update_display_name(db, user, "   ")
    assert e.value.status_code == 422


def test_user_to_dict_never_exposes_password_hash(db):
    data = user_service.user_to_dict(_register(db))
    assert set(data) == {"id", "email", "display_name", "created_at"}
