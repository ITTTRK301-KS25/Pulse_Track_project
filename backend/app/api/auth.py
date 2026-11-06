"""B05: /auth/register, /login, /logout, GET/PATCH /me."""
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_session, get_current_user
from app.core import auth_cookie as settings
from app.database.db import get_db
from app.models.user import User, UserSession
from app.schemas.auth import LoginRequest, RegisterRequest, UpdateMeRequest
from app.services import auth_service, user_service
from app.services.response import create_response

router = APIRouter(prefix="/auth", tags=["auth"])


def _cookie_args() -> dict:
    return {
        "key": settings.SESSION_COOKIE_NAME,
        "httponly": True,
        "secure": settings.COOKIE_SECURE,
        "samesite": settings.COOKIE_SAMESITE,
        "path": "/",
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(req: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    user = user_service.register(db, email=body.email, password=body.password, display_name=body.display_name)
    return create_response(req, 201, "Đăng ký thành công", user_service.user_to_dict(user), None)


@router.post("/login")
def login(req: Request, body: LoginRequest, db: Session = Depends(get_db)):
    user = user_service.authenticate(db, email=body.email, password=body.password)
    token = auth_service.create_session(db, user)
    res = create_response(req, 200, "Đăng nhập thành công", user_service.user_to_dict(user), None)
    res.set_cookie(value=token, max_age=settings.SESSION_TTL_HOURS * 3600, **_cookie_args())
    return res


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    ctx: tuple[User, UserSession] = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    auth_service.revoke_session(db, ctx[1])
    res = Response(status_code=status.HTTP_204_NO_CONTENT)
    res.delete_cookie(key=settings.SESSION_COOKIE_NAME, path="/", httponly=True,
                      secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE)
    return res


@router.get("/me")
def get_me(req: Request, user: User = Depends(get_current_user)):
    return create_response(req, 200, "OK", user_service.user_to_dict(user), None)


@router.patch("/me")
def update_me(req: Request, body: UpdateMeRequest, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    user = user_service.update_display_name(db, user, body.display_name)
    return create_response(req, 200, "Cập nhật thành công", user_service.user_to_dict(user), None)
