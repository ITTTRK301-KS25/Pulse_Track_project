"""B09: DTO thêm thành viên theo email."""
import re

from pydantic import BaseModel, field_validator
from pydantic_core import PydanticCustomError

ROLES = ("OWNER", "MEMBER", "VIEWER")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _err(message: str) -> PydanticCustomError:
    return PydanticCustomError("invalid_value", message)


class AddMemberRequest(BaseModel):
    email: str
    role: str = "MEMBER"

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) > 254 or not _EMAIL_RE.match(v):
            raise _err("Email không hợp lệ")
        return v

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in ROLES:
            raise _err("Vai trò phải là OWNER, MEMBER hoặc VIEWER")
        return v
