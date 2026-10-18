# Vận hành Antigravity có giám sát

Chế độ được chủ dự án chọn: SUPERVISED_MANUAL_LAUNCH. Không thêm allow-rule, không bỏ qua permission, không chuyển token Google.

1. Người vận hành mở Antigravity bằng cơ chế chính thức và đăng nhập tài khoản đã được cấp quyền. Một Windows user không chứng minh cách ly tài khoản.
2. Mở đúng workspace: ANTI-01 tại C:/KTOOL/Workspaces/ANTI-01; ANTI-02 tại C:/KTOOL/Workspaces/ANTI-02. Giữ nguyên cấu hình MCP riêng đã tạo trong .agents/mcp_config.json. Không chép token vào chat.
3. Trong từng phiên, kiểm tra danh sách MCP và yêu cầu status/get_task cho đúng identity. Nếu ứng dụng hỏi quyền, người vận hành quyết định trong ứng dụng; Codex không tự mở rộng quyền.
4. Trước khi code, lấy contract, scope và fencing token mới từ Codex. Task pilot hiện có không tự chứng minh owner execution context còn sống; không sử dụng fence cũ sau recovery.
5. Khởi chạy Teamwork Preview bằng giao diện/lệnh chính thức nếu phiên đó có. Lưu session/conversation ID, phiên bản, thời điểm bắt đầu/kết thúc và kết quả tool được phép; không lưu reasoning hoặc thông tin đăng nhập. MCP_CONNECTED không tương đương TEAMWORK_ACTIVE.
6. Hai phiên chỉ được nghiệm thu đồng thời khi có bằng chứng overlap thời gian, workspace/owner riêng và kết quả thực thi thật. Hai MCP credentials không chứng minh hai tài khoản Google độc lập. Nếu phiên thứ hai không được hỗ trợ, giữ gate BLOCKED_TWO_ACCOUNT_TEAMWORK.
7. Mỗi team commit riêng, Self-QA thật và gửi commit/checkpoint/evidence; đây là CLAIMED cho đến QA độc lập. Không team nào tự accept hoặc merge.
8. Khi quyền bị từ chối/worker gián đoạn, giữ khóa, checkpoint nếu được phép và báo blocker. Không retry với skip-permissions.

Bản hardening chỉ có source; không thay bản cổng 8876 trước phê duyệt triển khai. Protected CI/principal và Central writer thực vẫn chưa cấu hình, nên không có đường production acceptance/merge tự động.
