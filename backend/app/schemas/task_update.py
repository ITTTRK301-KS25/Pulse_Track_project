"""B12: DTO sửa task. Trường không gửi = giữ nguyên; due_date/assignee_id gửi null = xóa giá trị."""
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from app.schemas.task import clean_assignee, clean_description, clean_due_date, clean_title

STATUSES = ("TODO", "IN_PROGRESS", "DONE")


class UpdateTaskRequest(BaseModel):
    version: int = Field(ge=1)
    title: str | None = None
    description: str | None = None
    status: str | None = None
    due_date: str | None = None
    assignee_id: str | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, v):
        if v is None:
            raise PydanticCustomError("invalid_title", "Tiêu đề không được để trống")
        return clean_title(v)

    @field_validator("description")
    @classmethod
    def _desc(cls, v):
        return clean_description(v)

    @field_validator("status")
    @classmethod
    def _status(cls, v):
        if v is None:
            raise PydanticCustomError("invalid_status", "Trạng thái không được để trống")
        v = v.strip().upper()
        if v not in STATUSES:
            raise PydanticCustomError("invalid_status", "Trạng thái phải là TODO, IN_PROGRESS hoặc DONE")
        return v

    @field_validator("due_date")
    @classmethod
    def _due(cls, v):
        d = clean_due_date(v)
        return d.isoformat() if d else None

    @field_validator("assignee_id")
    @classmethod
    def _assignee(cls, v):
        return clean_assignee(v)

    @model_validator(mode="after")
    def _need_one_field(self):
        if not (self.model_fields_set - {"version"}):
            raise PydanticCustomError("empty_update", "Cần gửi ít nhất một trường để sửa")
        return self

    def requested(self) -> dict:
        """Chỉ các trường client thực sự gửi (kể cả null cho due_date/assignee_id/description)."""
        return {f: getattr(self, f) for f in self.model_fields_set if f != "version"}
