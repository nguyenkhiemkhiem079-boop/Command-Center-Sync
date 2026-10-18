# K-TOOL AI Command Center v0.6 — Reliability & Recovery

**Trạng thái:** PILOT. Đây là bản nâng cấp từ v0.5, chưa chứng minh điều khiển Teamwork Preview của 2 tài khoản Google hoặc chạy Revit 2025 trên Windows. Mọi khóa hiện tại vẫn do SQLite Registry quản lý, chưa phải `Can't Edit` enforced ở NTFS/GitHub.

## Mục tiêu

Bạn → Codex Team Lead → hai Antigravity **đồng thời code trong hai phạm vi khác nhau**, mỗi nhóm có thể dùng Teamwork nội bộ và tự QA → Codex dùng MCP review diff/build/tests/preview → feedback → Anti sửa trong đúng scope → Self-QA lại → Codex xem xét → tích hợp sau các gate. Không tự account rotation khi hết quota, không tự merge hoặc release.

### Khác biệt v0.6 so với v0.5

1. `Emergency Stop`: đóng băng toàn bộ khóa đang hoạt động, ngăn nhận task mới. **Không tự dừng tiến trình Windows**.
2. Restart / mất điện: lần khởi động Coordinator tiếp theo tự sao lưu SQLite **trước schema migration**, rồi đóng băng toàn bộ khóa `ACTIVE` và đưa Control Plane vào `RECOVERY_REQUIRED`.
3. `QUOTA_EXHAUSTED` hoặc `DISCONNECTED` do worker báo cáo: đóng băng task của worker, không làm ngưng task không liên quan. Không coi báo cáo quota là bằng chứng xác thực từ Google.
4. Codex có thể quét heartbeat cũ: `stale_sweep`. Thiếu heartbeat **không tự thu hồi quyền**.
5. `resume_control` cần xác nhận người vận hành đã dừng worker và kiểm tra backup; `resume_frozen_task` chỉ cho **cùng chủ cũ** tiếp tục với **fencing token mới**. Không có chuyển tài khoản tự động.
6. `exclusive_resources`: nếu hai task đụng cùng Shared Core contract, khóa resource chặn dù thư mục riêng. `depends_on`: task phụ thuộc không được giao trước khi upstream CLOSED.
7. Codex không thể `PASS_CODE_REVIEW` nếu chưa có bản ghi Local QA Runner PASS tương ứng **task + QA round + commit SHA**. Chỉ click/khai `build_verified=true` là không đủ.
8. Local QA Runner (`qa_runner.py`) đối chiếu commit thực của Git, SHA baseline, Git diff/scope, trạng thái dirty và tự chạy hai command build/test từ QA profile cấu hình riêng của supervisor.
9. Ba lần liên tiếp cùng một structured feedback không thay đổi: tự `FROZEN` để ngăn vòng sửa lỗi vô hạn.
10. Bảng điều khiển có **Recovery Center** và ghi rõ giới hạn runtime/OS enforcement.

## Cài mới trên Windows

- Python **3.11+**; máy bạn đã có Python 3.12.10. Cần Git trong PATH. Revit 2025 dùng riêng cho host QA.
- Giải nén ZIP vào một thư mục tách biệt, ví dụ `C:\KTOOL\CommandCenter\MCP`.
- Nhấp `01_SETUP.bat` để tạo roles và token, **không chia sẻ token**. Cài `mcp` package theo `requirements.txt` nếu script installer báo thiếu.
- Chạy `02_START_DASHBOARD.bat` và mở `http://127.0.0.1:8876/ui`.
- Dùng **CODEX token** để đăng nhập Dashboard. Theo `scripts/install-client.ps1` cài stdio adapter cho từng Windows profile độc lập.

**Quan trọng:** Hai Antigravity chỉ có thể lấy/gửi task qua MCP khi đã được đăng nhập/chạy chính thức và thực sự kết nối MCP. MCP không tự bật `/teamwork-preview` trên tài khoản Google của bạn.

## Nâng cấp từ v0.3 / v0.4 / v0.5 — bảo toàn dữ liệu

1. Dừng Coordinator cũ (cửa sổ chạy `02_START_DASHBOARD.bat`, `server.py`). Dừng/đóng băng hai phiên làm việc trước khi nâng cấp.
2. Giải nén v0.6 **sang thư mục khác**, không giải nén đè lên thư mục đang dùng.
3. Mở PowerShell và chạy:

```powershell
cd "C:\DuongDan\KTOOL_Command_Center_v0_6"
.\UPGRADE_EXISTING_MCP.ps1 -Target "C:\KTOOL\CommandCenter\MCP"
```

4. Script dùng SQLite online backup (WAL-safe), lưu bản sao code trước đó, cập nhật code/UI/docs, **không ghi đè `private\roles.json` hoặc token**.
5. Khởi chạy lại server. Khi Registry phát hiện khóa đang `ACTIVE` từ phiên trước, nó đưa task về `FROZEN` và mode `RECOVERY_REQUIRED`.
6. Kiểm tra Recovery Center và snapshot. Sau khi xác minh worker thật đã dừng, bấm **Mở lại Control Plane**. Sau đó `Khôi phục` task cùng owner; fencing cũ không còn hợp lệ.
7. Restart cả Codex và hai MCP client để nhận các tool mới.

## QA Runner — chạy từ Supervisor, KHÔNG chạy bằng account worker

Copy `config/qa_profile.example.json` thành `config/qa_profile.local.json` và sửa các đường dẫn `dotnet build`, `dotnet test` phù hợp solution K-TOOL thật. Chỉ supervisor được sửa QA profile, bảo vệ bằng Windows ACL. Đừng dùng lệnh dummy như `echo OK` để đánh dấu QA của dự án thật.

Sau khi một Anti `submit_self_qa PASS` + `submit_result`, chạy:

```powershell
py -3 .\qa_runner.py --task ARCH-011 --repo "D:\KTOOL\Workspaces\Anti-01-Arch" --profile ".\config\qa_profile.local.json"
```

QA Runner sẽ từ chối khi HEAD khác commit worker đã nộp, Git tree dirty, source có thay đổi ngoài scope, baseline commit không tồn tại hoặc build/test lỗi. Codex mới có thể review PASS khi **có bằng chứng PASS của runner**, và với task yêu cầu preview vẫn cần xác nhận preview có evidence. **Không tự gán Revit Host QA PASS.**

Mỗi lần sắp Sync, tạo backup:

```powershell
.\scripts\backup-before-sync.ps1
```

> Lưu ý bảo mật: trên một Windows profile chung có quyền sửa `private/registry.db` hoặc QA profile, agent có thể giả mạo kết quả. Trước khi production phải dùng supervisor Windows account tách biệt, NTFS ACL, GitHub required checks và CI runner tin cậy. Bản v0.6 chưa thực hiện đầy đủ các điều kiện đó.

## Dừng khẩn cấp và phục hồi

- Tab **Recovery Center** → `Emergency Stop`: chặn job mới, đóng băng khóa. **Dừng tiến trình Antigravity thật là công đoạn Windows riêng**.
- Chạy `py -3 backup_registry.py` và đối chiếu SHA256/integrity check.
- Xem `control_status` và `audit_log`. Không tự xóa row khóa trong SQLite.
- Codex chỉ `resume_control` sau khi **bạn** đã xác minh an toàn và cho phép. Từng task FROZEN sẽ tiếp tục cùng chủ cũ với fencing token mới.
- Nếu task phụ thuộc Core hoặc có ba lần feedback trùng lặp → sửa root cause/task contract theo quyết định được duyệt, không chạy vô hạn.

## Thứ tự pilot hai Antigravity

1. Anti-01 làm `ARCH-011` (ví dụ Envelope Areas), Anti-02 làm `DOC-012` độc lập.
2. Mỗi nhóm nhận task, heartbeat, checkpoint, self-QA, submit_result qua MCP.
3. Codex QA riêng từng commit với runner và preview, trả issue theo vòng. Không có chức năng tự khởi động Teamwork từ MCP trong bản này.
4. Thử cố ý giao Anti-02 vào cùng `architectural/envelope` → Registry trả `CANT_EDIT`.
5. Thử cả hai task khác thư mục nhưng cùng `exclusive_resources=["shared-revit-contract"]` → Registry trả `CANT_EDIT_SHARED_RESOURCE`.
6. Giả lập Anti-01 mất liên lạc → task Anti-01 bị `FROZEN`, Anti-02 tiếp tục.
7. Sau đó thử restart, recovery, stale fence, QA runner fail và Codex PASS gate.
8. Nghiệm thu Antigravity Teamwork thật, Windows NTFS/GitHub CI và Revit host riêng, không suy từ unit tests.

## Tình trạng nghiệm thu

- `SQLite/API/Registry`: có unit tests + local HTTP tests.
- `QA Runner + git`: đã có test repository Git local, command build/test mô phỏng, không phải build K-TOOL.
- `Dashboard`: static JS syntax; chưa có browser E2E trên Windows.
- `Codex ↔ MCP ↔ 2 Antigravity Teamwork`: **NOT_VERIFIED**.
- `Windows ACL / GitHub branch protection / CI`: **NOT_CONFIGURED**.
- `Revit 2025 real DLL/preview`: **NOT_EXECUTED**.
- `Production-ready`: **NO**.
