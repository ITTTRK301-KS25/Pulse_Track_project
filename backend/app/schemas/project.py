"""B06/B08: DTO dự án. Dùng PydanticCustomError để lỗi 422 luôn chuyển được sang JSON bằng handler của nhóm."""
from datetime import date
from zoneinfo import ZoneInfo

from pydantic import BaseModel, field_validator, model_validator
from pydantic_core import PydanticCustomError

DEFAULT_TIMEZONE = "Asia/Ho_Chi_Minh"


def _err(message: str) -> PydanticCustomError:
    return PydanticCustomError("invalid_value", message)


def validate_iana(value: str) -> str:
    value = (value or "").strip()
    if not value or ".." in value or value.startswith("/") or "\\" in value:
        raise _err("Múi giờ không hợp lệ")
    try:
        ZoneInfo(value)
    except Exception:
        raise _err("Múi giờ phải là tên IANA hợp lệ, ví dụ Asia/Ho_Chi_Minh")
    return value


def clean_name(v: str) -> str:
    v = v.strip()
    if not 1 <= len(v) <= 150:
        raise _err("Tên dự án phải từ 1 đến 150 ký tự")
    return v


def clean_description(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    if len(v) > 2000:
        raise _err("Mô tả tối đa 2000 ký tự")
    return v or None


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    timezone: str = DEFAULT_TIMEZONE

    _name = field_validator("name")(clean_name)
    _desc = field_validator("description")(clean_description)
    _tz = field_validator("timezone")(validate_iana)

    @model_validator(mode="after")
    def _dates(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise _err("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc")
        return self


class ProjectUpdate(BaseModel):
    """B08: sửa một phần. Múi giờ không được đổi sau khi tạo."""
    name: str | None = None
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    timezone: str | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        if v is None:
            raise _err("Tên dự án không được để trống")
        return clean_name(v)

    _desc = field_validator("description")(clean_description)

    @field_validator("timezone")
    @classmethod
    def _tz_locked(cls, v):
        raise _err("Múi giờ dự án không được thay đổi sau khi tạo")
