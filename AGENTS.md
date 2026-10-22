# Quy trình điều phối agent cho Command Center

## Vai trò mặc định

- Codex làm kiến trúc, phân tích lỗi, viết spec và chia việc; khi người dùng yêu cầu triển khai, giao phần build cho agent trong Antigravity IDE qua MCP `antigravity-ide`.
- Đây là hai cửa sổ IDE thật: `ANTI-01` và `ANTI-02`. Không thay bằng `agy` CLI hoặc yêu cầu người dùng copy prompt thủ công.
- Codex chịu trách nhiệm theo dõi, review kết quả và báo rõ phần nào đã xác minh.

## Giao task

1. Gọi `list_antigravity_ide_agents` để xác nhận workspace cần dùng đang online. Gọi `list_antigravity_ide_models` nếu cần chọn model hoặc kiểm tra quota.
2. Gửi task có mục tiêu, phạm vi/file liên quan, tiêu chí hoàn tất và giới hạn rõ ràng qua `start_antigravity_ide_task`.
3. Lưu `cascade_id`, theo dõi bằng `get_antigravity_ide_task_result`, và dùng `cancel_antigravity_ide_task` nếu người dùng yêu cầu dừng.
4. Sau khi agent báo xong, kiểm tra diff/trạng thái workspace và tổng hợp kết quả cho người dùng. Không khẳng định đã pass kiểm thử nếu chưa chạy kiểm thử được người dùng yêu cầu.

## Chia việc và giới hạn

- Chỉ chạy song song khi hai task độc lập và không sửa cùng file. Nếu phạm vi có thể chồng lấn, giao tuần tự.
- Chỉ giao task triển khai khi người dùng đã yêu cầu build/fix. Với yêu cầu brainstorm/spec/plan, chuẩn bị đầu ra trước; chưa tự khởi chạy thay đổi code.
- Nếu MCP chưa xuất hiện trong phiên Codex hiện tại, nói rõ cần mở phiên mới để tải cấu hình; không giả vờ đã gửi task.
- MCP bridge dùng endpoint local nội bộ của Antigravity IDE. Nếu IDE nâng cấp làm bridge lỗi, xác minh lại giao thức trước khi gửi task tiếp theo.
