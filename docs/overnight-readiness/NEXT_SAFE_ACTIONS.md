# Hành động an toàn tiếp theo

1. Giữ coordinator đang chạy và cắm nguồn cho máy. Không chạy installer hoặc start script khi port 8876 đang có listener.
2. Mở Antigravity workspace `C:\KTOOL\Workspaces\ANTI-01`, refresh `ktool-anti-01`, duyệt riêng `status`; xác nhận actor `ANTI-01`. Ghi thời gian và kết quả không bí mật.
3. Lặp lại ở `C:\KTOOL\Workspaces\ANTI-02`, server `ktool-anti-02`, actor `ANTI-02`. Nếu denial xảy ra, giữ nguyên denial và báo lại; không thêm allow-rule.
4. Chỉ sau khi cả hai lời gọi IDE thật đạt, tạo nhiệm vụ mới cho pilot trong disposable repository/worktrees riêng; kiểm tra scope khác nhau và resource locks trước khi dispatch. Không dùng `PILOT-ANTI01/02` đang FROZEN.
5. Quan sát ACK và checkpoint thật của từng worker; yêu cầu self-QA nhưng vẫn coi đó là claim. Codex phải review diff/test evidence độc lập. Không tích hợp branch vào Central trong readiness pilot.
6. Mở `http://127.0.0.1:8876/ui` trong browser để kiểm tra giao diện trực quan, console và refresh. Báo lỗi/API state; không dùng UI để sửa task production trong đợt kiểm tra này.
7. Xử lý task `OVERNIGHT-RBAC-CODEX` qua một cleanup mechanism được hỗ trợ khi có sẵn; không chỉnh SQLite trực tiếp.

Các bước 2–5 cần người vận hành tương tác với Antigravity và cấp quyền bằng UI của ứng dụng. Không chia sẻ token hoặc mã đăng nhập trong chat.
