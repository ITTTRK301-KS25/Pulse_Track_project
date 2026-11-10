import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.db import Base
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.member import AddMemberRequest
from app.services.member_service import add_member, list_members, lookup_user
from app.services.user_service import register


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(
        engine,
        "connect",
        lambda connection, _: connection.create_function("CHAR_LENGTH", 1, len),
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def project_owner(db):
    owner = register(
        db,
        email="owner@example.com",
        password="test-password",
        display_name="Owner",
    )
    project = Project(name="Project", timezone="UTC", created_by=owner.id)
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=owner.id, role="OWNER"))
    db.commit()
    return project, owner


def test_add_existing_user_with_normalized_email(db, project_owner):
    project, owner = project_owner
    target = register(
        db,
        email="member@example.com",
        password="test-password",
        display_name="Member",
    )
    request = AddMemberRequest(email="  MEMBER@Example.COM  ", role="member")

    result = add_member(
        db,
        owner,
        project.id,
        email=request.email,
        role=request.role,
    )

    assert result["user_id"] == target.id
    assert result["email"] == "member@example.com"
    assert result["display_name"] == "Member"
    assert result["role"] == "MEMBER"
    assert len(list_members(db, owner, project.id)) == 2


def test_add_member_returns_not_found_only_for_unknown_email(db, project_owner):
    project, owner = project_owner

    with pytest.raises(HTTPException) as error:
        add_member(
            db,
            owner,
            project.id,
            email="missing@example.com",
            role="MEMBER",
        )

    assert error.value.status_code == 404


def test_lookup_existing_user_uses_normalized_email(db, project_owner):
    project, owner = project_owner
    target = register(
        db,
        email="member@example.com",
        password="test-password",
        display_name="Member",
    )

    result = lookup_user(
        db,
        owner,
        project.id,
        " MEMBER@Example.COM ",
    )

    assert result == {
        "user_id": target.id,
        "email": target.email,
        "display_name": target.display_name,
    }


def test_lookup_unknown_user_returns_not_found(db, project_owner):
    project, owner = project_owner

    with pytest.raises(HTTPException) as error:
        lookup_user(db, owner, project.id, "missing@example.com")

    assert error.value.status_code == 404


def test_duplicate_member_returns_conflict(db, project_owner):
    project, owner = project_owner
    target = register(
        db,
        email="member@example.com",
        password="test-password",
        display_name="Member",
    )
    add_member(db, owner, project.id, email=target.email, role="MEMBER")

    with pytest.raises(HTTPException) as error:
        add_member(db, owner, project.id, email=target.email, role="VIEWER")

    assert error.value.status_code == 409
