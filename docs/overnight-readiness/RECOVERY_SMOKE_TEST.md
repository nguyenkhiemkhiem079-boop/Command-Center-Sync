# Recovery smoke test

## Cổng production không tác động

Không restart, kill hoặc thay đổi coordinator production; không reboot Windows; không sửa task/lock FROZEN; không đổi credentials hoặc power settings.

## Disposable drill

Chạy: `C:\KTOOL\CommandCenter\venv\Scripts\python.exe C:\KTOOL\CommandCenter\MCP\tests\process_recovery_drill.py`.

Kết quả: **PASS, 23/23 assertions** trên SQLite/Registry, token test-only, Git baseline và HTTP coordinator trong thư mục tạm. Drill dừng đúng child process mà chính test đã tạo, restart tiến trình disposable, xác minh checkpoint tồn tại, task đang chạy thành FROZEN, SQLite backup/integrity/hash, fencing cũ bị từ chối, Emergency Stop chặn ghi và legacy Boolean không đủ để resume. Task độc lập khác vẫn ghi checkpoint được trước crash.

Giới hạn: quota là event mô phỏng; không phải Google quota. Không thử mất điện/reboot hoặc process Antigravity thật. `legacy_safe_resume` tiếp tục BLOCKED cho tới khi có bằng chứng dừng worker được xác minh. Drill này không chứng nhận recovery của coordinator production đang chạy.

## Khởi động và sleep

Script an toàn được xác định: `C:\KTOOL\CommandCenter\MCP\scripts\start-local.ps1`; nó chọn interpreter venv, từ chối nếu cổng đã chiếm, kiểm tra health. Không chạy lại khi listener đang hoạt động. `02_START_DASHBOARD.bat` gọi `py -3` và không kiểm tra port trước; tránh dùng để khởi chạy lần kế tiếp.

Windows sleep: AC = Never; battery = 10 minutes. Không thay đổi global settings; để máy cắm nguồn khi cần phục vụ liên tục. Không có kiểm tra Windows restart thực tế.
