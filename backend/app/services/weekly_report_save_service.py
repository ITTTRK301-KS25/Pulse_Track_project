
"""A10 - Luu bao cao tuan tu preview A09."""

import hmac

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.weekly_report import WeeklyReport
from app.services import project_access as access
from app.services.weekly_metrics_service import (
    calculate_weekly_metrics,
)
from app.services.weekly_report_service import (
    get_preview,
    _snapshot_hash,
)


def _error(status_code, message):
    raise HTTPException(
        status_code=status_code,
        detail=message,
    )


def _serialize_report(report):
    return {
        "id": report.id,
        "report_id": report.id,
        "project_id": report.project_id,
        "week_start": report.week_start.isoformat(),
        "preview_id": report.preview_id,
        "timezone": report.timezone,
        "metrics": report.metrics,
        "ai_narrative": report.ai_narrative,
        "snapshot_hash": report.snapshot_hash,
        "is_mock": bool(report.is_mock),
        "status": "SAVED",
        "created_by": report.created_by,
        "created_at": report.created_at.isoformat(),
    }


def save_weekly_report(
    db,
    user,
    project_id,
    week_start,
    preview_id,
):
    # Kiem tra quyen OWNER.
    project, role = access.get_project_and_role(
        db,
        project_id,
        user,
        lock=True,
    )

    access.require(role, "project.edit")

    # Neu preview da duoc luu thanh cong truoc do,
    # tra lai ban ghi cu, khong tao them bao cao.
    existing_preview = db.scalar(
        select(WeeklyReport).where(
            WeeklyReport.preview_id == preview_id
        )
    )

    if existing_preview is not None:
        if (
            existing_preview.project_id != project_id
            or existing_preview.week_start != week_start
            or existing_preview.created_by != user.id
        ):
            _error(
                409,
                "Preview da duoc su dung cho yeu cau khac",
            )

        return _serialize_report(existing_preview)

    # Khong cho ghi bao cao moi vao du an da luu tru.
    access.require_active(project)

    preview = get_preview(preview_id)

    if preview is None:
        _error(
            409,
            "Preview khong ton tai hoac da het han",
        )

    # Xac minh preview thuoc dung du an va nguoi tao.
    if (
        preview["project_id"] != project_id
        or preview["owner_id"] != user.id
        or preview["week_start"] != week_start.isoformat()
    ):
        _error(
            403,
            "Preview khong thuoc yeu cau hien tai",
        )

    now = datetime.now(timezone.utc)

    if preview["expires_at"] <= now:
        _error(
            409,
            "Preview da het han, vui long tao lai",
        )

    # Kiem tra tinh toan ven cua snapshot da luu tam.
    saved_snapshot = preview["snapshot"]

    saved_hash = _snapshot_hash(saved_snapshot)

    if not hmac.compare_digest(
        saved_hash,
        preview["snapshot_hash"],
    ):
        _error(
            409,
            "Snapshot preview khong hop le",
        )

    # Tinh lai MET de phat hien thay doi du lieu.
    current_metrics = calculate_weekly_metrics(
        db=db,
        project_id=project_id,
        week_start=week_start,
    )

    current_snapshot = {
        "project_id": project_id,
        "week_start": week_start.isoformat(),
        "timezone": current_metrics["timezone"],
        "metrics": current_metrics["metrics"],
    }

    current_hash = _snapshot_hash(current_snapshot)

    if not hmac.compare_digest(
        current_hash,
        preview["snapshot_hash"],
    ):
        _error(
            409,
            "Du lieu bao cao da thay doi, vui long xem truoc lai",
        )

    # Moi du an chi co mot bao cao SAVED cho moi tuan.
    existing_week = db.scalar(
        select(WeeklyReport).where(
            WeeklyReport.project_id == project_id,
            WeeklyReport.week_start == week_start,
        )
    )

    if existing_week is not None:
        _error(
            409,
            "Bao cao cua tuan nay da duoc luu",
        )

    narrative = preview["ai_narrative"]

    if not isinstance(narrative, str) or not narrative.strip():
        _error(
            409,
            "Noi dung bao cao AI khong hop le",
        )

    report = WeeklyReport(
        project_id=project_id,
        week_start=week_start,
        preview_id=preview_id,
        snapshot_hash=preview["snapshot_hash"],
        snapshot=saved_snapshot,
        metrics=current_metrics["metrics"],
        ai_narrative=narrative,
        timezone=current_metrics["timezone"],
        is_mock=int(preview["is_mock"]),
        created_by=user.id,
    )

    db.add(report)

    try:
        db.commit()
        db.refresh(report)

    except IntegrityError:
        db.rollback()

        # Xu ly truong hop hai request luu cung luc.
        existing_preview = db.scalar(
            select(WeeklyReport).where(
                WeeklyReport.preview_id == preview_id
            )
        )

        if existing_preview is not None:
            if (
                existing_preview.project_id == project_id
                and existing_preview.week_start == week_start
                and existing_preview.created_by == user.id
            ):
                return _serialize_report(existing_preview)

        _error(
            409,
            "Bao cao da duoc luu boi mot yeu cau khac",
        )

    return _serialize_report(report)
