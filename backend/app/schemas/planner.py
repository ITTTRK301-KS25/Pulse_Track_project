"""A02: validated request and structured AI Planner output."""
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError


class PlannerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int = Field(gt=0, strict=True)
    goal: str
    scope: str = ""

    @field_validator("goal")
    @classmethod
    def _goal(cls, value: str) -> str:
        value = value.strip()
        if not 10 <= len(value) <= 2000:
            raise PydanticCustomError(
                "invalid_goal",
                "Mục tiêu phải từ 10 đến 2000 ký tự",
            )
        return value

    @field_validator("scope")
    @classmethod
    def _scope(cls, value: str) -> str:
        value = value.strip()
        if len(value) > 1000:
            raise PydanticCustomError(
                "invalid_scope",
                "Phạm vi tối đa 1000 ký tự",
            )
        return value

    @model_validator(mode="after")
    def _prompt_size(self):
        if len(self.goal) + len(self.scope) > 3000:
            raise PydanticCustomError(
                "planner_input_too_long",
                "Tổng mục tiêu và phạm vi tối đa 3000 ký tự",
            )
        return self


class PlannerSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None
    due_date: str | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 200:
            raise PydanticCustomError(
                "invalid_task_title",
                "Tiêu đề task phải từ 1 đến 200 ký tự",
            )
        return value

    @field_validator("description")
    @classmethod
    def _description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 5000:
            raise PydanticCustomError(
                "invalid_task_description",
                "Mô tả task tối đa 5000 ký tự",
            )
        return value or None

    @field_validator("due_date")
    @classmethod
    def _due_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from datetime import date

        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            raise PydanticCustomError(
                "invalid_task_due_date",
                "Hạn task phải có dạng YYYY-MM-DD hoặc null",
            ) from None


class PlannerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PlannerSuggestion] = Field(min_length=1, max_length=20)
