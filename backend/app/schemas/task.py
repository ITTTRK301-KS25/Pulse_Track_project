"""B11: DTO tạo task. Lỗi dùng PydanticCustomError để exception handler của nhóm trả 422 đúng dạng."""
from datetime import date

from pydantic import BaseModel, field_validator
from pydantic_core import PydanticCustomError

TITLE_MAX, DESC_MAX = 200, 5000


def clean_title(v: str) -> str:
    v = (v or "").strip()
    if not 1 <= len(v) <= TITLE_MAX:
        raise PydanticCustomError("invalid_title", "Tiêu đề phải từ 1 đến 200 ký tự")
    return v


def clean_description(v):
    if v is None:
        return None
    v = v.strip()
    if len(v) > DESC_MAX:
        raise PydanticCustomError("invalid_description", "Mô tả tối đa 5000 ký tự")
    return v or None


def clean_due_date(v):
    """Nhận chuỗi YYYY-MM-DD (hoặc rỗng/None = không có hạn)."""
    if v is None:
        return None
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise PydanticCustomError("invalid_date", "Ngày hạn phải có dạng YYYY-MM-DD")


def clean_assignee(v: int | str | None) -> int | str | None:
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


class CreateTaskRequest(BaseModel):
    title: str
    description: str | None = None
    due_date: str | None = None
    assignee_id: int | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, v):
        return clean_title(v)

    @field_validator("description")
    @classmethod
    def _desc(cls, v):
        return clean_description(v)

    @field_validator("due_date")
    @classmethod
    def _due(cls, v):
        d = clean_due_date(v)
        return d.isoformat() if d else None

    @field_validator("assignee_id", mode="before")
    @classmethod
    def _assignee(cls, v):
        return clean_assignee(v)
