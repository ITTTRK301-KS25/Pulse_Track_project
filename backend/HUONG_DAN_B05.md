# B05 – API Register / Login / Logout / Me (chỉ thêm file mới, không sửa code cũ)

## File mới
- backend/app/api/auth.py        (5 API: POST /auth/register, /auth/login, /auth/logout, GET + PATCH /auth/me)
- backend/app/api/deps.py        (lấy user hiện tại từ cookie)
- backend/app/schemas/auth.py    (DTO)
- backend/app/core/auth_cookie.py (cấu hình cookie, đọc biến môi trường, có giá trị mặc định)
- backend/tests/test_auth_schemas.py

## Bạn tự thêm vào backend/app/main.py (2 chỗ)
```python
from app.core.exception import register_exception_handler   # nếu chưa có
from app.api import auth as auth_api

app = FastAPI()
register_exception_handler(app)        # để lỗi trả đúng khuôn {status_code, message, data, error...}
app.include_router(auth_api.router)    # gắn B05
```
(CORS đã có sẵn trong main.py của nhóm, giữ nguyên.)

## B05 cần B03/B04 của nhóm có sẵn
- app/models/user.py: `User` (id, email, display_name, created_at) và `UserSession`
- app/services/user_service.py: `register(db, email=, password=, display_name=)`, `authenticate(db, email=, password=)`,
  `update_display_name(db, user, name)`, `user_to_dict(user)`
- app/services/auth_service.py: `create_session(db, user)` -> token chưa băm, `resolve_session(db, token)` -> (user, session),
  `revoke_session(db, session)`
Tên hàm khác thì sửa lời gọi trong api/auth.py và api/deps.py.

## Cookie (tùy chọn, đặt trong môi trường, KHÔNG đặt trong .env vì Settings của nhóm không nhận biến lạ)
SESSION_COOKIE_NAME (mặc định pulse_session), SESSION_TTL_HOURS (24), COOKIE_SECURE (true), COOKIE_SAMESITE (lax)
Chạy http không phải localhost: đặt COOKIE_SECURE=false. Frontend và backend nên cùng host `localhost`.

## Đã/chưa kiểm thử
Đã chạy: test DTO (9 test qua). Chưa chạy với FastAPI + MySQL thật.
