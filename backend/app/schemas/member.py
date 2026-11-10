import re

from pydantic import BaseModel, field_validator
from pydantic_core import PydanticCustomError

ROLES = ("OWNER", "MEMBER", "VIEWER")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AddMemberRequest(BaseModel):
    email: str
    role: str = "MEMBER"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if len(value) > 254 or not EMAIL_RE.fullmatch(value):
            raise PydanticCustomError("invalid_email", "Email không hợp lệ")
        return value

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in ROLES:
            raise PydanticCustomError("invalid_role", "Vai trò phải là OWNER, MEMBER hoặc VIEWER")
        return value
