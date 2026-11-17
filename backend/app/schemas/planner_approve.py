"""A04: dữ liệu duyệt bản nháp AI Planner."""
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

_KEY = re.compile(r"^[A-Za-z0-9._:\-]{8,160}$")


class ApprovePlannerDraftRequest(BaseModel):
    """POST /ai/planner/drafts/{id}/approve

    expected_version: version bản nháp mà người dùng đang xem (lệch -> 409, tránh duyệt nhầm bản đã bị sửa).
    idempotency_key: 8–160 ký tự chữ/số/. _ : - do client tự sinh; gửi lại cùng khóa thì không tạo task trùng.
    """
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1, strict=True)
    idempotency_key: str

    @field_validator("idempotency_key")
    @classmethod
    def _key(cls, v: str) -> str:
        v = v.strip()
        if not _KEY.match(v):
            raise PydanticCustomError(
                "invalid_idempotency_key",
                "idempotency_key phải dài 8-160 ký tự, chỉ gồm chữ, số và . _ : -",
            )
        return v
