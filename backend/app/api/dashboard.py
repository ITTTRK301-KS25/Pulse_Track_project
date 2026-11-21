"""B20 - API Dashboard."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.services.dashboard_service import get_dashboard
from app.services.response import create_response


router = APIRouter(tags=["Dashboard"])


@router.get("/dashboard")
def read_dashboard(
    request: Request,
    project_id: int = Query(gt=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = get_dashboard(db, user, project_id)
    return create_response(request, 200, "Lấy thống kê dashboard thành công", data, None)
