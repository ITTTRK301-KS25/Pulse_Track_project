# F11 – Bộ lọc và tìm kiếm task trên Kanban

## Phạm vi

- Tìm task theo từ khóa trong tiêu đề, không phân biệt chữ hoa/chữ thường.
- Lọc theo người thực hiện.
- Lọc theo hạn hoàn thành chính xác theo ngày.
- Ngày nhập trên Kanban dùng định dạng `dd/mm/yyyy`; khi lưu task, ngày được đổi sang định dạng API `YYYY-MM-DD`.
- Có thể kết hợp nhiều điều kiện và xóa toàn bộ bộ lọc.
- Bộ lọc chỉ thay đổi các task hiển thị trên bảng; không sửa dữ liệu task hoặc trạng thái.

Danh sách task được tải như trước. Các điều kiện được áp dụng trên dữ liệu đã tải để giữ đúng yêu cầu tìm theo tiêu đề; Backend và API không thay đổi.

## Kiểm tra thủ công

1. Mở `kanban.html` từ một dự án có task.
2. Nhập một phần tiêu đề và xác nhận chỉ task có tiêu đề khớp còn hiển thị.
3. Chọn người thực hiện và xác nhận các task thuộc người đó còn hiển thị.
4. Nhập hạn hoàn thành dạng `dd/mm/yyyy` ở bộ lọc và form task; xác nhận chỉ task có đúng ngày hạn còn hiển thị, ngày không hợp lệ bị báo lỗi.
5. Kết hợp các bộ lọc, sau đó chọn **Xóa bộ lọc** và xác nhận toàn bộ task trở lại.
6. Xác nhận số task trên từng cột và tổng số task hiển thị cập nhật theo bộ lọc.
