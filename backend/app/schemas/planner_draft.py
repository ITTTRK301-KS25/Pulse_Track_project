"""A03: dữ liệu sửa bản nháp AI Planner."""
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.planner import PlannerSuggestion


class UpdatePlannerDraftRequest(BaseModel):
    """PATCH /ai/planner/drafts/{id}: thay toàn bộ danh sách gợi ý (1–20 task, cùng quy tắc như A02).

    `version` (tùy chọn) là version bản nháp mà người dùng đang xem; lệch thì trả 409.
    """
    model_config = ConfigDict(extra="forbid")

    suggestions: list[PlannerSuggestion] = Field(min_length=1, max_length=20)
    version: int | None = Field(default=None, ge=1, strict=True)
