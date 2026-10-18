# K-TOOL v0.7 — một Windows user

Kiến trúc hiện hành dùng một Windows user. Không tạo Windows account hoặc VM mới trong pilot.
Coordinator: `C:\KTOOL\CommandCenter\MCP`; venv: `C:\KTOOL\CommandCenter\venv`.
Dashboard: http://127.0.0.1:8876/ui. Một SQLite Registry, ba token KTOOL khác nhau.

## Identity và giới hạn

- `ktool-codex`: CODEX; `ktool-anti-01`: ANTI-01; `ktool-anti-02`: ANTI-02.
- Credential references riêng: `%APPDATA%\KTOOLMCP\identities\<ROLE>\client_token.txt`.
- Adapter nhận `--identity` và `--token-file`, không nhận giá trị token trong command line. Backend xác thực token; identity không tự cấp quyền.
- Mỗi adapter kiểm tra actor do backend trả về trước khi phục vụ MCP; sai token/role phải fail closed.
- Token được pin trong tiến trình; cài role khác không đổi identity đang chạy. Credential v0.6 cũ được giữ để đối chiếu/rollback, không dùng làm fallback.
- MCP config của từng worktree nằm tại `.agents/mcp_config.json` theo tài liệu CLI chính thức; không ghi đè global MCP entries đang có.
- `ISOLATION_LEVEL=LOGICAL_ONLY`, `ROLE_SEPARATION_LOGICAL_ONLY`. Cùng Windows user có thể đọc/sửa credential và Registry nếu cố ý; ACL/DPAPI cùng user không tạo cách ly cứng.
- Chỉ dùng repo test không nhạy cảm. Không đặt CODEX entry trong global Antigravity config.

## Chạy/dừng/khôi phục

```powershell
& C:\KTOOL\CommandCenter\MCP\scripts\start-local.ps1
Invoke-RestMethod http://127.0.0.1:8876/health
& C:\KTOOL\CommandCenter\MCP\scripts\stop-local.ps1
```

Shortcut Startup hiện có chạy sau supervisor login; không phải SYSTEM service, chưa thử reboot.
Log timestamp mới ở `C:\KTOOL\CommandCenter\runtime`. Cổng bận thì không chạy Coordinator thứ hai.
Emergency Stop chỉ đóng băng Registry, không giết Antigravity.

1. Dừng/cô lập worker thật; kiểm tra checkpoint, source diff, Git status/SHA. Không tự reset code.
2. Python venv chạy `backup_registry.py`; kiểm tra manifest SHA256 và SQLite integrity `ok`.
3. Restart tự backup và chuyển ACTIVE lock sang FROZEN/RECOVERY_REQUIRED.
4. Chỉ xác nhận `resume_control` khi worker đã dừng và backup đã kiểm chứng; resume từng task cùng owner để cấp fencing mới.
5. Fencing cũ phải bị từ chối. Hết heartbeat/quota không nhả khóa, không đổi Google account.
6. Restore DB thủ công khi Coordinator dừng: giữ DB/WAL/SHM hiện tại trong backup được bảo vệ; mở snapshot đã kiểm tra trong thư mục recovery riêng; không ghép WAL/SHM cũ vào snapshot. Giữ roles/tokens; không bootstrap lại.

## QA và CI

Trusted QA profile có build/tests argv và tùy chọn allowed_paths/protected_paths. Không để worker chỉnh profile.
`qa_runner.py` kiểm SHA/base ancestor, name-status diff, paths, symlink/junction, clean tree và postflight.
Scope violation ghi FAIL rồi FROZEN giữ lock, không tự sửa/reset source.
`.github/workflows/scope-gate.yml` dùng checker/policy từ base commit, fail closed khi owner chưa cấp `.github/scope-policy.json`.
Workflow trong source chưa đồng nghĩa GitHub required checks/branch protection đã bật; production chờ owner cấu hình/duyệt.

## Hai Antigravity và Teamwork

Hai identity MCP không chứng minh hai Google account. Tài liệu hiện mô tả unified local sign-in; chưa xác minh account profile selector chính thức trên Windows.
Gate giữ `BLOCKED_TWO_ACCOUNT_TEAMWORK` tới khi có bằng chứng thực tế.
Theo quyết định owner, có thể thử Teamwork/session chính thức bằng tài khoản được cấp quyền hiện có, nhưng ghi rõ dùng chung account.
Không can thiệp OAuth/keyring/cookie hoặc dùng unofficial account launcher. Nếu CLI đòi login, owner thao tác qua giao diện chính thức.
`/teamwork-preview` phải được xác minh riêng từng session; MCP không tự chứng minh Teamwork.

Harness `tests/e2e_local_harness.py` tạo hai worker fixture, source/commit/test thật, feedback/fix/re-QA/integration; toàn bộ gắn TEST_HARNESS_NOT_ANTIGRAVITY.
Không suy thành Revit runtime PASS, hai Teamwork PASS hoặc owner release approval.
