"""Đổi AIError thành HTTPException để API A02+ chỉ cần `raise to_http_exception(err)`.

Handler của nhóm trả message = detail, không đưa chi tiết nội bộ ra ngoài.
"""
from fastapi import HTTPException

from app.ai.errors import AIError


def to_http_exception(err: AIError) -> HTTPException:
    return HTTPException(status_code=err.http_status, detail=err.message)
