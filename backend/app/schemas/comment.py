"""B15: DTO thêm bình luận. Lỗi dùng PydanticCustomError để exception handler của nhóm trả 422 đúng dạng."""
import re

from pydantic import BaseModel, field_validator
from pydantic_core import PydanticCustomError

CONTENT_MAX = 2000
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")   # bỏ ký tự điều khiển, giữ xuống dòng và tab


def clean_content(v: str) -> str:
    """Chuẩn hóa nội dung: thống nhất xuống dòng, bỏ ký tự điều khiển, cắt khoảng trắng hai đầu, kiểm độ dài 1..2000.

    Nội dung được lưu nguyên văn (không mã hóa HTML). Giao diện phải hiển thị bằng textContent
    (không dùng innerHTML) để chống XSS.
    """
    v = (v or "").replace("\r\n", "\n").replace("\r", "\n")
    v = _CONTROL.sub("", v).strip()
    if not 1 <= len(v) <= CONTENT_MAX:
        raise PydanticCustomError("invalid_content", "Nội dung bình luận phải từ 1 đến 2000 ký tự")
    return v


class CreateCommentRequest(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def _content(cls, v):
        return clean_content(v)
