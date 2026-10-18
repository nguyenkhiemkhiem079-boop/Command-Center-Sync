# Bàn giao local pilot — 18/10/2026

Coordinator được cài tại `C:\KTOOL\CommandCenter\MCP`, Python venv tại `C:\KTOOL\CommandCenter\venv`.
Dashboard: http://127.0.0.1:8876/ui. Chỉ CODEX token được đăng nhập; không đưa token vào chat.
Codex MCP đã cấu hình bằng executable của venv, adapter `client_mcp.py` và token trong APPDATA của supervisor.

## Chạy và dừng

```powershell
& C:\KTOOL\CommandCenter\MCP\scripts\start-local.ps1
Invoke-RestMethod http://127.0.0.1:8876/health
& C:\KTOOL\CommandCenter\MCP\scripts\stop-local.ps1
```

Shortcut `KTOOL Command Center.lnk` trong Startup của supervisor chạy khi người dùng này đăng nhập.
Không phải Windows service; chưa thử reboot. Log mới ở `C:\KTOOL\CommandCenter\runtime`.
Nếu cổng bận, script từ chối chạy thêm Coordinator. Không tắt tiến trình không liên quan.

## Khôi phục an toàn

1. Dừng/cô lập worker thật và xác minh Git status, commit, checkpoint. Emergency Stop chỉ đóng băng Registry.
2. Sao lưu trước sync/recovery bằng Python venv chạy `backup_registry.py`. Backup DB nằm dưới `private/backups`.
3. Đối chiếu SHA256 với JSON manifest và `PRAGMA integrity_check` trả `ok`.
4. Restart giữ khóa và đóng băng task đang hoạt động. Không xóa Registry, roles hoặc chạy lại bootstrap.
5. Chỉ sau xác nhận owner mới gọi `resume_control` với các xác nhận thật; tiếp tục từng task cùng owner qua `resume_frozen_task`.
6. Worker phải lấy fencing mới. Fencing cũ bị từ chối. Không đổi tài khoản để né quota.
7. Restore DB thủ công: dừng Coordinator/worker; giữ nguyên DB, WAL và SHM hiện tại trong thư mục backup được bảo vệ; sao chép snapshot đã kiểm tra thành DB trong thư mục recovery riêng; kiểm tra lại dữ liệu/schema trước khi chọn DB phục hồi. Không chép đè DB đang mở, không trộn WAL/SHM cũ vào snapshot. Không khôi phục token từ ZIP báo cáo vì ZIP không chứa token.

## Phần cần operator

Operator xác nhận hiện chưa có hai môi trường Antigravity riêng. Không cài ANTI-01/02 vào profile supervisor đang giữ CODEX token.
Chuẩn bị hai Windows user/máy/VM được cấp quyền; đăng nhập chính thức trong từng môi trường. Không gửi mật khẩu/OAuth/token vào chat.
Windows 11 Pro có nhiều profile không chứng minh GUI đồng thời; phải thử concurrency thật hoặc dùng CLI được hỗ trợ trong hai môi trường hợp lệ.

Sau đó Codex thực hiện phần còn lại:

- Kiểm tra đúng config MCP qua CLI/App chính thức, giữ các server có sẵn, backup config.
- Dùng Python venv; không chạy phần `pip --user` của installer baseline. Installer baseline chưa được dùng để triển khai worker và có khả năng ghi đè entry; cần điều chỉnh theo config thực trước khi sử dụng.
- Operator chuyển đúng token KTOOL qua kênh local được bảo vệ vào APPDATA riêng; không sao chép OAuth Google.
- Cấp ACL tối thiểu cho worktree đúng owner và kiểm thử đọc/ghi bị từ chối ở worktree khác/private/QA profile. Kiểm tra Git common metadata trước khi cho phép commit; worktree riêng tự nó không tạo boundary bảo mật.
- Mỗi Anti gọi thật status, heartbeat, get_task. Worker không được dùng CODEX token, create_task, review PASS hoặc resume admin.
- Mở `/teamwork-preview` trong App/CLI chính thức cho từng môi trường, duyệt prompt artifact rồi chạy task đúng scope. Không có adapter điều khiển từ xa Teamwork được triển khai.
- Tasks `PILOT-ANTI01` và `PILOT-ANTI02` đang QUEUED/unassigned. Git worktrees đã chuẩn bị ở `C:\KTOOL\Workspaces\ANTI-01` và `ANTI-02`. Không có commit triển khai của Anti.
- Codex review diff/SHA thật, build/test, phản hồi có cấu trúc, chạy lại QA và integration trong worktree riêng trước khi đề nghị owner duyệt merge.

## Giới hạn

Khóa hiện là REGISTRY_ONLY. Chưa nghiệm thu ACL bằng hai worker OS thật, GitHub protection/CI, hai Teamwork, Revit runtime, mất điện hoặc dừng toàn bộ descendant của build bị timeout.
Không release/merge/push tự động. `SHA256_MANIFEST.json` được giữ từ baseline để truy nguồn; manifest bàn giao mới nằm trong gói báo cáo.
