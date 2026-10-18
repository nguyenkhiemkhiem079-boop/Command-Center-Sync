# Báo cáo sẵn sàng vận hành K-TOOL — sáng 19/10/2026

**Mức hiện tại: YELLOW — MCP READY.** Coordinator và ba MCP stdio identity hoạt động trong kiểm tra trực tiếp. Chưa có bằng chứng Antigravity IDE gọi MCP ở cả hai workspace, nên chưa thể xác nhận hai worker Antigravity thực hoặc Teamwork. Không đạt GREEN.

## Phạm vi và hiện trạng

- Cài đặt đang chạy: `C:\KTOOL\CommandCenter\MCP`; Dashboard `http://127.0.0.1:8876/ui`.
- HEAD nhánh phát triển của repo này: `4ebd891c5f6ff3011d935039484104a363138852` (`feature/full-fix-e2e-acceptance`). Giá trị trong `DEPLOYMENT.json` là `c377d103da179e3ef1f5d48a11d8d9e6d1ee5a3d`, nhưng đó là khai báo triển khai; thư mục cài không phải Git checkout nên chưa chứng minh được HEAD thực tế của bản cài.
- Listener duy nhất tại `127.0.0.1:8876` thuộc PID `23652`, chạy Python hệ thống 3.12.10; PID cha `44844` chạy Python trong venv. Hai tiến trình cùng lệnh server và ngày bắt đầu; hiện chỉ một listener. Không dừng hay khởi động lại dịch vụ.
- `/health`, `/ui`, JavaScript UI: HTTP 200. Registry SQLite `integrity_check=ok`; `user_version=0` và không có migration-version table rõ ràng. `pip check` sạch, còn khoảng 315.5 GB trống; bộ nhớ trống hệ thống khoảng 4.8 GB. Sleep khi cắm nguồn: không ngủ; dùng pin: 10 phút. Không đổi thiết lập nguồn.
- Task cũ `PILOT-ANTI01` và `PILOT-ANTI02` vẫn `FROZEN`, không có lock hoạt động. `UI-SMOKE` đang `QUEUED`, không owner. Probe RBAC tạo thêm `OVERNIGHT-RBAC-CODEX`, `QUEUED`, không owner/lock; không xóa trực tiếp DB. Chi tiết ở [MCP_CONNECTION_MATRIX.json](MCP_CONNECTION_MATRIX.json).

## Các cổng

| Cổng | Kết quả | Bằng chứng / giới hạn |
|---|---|---|
| Coordinator, health, Python/dependencies, DB integrity | PASS | PID/URL/commands trong báo cáo; `pip check`; SQLite integrity. |
| CODEX MCP initialize, tools/list, status | PASS | MCP stdio thật đến coordinator cài; 36 tool. |
| ANTI-01/02 stdio identity, task scope, negative RBAC | PASS | Mỗi identity đọc task của mình; đọc task khác, create/review bị từ chối theo role. |
| Reconnect adapter | PASS | Tiến trình stdio tạm mới cho ANTI-01 reconnect và status đúng. Không phải restart coordinator. |
| Dashboard login/session/API | PASS | CODEX login, snapshot, Run Studio, report, logout; sau logout snapshot trả 401. Giá trị token/session không ghi log. |
| Dashboard browser UI/console/responsive | NOT_EXECUTED | HTTP/API đã kiểm; chưa có browser UI automation ổn định trong lượt này. |
| Hai Antigravity IDE gọi MCP | BLOCKED — thao tác người vận hành | Cấu hình sẵn có nhưng cần mở đúng workspace, refresh server và duyệt tool theo UI. |
| Hai Teamwork thực, session overlap | NOT_EXECUTED | Không có session ID hoặc quan sát runtime đáng tin cậy. |
| Disposable worker harness | PASS — simulated/local fixtures | Hai fixture process chạy chồng thời gian, feedback/rework và combined integration; không phải Anti thật. |
| Recovery drill | PASS — disposable coordinator | 23 assertions; xem [RECOVERY_SMOKE_TEST.md](RECOVERY_SMOKE_TEST.md). Không restart production. |

Bộ regression cài đặt chạy bằng `C:\KTOOL\CommandCenter\venv\Scripts\python.exe -m unittest discover -s C:\KTOOL\CommandCenter\MCP\tests -v`: **155 tests, 0 failures, 2 skipped**. Hai test bị skip do log pilot `agy-01-teamwork.jsonl` và `agy-02-teamwork.jsonl` không có trong source; đây không phải xác minh phiên Teamwork. Log đầy đủ: `evidence/installed-regression.log`.

## Kết luận vận hành sáng mai

CODEX có thể dùng MCP coordinator qua adapter đã cấu hình. Hai logical Anti MCP identities cũng được backend nhận dạng và RBAC giới hạn đúng trong subprocess probe. Tuy nhiên, cho tới khi mỗi ứng dụng Antigravity thực sự kết nối từ workspace đúng, gọi `status`, đọc được assignment mới và ACK với evidence, hệ thống chỉ ở **YELLOW — MCP READY**. Hai assignment pilot cũ đang đóng băng; đừng triển khai code lên chúng và đừng dùng lại fencing epoch đó.

Để hoàn tất kiểm chứng: mở `C:\KTOOL\Workspaces\ANTI-01` trong Antigravity, refresh `ktool-anti-01`, duyệt riêng tool đọc `status` rồi đọc task chỉ khi owner xác nhận muốn đọc task FROZEN; lặp lại độc lập cho `ANTI-02`. Không bật auto-allow hoặc headless bypass. Sau khi có hai kết nối IDE được xác nhận, tạo task/worktree pilot mới ở repo dùng một lần; không tạo chúng trong Registry production trước bước đó.

Lệnh khởi động đề xuất tiếp theo là `scripts\start-local.ps1` trong thư mục cài đặt: script chọn Python venv, từ chối khi cổng đã được dùng và đợi `/health`. Không chạy khi PID hiện tại đang phục vụ. Tránh `02_START_DASHBOARD.bat` vì nó gọi `py -3 server.py` và chưa có kiểm tra cổng trước khi start.
