"""B10: DTO đổi vai trò thành viên."""
from pydantic import BaseModel, field_validator
from pydantic_core import PydanticCustomError

ROLES = ("OWNER", "MEMBER", "VIEWER")


class ChangeRoleRequest(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in ROLES:
            raise PydanticCustomError("invalid_value", "Vai trò phải là OWNER, MEMBER hoặc VIEWER")
        return v
