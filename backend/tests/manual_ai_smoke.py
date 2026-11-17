"""Chạy tay để thử AI Adapter (KHÔNG phải test tự động, pytest không tự chạy file này).

Từ thư mục backend:   python tests/manual_ai_smoke.py
- Có AI_API_KEY + AI_MODEL trong .env  -> gọi LLM thật 1 lần.
- APP_ENV=demo và AI_MOCK_MODE=true     -> trả dữ liệu mẫu có nhãn MOCK, không gọi mạng.
- Chưa cấu hình                         -> in lỗi AI_NOT_CONFIGURED (đúng thiết kế).
Chỉ in mã lỗi/metadata, không in key hay nội dung prompt.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import BaseModel

from app.ai.adapter import AIAdapter
from app.ai.config import load_ai_config
from app.ai.errors import AIError


class Hello(BaseModel):
    message: str


def main() -> None:
    adapter = AIAdapter(load_ai_config())
    try:
        r = adapter.complete_json(
            "PLANNER",
            'Trả lời CHỈ bằng JSON dạng {"message": "<chuỗi>"}.',
            "Hãy chào ngắn gọn bằng tiếng Việt.",
            Hello,
            mock_payload={"message": "xin chào (dữ liệu mẫu)"},
        )
        print("OK  message =", r.data.message)
        print("    request_id =", r.request_id, "| attempts =", r.attempts, "| latency_ms =", r.latency_ms,
              "| mock =", r.is_mock, "| label =", r.label)
    except AIError as e:
        print("LỖI CÓ KIỂM SOÁT:", e.code, "| HTTP", e.http_status, "|", e.message,
              "| attempts =", e.attempts, "| request_id =", e.request_id)


if __name__ == "__main__":
    main()
