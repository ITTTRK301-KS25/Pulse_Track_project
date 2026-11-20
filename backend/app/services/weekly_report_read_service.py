
"""A11 - Danh sach, chi tiet va xuat Markdown bao cao tuan."""

from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.weekly_report import WeeklyReport
from app.services import project_access as access
from app.schemas.weekly_report import format_metrics


def _get_report(db: Session, user, report_id: int):
    report = db.scalar(
        select(WeeklyReport).where(
            WeeklyReport.id == report_id
        )
    )

    if report is None:
        raise HTTPException(
            status_code=404,
            detail="Bao cao khong ton tai",
        )

    # Khong cho phep nguoi ngoai du an xem bao cao.
    # get_project_and_role tra 403 neu khong thuoc du an.
    _, role = access.get_project_and_role(
        db,
        report.project_id,
        user,
    )
    access.require(role, "project.read")

    return report


def _serialize(report: WeeklyReport):
    return {
        "id": report.id,
        "report_id": report.id,
        "project_id": report.project_id,
        "week_start": report.week_start.isoformat(),
        "week_end": (
            report.week_start + timedelta(days=6)
        ).isoformat(),
        "timezone": report.timezone,
        "metrics": format_metrics(report.metrics),
        "metrics_raw": report.metrics,
        "ai_narrative": report.ai_narrative,
        "snapshot_hash": report.snapshot_hash,
        "is_mock": bool(report.is_mock),
        "status": "SAVED",
        "created_by": report.created_by,
        "created_at": report.created_at.isoformat(),
    }


def list_weekly_reports(
    db: Session,
    user,
    project_id: int,
    page: int = 1,
    page_size: int = 10,
):
    _, role = access.get_project_and_role(
        db,
        project_id,
        user,
    )
    access.require(role, "project.read")

    filters = (
        WeeklyReport.project_id == project_id,
    )

    total = db.scalar(
        select(func.count())
        .select_from(WeeklyReport)
        .where(*filters)
    ) or 0

    reports = db.scalars(
        select(WeeklyReport)
        .where(*filters)
        .order_by(
            WeeklyReport.week_start.desc(),
            WeeklyReport.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "items": [_serialize(report) for report in reports],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (
            (total + page_size - 1) // page_size
        ),
    }


def get_weekly_report_detail(
    db: Session,
    user,
    report_id: int,
):
    report = _get_report(db, user, report_id)
    return _serialize(report)


def _markdown_cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def export_weekly_report_markdown(
    db: Session,
    user,
    report_id: int,
):
    report = _get_report(db, user, report_id)

    week_end = report.week_start + timedelta(days=6)
    metrics = format_metrics(report.metrics)

    lines = [
        "# BAO CAO TIEN DO TUAN",
        "",
        f"- Ma bao cao: {report.id}",
        f"- Ma du an: {report.project_id}",
        f"- Tu ngay: {report.week_start.isoformat()}",
        f"- Den ngay: {week_end.isoformat()}",
        f"- Mui gio: {report.timezone}",
        "- Trang thai: SAVED",
        "",
        "## 1. Tong quan cac chi so",
        "",
        "| Ma | Chi so | Gia tri | Don vi |",
        "|---|---|---:|---|",
    ]

    for metric in metrics:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(metric["code"]),
                    _markdown_cell(metric["label"]),
                    _markdown_cell(metric["value"]),
                    _markdown_cell(metric["unit"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 2. Nhan xet tien do",
            "",
            report.ai_narrative,
            "",
        ]
    )

    if report.is_mock:
        lines.extend(
            [
                "> Luu y: Noi dung nhan xet duoc tao "
                "trong che do AI gia lap (Mock Mode).",
                "",
            ]
        )

    lines.extend(
        [
            "## 3. Thong tin luu tru",
            "",
            f"- Snapshot hash: `{report.snapshot_hash}`",
            f"- Nguoi luu (ID): {report.created_by}",
            f"- Thoi diem luu: {report.created_at.isoformat()}",
            "",
            "---",
            "",
            "Bao cao duoc xuat tu snapshot da luu.",
            "Khong tinh lai MET va khong goi lai AI.",
            "",
        ]
    )

    return "\n".join(lines)
