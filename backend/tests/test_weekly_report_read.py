
"""Kiem thu A11 - Danh sach, chi tiet va xuat Markdown."""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.weekly_report_read_service import (
    list_weekly_reports,
    get_weekly_report_detail,
    export_weekly_report_markdown,
)


METRICS = {
    "MET-01": 1,
    "MET-02": 1,
    "MET-03": 1,
    "MET-04": 0,
    "MET-05": 0,
    "MET-06": 0.0,
}

SERVICE = "app.services.weekly_report_read_service"


def make_user():
    return SimpleNamespace(id=3)


def make_project():
    return SimpleNamespace(
        id=2,
        archived_at=None,
    )


def make_report():
    return SimpleNamespace(
        id=1,
        project_id=2,
        week_start=date(2026, 11, 9),
        timezone="Asia/Ho_Chi_Minh",
        metrics=METRICS.copy(),
        ai_narrative="Bao cao kiem thu A11.",
        snapshot_hash="abc123",
        is_mock=True,
        created_by=3,
        created_at=datetime(
            2026, 11, 20, 14, 39, 59,
            tzinfo=timezone.utc,
        ),
    )


@pytest.mark.parametrize(
    "role",
    ["OWNER", "MEMBER", "VIEWER"],
)
def test_a11_list_allowed_roles(role):
    db = MagicMock()
    db.scalar.return_value = 1
    db.scalars.return_value.all.return_value = [
        make_report()
    ]

    with patch(
        f"{SERVICE}.access.get_project_and_role",
        return_value=(make_project(), role),
    ):
        result = list_weekly_reports(
            db=db,
            user=make_user(),
            project_id=2,
        )

    assert result["total"] == 1
    assert result["page"] == 1
    assert result["total_pages"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["report_id"] == 1
    assert result["items"][0]["status"] == "SAVED"


def test_a11_list_empty():
    db = MagicMock()
    db.scalar.return_value = 0
    db.scalars.return_value.all.return_value = []

    with patch(
        f"{SERVICE}.access.get_project_and_role",
        return_value=(make_project(), "OWNER"),
    ):
        result = list_weekly_reports(
            db=db,
            user=make_user(),
            project_id=2,
        )

    assert result["items"] == []
    assert result["total"] == 0
    assert result["total_pages"] == 0


def test_a11_list_pagination():
    db = MagicMock()
    db.scalar.return_value = 25
    db.scalars.return_value.all.return_value = [
        make_report()
    ]

    with patch(
        f"{SERVICE}.access.get_project_and_role",
        return_value=(make_project(), "OWNER"),
    ):
        result = list_weekly_reports(
            db=db,
            user=make_user(),
            project_id=2,
            page=2,
            page_size=10,
        )

    assert result["page"] == 2
    assert result["page_size"] == 10
    assert result["total"] == 25
    assert result["total_pages"] == 3


def test_a11_detail_success():
    db = MagicMock()
    db.scalar.return_value = make_report()

    with patch(
        f"{SERVICE}.access.get_project_and_role",
        return_value=(make_project(), "OWNER"),
    ):
        result = get_weekly_report_detail(
            db=db,
            user=make_user(),
            report_id=1,
        )

    assert result["report_id"] == 1
    assert result["week_start"] == "2026-11-09"
    assert result["week_end"] == "2026-11-15"
    assert result["metrics_raw"] == METRICS
    assert len(result["metrics"]) == 6
    assert result["status"] == "SAVED"


def test_a11_report_not_found():
    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc:
        get_weekly_report_detail(
            db=db,
            user=make_user(),
            report_id=999,
        )

    assert exc.value.status_code == 404


@pytest.mark.parametrize(
    "role",
    ["MEMBER", "VIEWER"],
)
def test_a11_detail_member_viewer_allowed(role):
    db = MagicMock()
    db.scalar.return_value = make_report()

    with patch(
        f"{SERVICE}.access.get_project_and_role",
        return_value=(make_project(), role),
    ):
        result = get_weekly_report_detail(
            db=db,
            user=make_user(),
            report_id=1,
        )

    assert result["report_id"] == 1


def test_a11_outsider_denied():
    db = MagicMock()
    db.scalar.return_value = make_report()

    with patch(
        f"{SERVICE}.access.get_project_and_role",
        side_effect=HTTPException(
            status_code=403,
            detail="Khong thuoc du an",
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            get_weekly_report_detail(
                db=db,
                user=make_user(),
                report_id=1,
            )

    assert exc.value.status_code == 403


def test_a11_export_markdown():
    db = MagicMock()
    db.scalar.return_value = make_report()

    with patch(
        f"{SERVICE}.access.get_project_and_role",
        return_value=(make_project(), "OWNER"),
    ):
        markdown = export_weekly_report_markdown(
            db=db,
            user=make_user(),
            report_id=1,
        )

    assert "# BAO CAO TIEN DO TUAN" in markdown
    assert "MET-01" in markdown
    assert "MET-06" in markdown
    assert "2026-11-09" in markdown
    assert "2026-11-15" in markdown
    assert "Bao cao kiem thu A11." in markdown
    assert "Mock Mode" in markdown


def test_a11_export_does_not_modify_database():
    db = MagicMock()
    db.scalar.return_value = make_report()

    with patch(
        f"{SERVICE}.access.get_project_and_role",
        return_value=(make_project(), "OWNER"),
    ):
        export_weekly_report_markdown(
            db=db,
            user=make_user(),
            report_id=1,
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()


def test_a11_export_outsider_denied():
    db = MagicMock()
    db.scalar.return_value = make_report()

    with patch(
        f"{SERVICE}.access.get_project_and_role",
        side_effect=HTTPException(
            status_code=403,
            detail="Khong thuoc du an",
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            export_weekly_report_markdown(
                db=db,
                user=make_user(),
                report_id=1,
            )

    assert exc.value.status_code == 403


def test_a11_uses_saved_metrics_without_recalculation():
    db = MagicMock()
    db.scalar.return_value = make_report()

    with (
        patch(
            f"{SERVICE}.access.get_project_and_role",
            return_value=(make_project(), "OWNER"),
        ),
        patch(
            "app.services.weekly_metrics_service.calculate_weekly_metrics",
            side_effect=AssertionError(
                "A11 khong duoc tinh lai MET"
            ),
        ),
    ):
        detail = get_weekly_report_detail(
            db=db,
            user=make_user(),
            report_id=1,
        )

        markdown = export_weekly_report_markdown(
            db=db,
            user=make_user(),
            report_id=1,
        )

    assert detail["metrics_raw"] == METRICS
    assert "MET-01" in markdown
    db.commit.assert_not_called()
