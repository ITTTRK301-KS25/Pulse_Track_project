import os
from datetime import date
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.ai import errors as ai_errors
from app.services import weekly_report_service


def test_ai_failure_keeps_metrics_and_marks_preview_without_fabricated_narrative(monkeypatch):
    monkeypatch.setattr(weekly_report_service, "_preview_store", {})
    metrics = {
        "MET-01": 1,
        "MET-02": 2,
        "MET-03": 1,
        "MET-04": 0,
        "MET-05": 0,
        "MET-06": 0.0,
    }
    error = ai_errors.timeout()
    error.request_id = "request-timeout"
    adapter = MagicMock()
    adapter.complete_json.side_effect = error
    db = MagicMock()
    user = SimpleNamespace(id=5)
    project = SimpleNamespace(name="Project")

    with (
        patch.object(weekly_report_service.access, "get_project_and_role", return_value=(project, "OWNER")),
        patch.object(weekly_report_service, "calculate_weekly_metrics", return_value={
            "timezone": "Asia/Ho_Chi_Minh",
            "metrics": metrics,
            "warnings": [],
            "complete": True,
        }),
        patch.object(weekly_report_service, "get_ai_adapter", return_value=adapter),
        patch.object(weekly_report_service, "make_ai_call_recorder", return_value=MagicMock()),
    ):
        result = weekly_report_service.create_weekly_preview(
            db,
            user,
            project_id=7,
            week_start=date(2026, 11, 9),
        )

    assert result["metrics"][0]["value"] == 1
    assert result["ai_narrative"] is None
    assert result["is_mock"] is False
    assert result["label"] is None
    assert result["request_id"] == "request-timeout"
    assert result["ai_error"] == {
        "code": "AI_TIMEOUT",
        "message": ai_errors.timeout().message,
    }
    assert result["warnings"] == []
    assert result["complete"] is True
    preview = weekly_report_service.get_preview(result["preview_id"])
    assert preview["ai_narrative"] is None
