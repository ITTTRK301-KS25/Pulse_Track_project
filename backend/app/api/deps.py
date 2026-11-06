from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core import auth_cookie as settings
from app.database.db import get_db
from app.models.user import User, UserSession
from app.services import auth_service


def get_current_session(request: Request, db: Session = Depends(get_db)) -> tuple[User, UserSession]:
    return auth_service.resolve_session(db, request.cookies.get(settings.SESSION_COOKIE_NAME))


def get_current_user(ctx: tuple[User, UserSession] = Depends(get_current_session)) -> User:
    return ctx[0]
