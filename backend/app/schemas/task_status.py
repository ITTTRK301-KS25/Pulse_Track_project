"""B14: DTO đổi trạng thái nhanh (Kanban / tick subtask)."""
from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError

STATUSES = ("TODO", "IN_PROGRESS", "DONE")


class SetStatusRequest(BaseModel):
    status: str
    version: int = Field(ge=1)

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in STATUSES:
            raise PydanticCustomError("invalid_status", "Trạng thái phải là TODO, IN_PROGRESS hoặc DONE")
        return v
