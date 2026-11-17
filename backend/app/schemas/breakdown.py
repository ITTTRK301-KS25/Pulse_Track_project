"""A05: yêu cầu và kết quả AI Breakdown (phân rã task cha thành subtask)."""
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError


class BreakdownRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: str

    @field_validator("objective")
    @classmethod
    def _objective(cls, v: str) -> str:
        v = v.strip()
        if not 10 <= len(v) <= 2000:
            raise PydanticCustomError("invalid_objective", "Mục tiêu phân rã phải từ 10 đến 2000 ký tự")
        return v


class BreakdownSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None
    due_date: str | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        v = v.strip()
        if not 1 <= len(v) <= 200:
            raise PydanticCustomError("invalid_subtask_title", "Tiêu đề subtask phải từ 1 đến 200 ký tự")
        return v

    @field_validator("description")
    @classmethod
    def _description(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if len(v) > 5000:
            raise PydanticCustomError("invalid_subtask_description", "Mô tả subtask tối đa 5000 ký tự")
        return v or None

    @field_validator("due_date")
    @classmethod
    def _due_date(cls, v: str | None) -> str | None:
        if v is None:
            return None
        try:
            return date.fromisoformat(v).isoformat()
        except ValueError:
            raise PydanticCustomError("invalid_subtask_due_date", "Hạn subtask phải có dạng YYYY-MM-DD hoặc null") from None


class BreakdownOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[BreakdownSuggestion] = Field(min_length=1, max_length=10)
