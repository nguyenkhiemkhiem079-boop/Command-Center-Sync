# Cầu Codex đến Antigravity IDE

## Trạng thái

Ngày 23-10-2026, MCP server `antigravity_ide_mcp.py` đã được đăng ký trong cấu hình Codex tại `%USERPROFILE%\.codex\config.toml`. `codex mcp list` nhận server là `antigravity-ide`, trạng thái `enabled`.

Đã gọi thử qua MCP đến cả hai workspace Antigravity IDE:

- `ANTI-01` — `C:\KTOOL\Workspaces\ANTI-01`
- `ANTI-02` — `C:\KTOOL\Workspaces\ANTI-02`

Cả hai agent đã trả lời đúng yêu cầu smoke check. Thử nghiệm không sửa file và không chạy lệnh trong workspace.

## Cách Codex sử dụng

MCP server cung cấp các công cụ:

- `list_antigravity_ide_agents`: kiểm tra IDE nào đang mở và truy cập được.
- `list_antigravity_ide_models`: xem model và quota của từng IDE.
- `start_antigravity_ide_task`: gửi task vào đúng workspace IDE; task có thể sửa code và dùng công cụ của IDE.
- `get_antigravity_ide_task_result`: lấy tiến độ hoặc kết quả theo `cascade_id`.
- `cancel_antigravity_ide_task`: dừng task đang chạy.

Quy trình điều phối: Codex làm rõ đầu ra và chia việc, chọn `ANTI-01` hoặc `ANTI-02`, gửi task trực tiếp qua MCP, theo dõi kết quả bằng `cascade_id`, rồi tổng hợp và review thay đổi. Model mặc định hiện là Gemini 3.8 Flash (High); dùng `list_antigravity_ide_models` để kiểm tra tên model và quota trước khi giao task.

## Điều kiện để kết nối

- Mở Antigravity IDE với workspace đúng tên ANTI-01 hoặc ANTI-02.
- Không mở nhiều cửa sổ cùng một workspace; server sẽ báo lỗi khi phát hiện trùng.
- Sau khi thay đổi MCP config, mở một Codex session mới nếu danh sách tool trong cửa sổ hiện tại chưa được tải lại.

## Giới hạn và an toàn

- Server chỉ gọi language server trên `127.0.0.1`; CSRF token được đọc từ process IDE lúc cần và chỉ giữ trong bộ nhớ. Token không được trả về qua MCP hay ghi vào file.
- Việc giao task cho phép agent thao tác trong workspace được chọn. Codex chỉ nên gửi task triển khai khi người dùng đã yêu cầu triển khai.
- Kết nối hiện dùng endpoint nội bộ của Antigravity IDE, không phải API bên ngoài được Google công bố ổn định. Nâng cấp IDE có thể làm đổi giao thức; khi đó cần chạy lại smoke check và cập nhật server.
- Google có tài liệu chính thức cho MCP trong Antigravity IDE và một Antigravity SDK riêng cho agent chạy bằng Python. SDK là lựa chọn phù hợp nếu sau này muốn xây agent độc lập; cầu hiện tại được chọn để điều khiển đúng hai IDE và account đang mở.
