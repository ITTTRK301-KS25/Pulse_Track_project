"""B09: GET /projects/{id}/members, POST /projects/{id}/members."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.member import AddMemberRequest
from app.services import member_service
from app.services.response import create_response

router = APIRouter(prefix="/projects/{project_id}/members", tags=["members"])


@router.get("")
def list_members(req: Request, project_id: str, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    return create_response(req, 200, "OK", member_service.list_members(db, user, project_id), None)


@router.post("", status_code=201)
def add_member(req: Request, project_id: str, body: AddMemberRequest, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    data = member_service.add_member(db, user, project_id, email=body.email, role=body.role)
    return create_response(req, 201, "Đã thêm thành viên", data, None)
