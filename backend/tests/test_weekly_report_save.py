
"""Kiem thu A10 - Luu bao cao tuan."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.weekly_report_save_service import (
    save_weekly_report,
)
from app.services.weekly_report_service import _snapshot_hash


WEEK = date(2026, 11, 9)
METRICS = {
    "MET-01": 1,
    "MET-02": 1,
    "MET-03": 1,
    "MET-04": 0,
    "MET-05": 0,
    "MET-06": 0.0,
}


def make_preview():
    snapshot = {
        "project_id": 2,
        "week_start": WEEK.isoformat(),
        "timezone": "Asia/Ho_Chi_Minh",
        "metrics": METRICS.copy(),
    }

    return {
        "preview_id": "test-preview-123",
        "project_id": 2,
        "owner_id": 3,
        "week_start": WEEK.isoformat(),
        "snapshot_hash": _snapshot_hash(snapshot),
        "snapshot": snapshot,
        "ai_narrative": "Bao cao kiem thu tu dong A10.",
        "is_mock": True,
        "expires_at": datetime.now(timezone.utc)
        + timedelta(minutes=10),
    }


def make_db():
    db = MagicMock()
    db.scalar.return_value = None
    return db


def make_project():
    return SimpleNamespace(id=2, archived_at=None)


def make_user():
    return SimpleNamespace(id=3)


def metrics_result():
    return {
        "timezone": "Asia/Ho_Chi_Minh",
        "metrics": METRICS.copy(),
    }


def run_save(db, **kwargs):
    params = {
        "db": db,
        "user": make_user(),
        "project_id": 2,
        "week_start": WEEK,
        "preview_id": "test-preview-123",
    }
    params.update(kwargs)
    return save_weekly_report(**params)


def test_a10_owner_can_save():
    db = make_db()
    preview = make_preview()

    def refresh(report):
        report.id = 1
        report.created_at = datetime.now(timezone.utc)

    db.refresh.side_effect = refresh

    with (
        patch(
            "app.services.weekly_report_save_service.access.get_project_and_role",
            return_value=(make_project(), "OWNER"),
        ),
        patch(
            "app.services.weekly_report_save_service.get_preview",
            return_value=preview,
        ),
        patch(
            "app.services.weekly_report_save_service.calculate_weekly_metrics",
            return_value=metrics_result(),
        ),
    ):
        result = run_save(db)

    assert result["report_id"] == 1
    assert result["status"] == "SAVED"
    assert result["metrics"] == METRICS
    db.add.assert_called_once()
    db.commit.assert_called_once()


@pytest.mark.parametrize("role", ["MEMBER", "VIEWER"])
def test_a10_non_owner_denied(role):
    db = make_db()

    with patch(
        "app.services.weekly_report_save_service.access.get_project_and_role",
        return_value=(make_project(), role),
    ):
        with pytest.raises(HTTPException) as exc:
            run_save(db)

    assert exc.value.status_code == 403
    db.add.assert_not_called()


def test_a10_expired_preview_denied():
    db = make_db()
    preview = make_preview()
    preview["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    )

    with (
        patch(
            "app.services.weekly_report_save_service.access.get_project_and_role",
            return_value=(make_project(), "OWNER"),
        ),
        patch(
            "app.services.weekly_report_save_service.get_preview",
            return_value=preview,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            run_save(db)

    assert exc.value.status_code == 409
    db.add.assert_not_called()


def test_a10_changed_metrics_denied():
    db = make_db()
    changed = metrics_result()
    changed["metrics"]["MET-01"] = 99

    with (
        patch(
            "app.services.weekly_report_save_service.access.get_project_and_role",
            return_value=(make_project(), "OWNER"),
        ),
        patch(
            "app.services.weekly_report_save_service.get_preview",
            return_value=make_preview(),
        ),
        patch(
            "app.services.weekly_report_save_service.calculate_weekly_metrics",
            return_value=changed,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            run_save(db)

    assert exc.value.status_code == 409
    db.add.assert_not_called()


def test_a10_archived_project_denied():
    db = make_db()
    project = SimpleNamespace(
        id=2,
        archived_at=datetime.now(timezone.utc),
    )

    with patch(
        "app.services.weekly_report_save_service.access.get_project_and_role",
        return_value=(project, "OWNER"),
    ):
        with pytest.raises(HTTPException) as exc:
            run_save(db)

    assert exc.value.status_code == 409
    db.add.assert_not_called()


def test_a10_duplicate_preview_returns_existing():
    db = make_db()

    existing = SimpleNamespace(
        id=1,
        project_id=2,
        week_start=WEEK,
        preview_id="test-preview-123",
        timezone="Asia/Ho_Chi_Minh",
        metrics=METRICS.copy(),
        ai_narrative="Bao cao da luu",
        snapshot_hash="abc123",
        is_mock=1,
        created_by=3,
        created_at=datetime.now(timezone.utc),
    )

    db.scalar.return_value = existing

    with patch(
        "app.services.weekly_report_save_service.access.get_project_and_role",
        return_value=(make_project(), "OWNER"),
    ):
        result = run_save(db)

    assert result["report_id"] == 1
    assert result["status"] == "SAVED"
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_a10_wrong_preview_owner_denied():
    db = make_db()
    preview = make_preview()
    preview["owner_id"] = 999

    with (
        patch(
            "app.services.weekly_report_save_service.access.get_project_and_role",
            return_value=(make_project(), "OWNER"),
        ),
        patch(
            "app.services.weekly_report_save_service.get_preview",
            return_value=preview,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            run_save(db)

    assert exc.value.status_code == 403
    db.add.assert_not_called()
