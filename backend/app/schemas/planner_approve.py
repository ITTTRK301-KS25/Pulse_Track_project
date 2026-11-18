"""A04: dữ liệu duyệt bản nháp AI Planner."""
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

_KEY = re.compile(r"^[A-Za-z0-9._:\-]{8,160}$")


def check_idempotency_key(v: str) -> str:
    v = v.strip()
    if not _KEY.match(v):
        raise PydanticCustomError(
            "invalid_idempotency_key",
            "idempotency_key phải dài 8-160 ký tự, chỉ gồm chữ, số và . _ : -",
        )
    return v


class ApprovePlannerDraftRequest(BaseModel):
    """POST /ai/planner/drafts/{id}/approve — body có thể trống hoặc {"draft_id": N}.

    draft_id: (tùy chọn) phải trùng id trên đường dẫn.
    expected_version: (tùy chọn) version bản nháp người dùng đang xem; lệch -> 409.
    idempotency_key: (tùy chọn trong body) ưu tiên gửi bằng header `Idempotency-Key`.
    """
    model_config = ConfigDict(extra="forbid")

    draft_id: int | None = Field(default=None, ge=1, strict=True)
    expected_version: int | None = Field(default=None, ge=1, strict=True)
    idempotency_key: str | None = None

    @field_validator("idempotency_key")
    @classmethod
    def _key(cls, v: str | None) -> str | None:
        return None if v is None else check_idempotency_key(v)
