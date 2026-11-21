import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.ai.adapter import AICallRecord
from app.database.db import Base
from app.models.ai_call_log import AICallLog
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User, UserSession
from app.services import ai_call_log_service


def test_ai_call_recorder_persists_only_safe_metadata(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    test_sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(ai_call_log_service, "SessionLocal", test_sessions)

    record = AICallRecord(
        request_id="req-123",
        type="REPORT",
        status="TIMEOUT",
        error_code="AI_TIMEOUT",
        latency_ms=3000,
        attempts=2,
        is_mock=False,
    )
    ai_call_log_service.make_ai_call_recorder(12, 34)(record)

    with test_sessions() as db:
        saved = db.scalar(select(AICallLog))
        assert saved is not None
        assert (
            saved.project_id,
            saved.actor_id,
            saved.request_id,
            saved.type,
            saved.status,
            saved.error_code,
        ) == (12, 34, "req-123", "REPORT", "TIMEOUT", "AI_TIMEOUT")

    assert set(AICallLog.__table__.columns.keys()) == {
        "id",
        "project_id",
        "actor_id",
        "request_id",
        "type",
        "status",
        "error_code",
        "created_at",
    }
    Base.metadata.drop_all(engine)
    engine.dispose()
