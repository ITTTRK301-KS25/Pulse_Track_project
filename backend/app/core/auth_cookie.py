"""B05: cấu hình cookie phiên. Đọc từ biến môi trường (có mặc định) để không phải sửa core/config.py."""
import os

SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "pulse_session")
SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "24"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() != "false"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")
