"""B05: cấu hình cookie phiên. Đọc từ biến môi trường (có mặc định) để không phải sửa core/config.py."""
import os

SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "pulse_session")
SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "24"))      # khớp B04: phiên 24 giờ
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() != "false"  # đặt COOKIE_SECURE=false nếu chạy http không phải localhost
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")
