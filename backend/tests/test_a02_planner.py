"""A02: Planner input, access control, draft persistence, and Gemini request compatibility."""
from datetime import datetime, timezone
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.adapter import AIResult
from app.ai.config import from_mapping
from app.ai.providers import build_request
from app.database.db import Base
from app.models.ai_draft import AIDraft
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.task import Task
from app.models.user import User
from app.schemas.planner import PlannerOutput, PlannerRequest
from app.services import planner_service


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def world(db):
    owner = User(
        email="owner@example.com",
        password_hash="hash",
        display_name="Owner",
    )
    member = User(
        email="member@example.com",
        password_hash="hash",
        display_name="Member",
    )
    db.add_all([owner, member])
    db.flush()

    project = Project(
        name="Planner project",
        timezone="Asia/Ho_Chi_Minh",
        created_by=owner.id,
    )
    db.add(project)
    db.flush()
    db.add_all(
        [
            ProjectMember(
                project_id=project.id,
                user_id=owner.id,
                role="OWNER",
            ),
            ProjectMember(
                project_id=project.id,
                user_id=member.id,
                role="MEMBER",
            ),
        ]
    )
    db.commit()
    return {"owner": owner, "member": member, "project": project}


class FakeAdapter:
    def __init__(self):
        self.calls = []

    def complete_json(self, feature, system, user, schema, **kwargs):
        self.calls.append((feature, system, user, schema, kwargs))
        return AIResult(
            data=schema.model_validate(
                {
                    "items": [
                        {
                            "title": "Thiết kế kiến trúc",
                            "description": "Chốt phạm vi kỹ thuật.",
                            "due_date": "2026-12-01",
                        }
                    ]
                }
            ),
            request_id="request-test-01",
            feature=feature,
            latency_ms=12,
            attempts=1,
        )


def test_planner_request_validation_and_output_schema():
    request = PlannerRequest(
        project_id=1,
        goal="  Xây dựng cổng quản lý dự án  ",
        scope="  Web và API  ",
    )
    assert request.goal == "Xây dựng cổng quản lý dự án"
    assert request.scope == "Web và API"

    with pytest.raises(ValidationError):
        PlannerRequest(project_id=1, goal="short")
    with pytest.raises(ValidationError):
        PlannerRequest(project_id=1, goal="X" * 10, scope="S" * 1001)
    with pytest.raises(ValidationError):
        PlannerOutput(items=[])
    with pytest.raises(ValidationError):
        PlannerOutput(items=[{"title": "T", "due_date": "01/12/2026"}])


def test_owner_saves_validated_draft_without_creating_tasks(db, world, monkeypatch):
    fake_adapter = FakeAdapter()
    monkeypatch.setattr(
        planner_service,
        "get_ai_adapter",
        lambda: fake_adapter,
    )
    request = PlannerRequest(
        project_id=world["project"].id,
        goal="Xây dựng cổng quản lý dự án",
        scope="Web và API",
    )

    result = planner_service.create_planner_draft(db, world["owner"], request)

    draft = db.get(AIDraft, result["draft_id"])
    assert result["type"] == "PROJECT_PLAN"
    assert result["status"] == "DRAFT"
    assert result["version"] == 1
    assert result["request_id"] == "request-test-01"
    assert result["suggestions"] == [
        {
            "title": "Thiết kế kiến trúc",
            "description": "Chốt phạm vi kỹ thuật.",
            "due_date": "2026-12-01",
        }
    ]
    assert draft.input_payload == {"goal": request.goal, "scope": request.scope}
    assert draft.draft_payload == {"items": result["suggestions"]}
    assert db.scalar(select(func.count()).select_from(Task)) == 0
    assert fake_adapter.calls[0][0] == "PLANNER"


def test_member_cannot_call_planner_or_spend_ai_request(db, world, monkeypatch):
    fake_adapter = FakeAdapter()
    monkeypatch.setattr(
        planner_service,
        "get_ai_adapter",
        lambda: fake_adapter,
    )
    request = PlannerRequest(
        project_id=world["project"].id,
        goal="Xây dựng cổng quản lý dự án",
    )

    with pytest.raises(HTTPException) as error:
        planner_service.create_planner_draft(db, world["member"], request)

    assert error.value.status_code == 403
    assert fake_adapter.calls == []
    assert db.scalar(select(func.count()).select_from(AIDraft)) == 0


def test_archived_project_cannot_create_planner_draft(db, world, monkeypatch):
    fake_adapter = FakeAdapter()
    monkeypatch.setattr(
        planner_service,
        "get_ai_adapter",
        lambda: fake_adapter,
    )
    world["project"].archived_at = datetime.now(timezone.utc)
    db.commit()
    request = PlannerRequest(
        project_id=world["project"].id,
        goal="Xây dựng cổng quản lý dự án",
    )

    with pytest.raises(HTTPException) as error:
        planner_service.create_planner_draft(db, world["owner"], request)

    assert error.value.status_code == 409
    assert fake_adapter.calls == []


def test_gemini_openai_compatible_request_uses_google_endpoint():
    config = from_mapping(
        {
            "AI_PROVIDER": "openai_compatible",
            "AI_API_KEY": "test-key-not-a-real-secret",
            "AI_MODEL": "gemini-3.8-flash",
            "AI_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai",
        }
    )

    request = build_request(config, "planner system", "planner input")

    assert request.url == (
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    )
    assert request.headers["authorization"] == "Bearer test-key-not-a-real-secret"
