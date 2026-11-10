"""B09: tra cứu tên tài khoản trước khi thêm thành viên."""
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.db import Base
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User
from app.services import member_service


@pytest.fixture()
def project_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    owner = User(email="owner@example.com", password_hash="hash", display_name="Owner")
    target = User(email="member@example.com", password_hash="hash", display_name="Member")
    session.add_all([owner, target])
    session.flush()
    project = Project(name="Project", created_by=owner.id)
    session.add(project)
    session.flush()
    session.add(ProjectMember(project_id=project.id, user_id=owner.id, role="OWNER"))
    session.commit()

    try:
        yield session, owner, target, project
    finally:
        session.close()
        engine.dispose()


def test_lookup_account_returns_name_for_normalized_email(project_db):
    db, owner, target, project = project_db

    result = member_service.lookup_account(
        db, owner, project.id, "  MEMBER@EXAMPLE.COM "
    )

    assert result == {
        "email": target.email,
        "display_name": target.display_name,
    }


def test_lookup_account_returns_404_for_unknown_email(project_db):
    db, owner, _, project = project_db

    with pytest.raises(HTTPException) as error:
        member_service.lookup_account(db, owner, project.id, "unknown@example.com")

    assert error.value.status_code == 404


def test_lookup_account_is_owner_only(project_db):
    db, _, target, project = project_db
    db.add(ProjectMember(project_id=project.id, user_id=target.id, role="MEMBER"))
    db.commit()

    with pytest.raises(HTTPException) as error:
        member_service.lookup_account(db, target, project.id, "owner@example.com")

    assert error.value.status_code == 403


def test_lookup_account_is_unavailable_for_archived_project(project_db):
    db, owner, target, project = project_db
    from datetime import datetime, timezone

    project.archived_at = datetime.now(timezone.utc)
    db.commit()

    with pytest.raises(HTTPException) as error:
        member_service.lookup_account(db, owner, project.id, target.email)

    assert error.value.status_code == 409
