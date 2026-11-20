
"""A10 - Du lieu yeu cau luu bao cao."""

from datetime import date

from pydantic import BaseModel, Field


class WeeklyReportSaveRequest(BaseModel):
    project_id: int = Field(gt=0)
    week_start: date
    preview_id: str = Field(min_length=1, max_length=160)
