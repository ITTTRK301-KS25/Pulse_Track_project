
"""A09 Preview, A10 Save, A11 Read and Export."""

from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    Query,
    Request,
)
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.weekly_report_save import (
    WeeklyReportSaveRequest,
)
from app.services.response import create_response
from app.services.weekly_report_service import (
    create_weekly_preview,
)
from app.services.weekly_report_save_service import (
    save_weekly_report,
)
from app.services.weekly_report_read_service import (
    list_weekly_reports,
    get_weekly_report_detail,
    export_weekly_report_markdown,
)


router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
)


# A09 - Xem truoc bao cao
@router.get("/preview")
def preview_weekly_report(
    request: Request,
    project_id: int = Query(gt=0),
    week_start: date = Query(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = create_weekly_preview(
        db=db,
        user=user,
        project_id=project_id,
        week_start=week_start,
    )

    return create_response(
        request,
        200,
        "Tao ban xem truoc bao cao tuan thanh cong",
        data,
        None,
    )


# A10 - Luu bao cao
@router.post("", status_code=201)
def save_report(
    request: Request,
    body: WeeklyReportSaveRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = save_weekly_report(
        db=db,
        user=user,
        project_id=body.project_id,
        week_start=body.week_start,
        preview_id=body.preview_id,
    )

    return create_response(
        request,
        201,
        "Luu bao cao tuan thanh cong",
        data,
        None,
    )


# A11 - Danh sach bao cao
@router.get("")
def get_reports(
    request: Request,
    project_id: int = Query(gt=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = list_weekly_reports(
        db=db,
        user=user,
        project_id=project_id,
        page=page,
        page_size=page_size,
    )

    return create_response(
        request,
        200,
        "Lay danh sach bao cao thanh cong",
        data,
        None,
    )


# A11 - Xuat Markdown
@router.get("/{report_id}/export")
def export_report(
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    markdown = export_weekly_report_markdown(
        db=db,
        user=user,
        report_id=report_id,
    )

    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="weekly-report-{report_id}.md"'
            ),
            "Cache-Control": "private, no-store",
        },
    )


# A11 - Chi tiet bao cao
@router.get("/{report_id}")
def get_report_detail(
    request: Request,
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = get_weekly_report_detail(
        db=db,
        user=user,
        report_id=report_id,
    )

    return create_response(
        request,
        200,
        "Lay chi tiet bao cao thanh cong",
        data,
        None,
    )
