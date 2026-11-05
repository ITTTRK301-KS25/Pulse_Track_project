# Pulse Track – F01 (HTML/CSS/JavaScript)

## 1. Phạm vi

- Khởi tạo Frontend bằng HTML, CSS và JavaScript thuần.
- Không sử dụng React, Vite hoặc npm.
- Điều hướng giữa các trang HTML.
- Bảo vệ `dashboard.html`, `projects.html` và `kanban.html`.
- Xây dựng HTTP Client dùng chung.
- Cấu hình API Base URL và kết nối Backend.
- Xử lý HTTP 200, 401, 403.
- Xử lý timeout và lỗi kết nối.

## 2. Cấu trúc Frontend

```text
frontend/
├── assets/
├── css/
│   └── style.css
├── js/
│   ├── api.js
│   ├── config.js
│   ├── main.js
│   └── router.js
├── index.html
├── login.html
├── register.html
├── dashboard.html
├── projects.html
├── kanban.html
└── README_F01.md
```

## 3. Cấu hình API

File: `js/config.js`

- API_BASE_URL: `http://localhost:8000`
- REQUEST_TIMEOUT_MS: 15000 ms.
- LOGIN_PAGE: `login.html`.
- AFTER_LOGIN_PAGE: `dashboard.html`.

HTTP Client sử dụng:

- Fetch API.
- `credentials: "include"`.
- JSON request/response.
- GET, POST, PATCH, DELETE.
- AbortController để xử lý timeout.
- Không lưu access token trong localStorage hoặc sessionStorage.

Frontend đã kết nối thành công với Backend FastAPI qua API `GET /health/db`.

## 4. Router và xác thực

Các trang được bảo vệ:

- `dashboard.html`
- `projects.html`
- `kanban.html`

Quy trình xử lý:

1. Router gọi `GET /auth/me`.
2. HTTP 200: lưu thông tin người dùng và hiển thị trang.
3. HTTP 401: chuyển về `login.html`.
4. Lỗi mạng hoặc timeout: hiển thị thông báo và nút Thử lại.
5. HTTP 403: hiển thị thông báo không đủ quyền, không tự đăng xuất.

Khi xác thực thành công, Router xóa thông báo lỗi cũ và ẩn nút Thử lại.

Các tình huống xác thực hiện đã được kiểm thử bằng phản hồi mô phỏng. Việc kiểm thử xác thực thật phụ thuộc vào API Backend.

## 5. Kết quả kiểm thử

### 5.1. Kiểm thử Frontend

- [x] Frontend chạy bằng VS Code Live Server.
- [x] HTTP Client nhận phản hồi HTTP 200 mô phỏng.
- [x] Xử lý HTTP 401 mô phỏng.
- [x] Xử lý HTTP 403 mô phỏng qua HTTP Client.
- [x] Hiển thị thông báo HTTP 403.
- [x] Timeout trả về `REQUEST_ABORTED`.
- [x] Router mở khóa Dashboard khi HTTP 200 mô phỏng.
- [x] Dashboard hiển thị đầy đủ sau khi Router mở khóa.
- [x] Xóa thông báo lỗi cũ sau khi xác thực thành công.

### 5.2. Kiểm thử tích hợp Backend

- [x] Backend FastAPI khởi động thành công.
- [x] Swagger hoạt động tại `/docs`.
- [x] Backend kết nối MySQL thành công.
- [x] API `GET /health/db` trả HTTP 200.
- [x] Frontend gọi thành công `GET /health/db` qua HTTP Client.
- [x] CORS cho phép Frontend đọc phản hồi API.
- [x] Khi Backend dừng, HTTP Client trả về `NETWORK_ERROR`.

### 5.3. Chưa hoàn tất kiểm thử

- [ ] Xác nhận điều hướng đầy đủ giữa các trang.
- [ ] Kiểm thử `GET /auth/me` với Backend thật.
- [ ] Kiểm thử HTTP 401/403 từ API xác thực thật.
- [ ] Kiểm tra Cookie HttpOnly và phiên đăng nhập.
- [ ] Xác nhận yêu cầu CSRF với Backend.
- [ ] Kiểm thử timeout với Backend thật.

## 6. Tích hợp Backend

Backend sử dụng FastAPI và MySQL.

Địa chỉ chạy cục bộ:

- Backend: `http://localhost:8000`
- Frontend: `http://127.0.0.1:5500`

Các API đã xác nhận:

- `GET /`
- `GET /health/db`

API xác thực `GET /auth/me` chưa được xác nhận là đã triển khai trong Backend.

CORS đã hoạt động đối với yêu cầu kiểm tra cơ sở dữ liệu. Việc xác thực bằng Cookie HttpOnly cần được kiểm thử riêng khi Backend cung cấp API đăng nhập.

## 7. Hướng dẫn chạy

1. Mở dự án bằng VS Code.
2. Khởi động MySQL.
3. Mở Terminal trong thư mục `backend`.
4. Chạy Backend:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

5. Kiểm tra Backend tại `http://127.0.0.1:8000/docs`.
6. Mở `frontend/login.html` bằng Live Server.
7. Sử dụng HTTP Client để kiểm tra kết nối Backend.

Không sử dụng `file://` để kiểm thử API hoặc Cookie.

## 8. Giới hạn F01

F01 tập trung xây dựng nền tảng Frontend và kết nối API cơ bản.

Các chức năng thuộc những task tiếp theo:

- Đăng ký và đăng nhập thực tế (F02).
- Quản lý dự án và công việc.
- Kéo thả Kanban.
- Báo cáo tiến độ và các tính năng AI.

F01 đã kết nối Backend thật qua API kiểm tra cơ sở dữ liệu. Việc tích hợp xác thực sẽ tiếp tục khi Backend cung cấp các endpoint tương ứng.

## 9. Kết luận

F01 đã hoàn thành phần xây dựng nền tảng Frontend, cấu hình Router, HTTP Client và các bài kiểm thử mô phỏng chính.

Frontend đã kết nối thành công với Backend FastAPI và MySQL. CORS và cơ chế xử lý lỗi mất kết nối đã được kiểm thử thực tế.

Việc nghiệm thu đầy đủ F01 còn phụ thuộc vào kiểm thử xác thực với Backend thật và xác nhận các trường hợp chưa kiểm thử.