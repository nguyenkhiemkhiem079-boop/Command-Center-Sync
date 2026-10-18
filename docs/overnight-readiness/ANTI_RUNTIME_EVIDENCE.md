# Bằng chứng runtime Antigravity

## Trạng thái

**BLOCKED / NOT_EXECUTED cho phiên Antigravity thật và Teamwork.** Các cấu hình MCP workspace tồn tại ở:

- `C:\KTOOL\Workspaces\ANTI-01\.agents\mcp_config.json` → server `ktool-anti-01`, role/token reference `ANTI-01`.
- `C:\KTOOL\Workspaces\ANTI-02\.agents\mcp_config.json` → server `ktool-anti-02`, role/token reference `ANTI-02`.

Hai workspace là Git worktrees riêng trên nhánh `pilot/anti-01` và `pilot/anti-02`, base `c4157c5d781de811b18ec1c4e9061377342511b8`. Chúng gắn với task FROZEN hiện có; không chỉnh sửa hoặc ghi đè. Cấu hình MCP để hiển thị các tool, nhưng không có allow-rule được thêm. Phải duyệt bằng UI của Antigravity theo cơ chế hiện hành.

Tiến trình Antigravity được quan sát tại `C:\Users\khiem.nguyen\AppData\Local\Programs\antigravity\Antigravity.exe` (PID root 46248). CLI shim `agy` không có trên PATH; `antigravity --help` không chạy được. Có một thư mục user-data dùng chung `C:\Users\khiem.nguyen\AppData\Roaming\Antigravity`; không có bằng chứng hai provider sessions độc lập.

Không ghi nhận session ID, PID riêng cho mỗi Anti, lời gọi MCP trong IDE, thời gian overlap, assignment ACK, checkpoint hoặc Teamwork session. Trạng thái Teamwork là **UNKNOWN**, không phải PASS.

## Hướng dẫn supervised manual launch

1. Trong Antigravity, mở workspace `C:\KTOOL\Workspaces\ANTI-01`; vào MCP settings/manager, refresh `ktool-anti-01`.
2. Duyệt đúng lời gọi chỉ đọc `status`. Kiểm tra actor trả về là `ANTI-01`. Ghi nhận bằng chứng không bí mật (thời gian, workspace, tên server, actor, kết quả).
3. Không gọi công cụ sửa task/lock. Nếu chủ dự án muốn task retrieval, chỉ đọc `PILOT-ANTI01` và ghi nhận trạng thái FROZEN; không nhận/chạy task này.
4. Lặp lại trong phiên/workspace `C:\KTOOL\Workspaces\ANTI-02` với `ktool-anti-02`; actor phải là `ANTI-02`.
5. Nếu app từ chối hoặc không hiện server, giữ trạng thái BLOCKED; lưu thông báo denial/phiên bản app đã làm sạch bí mật và dừng, không thêm allow-rule tự động.

MCP stdio subprocess đã được xác minh riêng cho ba identity; điều này không phải bằng chứng app Antigravity kết nối. Tham khảo [MCP docs của Google](https://antigravity.google/docs/mcp) về cấu hình server MCP theo workspace và permission UI. Headless CLI không được dùng để suy ra Teamwork; tài liệu CLI cảnh báo lệnh có thể kết thúc thành công dù tool bị soft-deny: [Antigravity Headless CLI](https://www.antigravity.google/docs/cli/headless/).
