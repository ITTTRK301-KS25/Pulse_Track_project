"""A06: sửa nội dung và duyệt bản nháp AI Breakdown."""
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.breakdown import BreakdownSuggestion
from app.schemas.planner_approve import check_idempotency_key


class UpdateBreakdownDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subtasks: list[BreakdownSuggestion] = Field(min_length=1, max_length=10)
    version: int | None = Field(default=None, ge=1, strict=True)


class ApproveBreakdownDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: int | None = Field(default=None, ge=1, strict=True)
    expected_version: int | None = Field(default=None, ge=1, strict=True)
    idempotency_key: str | None = None

    @field_validator("idempotency_key")
    @classmethod
    def _key(cls, value: str | None) -> str | None:
        return None if value is None else check_idempotency_key(value)
