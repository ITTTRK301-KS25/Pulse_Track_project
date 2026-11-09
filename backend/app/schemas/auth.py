"""DTO cho /auth/*. Chỉ dùng pydantic để dễ test độc lập."""
import re
from datetime import datetime

from pydantic import BaseModel, field_validator
from pydantic_core import PydanticCustomError

from app.core.security import validate_password as _validate_password

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str) -> str:
    return value.strip().lower()


def _check_email(value: str) -> str:
    value = normalize_email(value)
    if len(value) > 254 or not _EMAIL_RE.match(value):
        raise PydanticCustomError("invalid_value", "Email không hợp lệ")
    return value


def _check_display_name(value: str) -> str:
    value = value.strip()
    if not 1 <= len(value) <= 100:
        raise PydanticCustomError("invalid_value", "Tên hiển thị phải từ 1 đến 100 ký tự")
    return value


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _check_email(v)

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        try:
            return _validate_password(v)
        except ValueError as exc:
            raise PydanticCustomError("invalid_value", str(exc)) from exc

    @field_validator("display_name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _check_display_name(v)


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return normalize_email(v)


class UpdateMeRequest(BaseModel):
    display_name: str

    @field_validator("display_name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _check_display_name(v)


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    created_at: datetime
