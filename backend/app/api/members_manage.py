"""B10: PATCH và DELETE /projects/{id}/members/{user_id}."""
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.member_update import ChangeRoleRequest
from app.services import member_manage_service
from app.services.response import create_response

router = APIRouter(prefix="/projects/{project_id}/members", tags=["members"])


@router.patch("/{user_id}")
def change_role(req: Request, project_id: str, user_id: str, body: ChangeRoleRequest,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = member_manage_service.change_role(db, user, project_id, user_id, body.role)
    return create_response(req, 200, "Đã đổi vai trò", data, None)


@router.delete("/{user_id}", status_code=204)
def remove_member(project_id: str, user_id: str, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    member_manage_service.remove_member(db, user, project_id, user_id)
    return Response(status_code=204)
