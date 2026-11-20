
"""Schema cho A09 - Weekly AI Report Preview."""

from pydantic import BaseModel, ConfigDict, Field


class WeeklyNarrativeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrative: str = Field(min_length=20, max_length=6000)


METRIC_LABELS = {
    "MET-01": "Công việc hoàn thành trong tuần",
    "MET-02": "Công việc đang mở cuối tuần",
    "MET-03": "Công việc quá hạn cuối tuần",
    "MET-04": "Công việc đến hạn trong tuần",
    "MET-05": "Công việc hoàn thành đúng hạn",
    "MET-06": "Tỷ lệ hoàn thành đúng hạn",
}


def format_metrics(values: dict) -> list[dict]:
    result = []

    for code, label in METRIC_LABELS.items():
        result.append({
            "code": code,
            "label": label,
            "value": values[code],
            "unit": "%" if code == "MET-06" else "task",
        })

    return result
