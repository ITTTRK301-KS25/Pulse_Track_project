"""B06 POST /projects · B07 GET /projects, GET /projects/{id} · B08 PATCH, archive, restore."""
from typing import Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services import project_service
from app.services.response import create_response

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=201)
def create_project(req: Request, body: ProjectCreate, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    data = project_service.create_project(
        db, user, name=body.name, description=body.description, timezone_name=body.timezone)
    return create_response(req, 201, "Tạo dự án thành công", data, None)


@router.get("")
def list_projects(req: Request, status: Literal["active", "archived"] = "active",
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return create_response(req, 200, "OK", project_service.list_projects(db, user, status), None)


@router.get("/{project_id}")
def get_project(req: Request, project_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    return create_response(req, 200, "OK", project_service.get_project(db, user, project_id), None)


@router.patch("/{project_id}")
def update_project(req: Request, project_id: int, body: ProjectUpdate, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    changes = {k: getattr(body, k) for k in body.model_fields_set}
    return create_response(req, 200, "Cập nhật dự án thành công",
                           project_service.update_project(db, user, project_id, changes), None)


@router.post("/{project_id}/archive")
def archive_project(req: Request, project_id: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    return create_response(req, 200, "Đã lưu trữ dự án", project_service.set_archived(db, user, project_id, True), None)


@router.post("/{project_id}/restore")
def restore_project(req: Request, project_id: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    return create_response(req, 200, "Đã khôi phục dự án", project_service.set_archived(db, user, project_id, False), None)
