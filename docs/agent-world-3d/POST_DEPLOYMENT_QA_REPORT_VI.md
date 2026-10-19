# Báo cáo QA và sửa lỗi Agent World 3D sau triển khai

Ngày: 19/10/2026 (Asia/Bangkok)  
Nhánh: `feature/agent-world-3d`  
Commit được rà soát ban đầu: `7a87fccbd474d2663cc66f390abc1b80f80e4aa0`  
Dashboard production: `http://127.0.0.1:8876/ui`

## Kết quả chính

Đã sửa lỗi gộp `CODE_REVIEWED` và `PASS_CODE_REVIEW` thành `ACCEPTED`. Agent World hiện tách review pass, integration pending/in progress, approval pending, accepted và integrated; assignment chỉ được hiển thị `ACCEPTED` khi đúng trạng thái controller. Snapshot quá 5 phút hoặc lệch tương lai trên 1 phút không còn được trình bày như trạng thái mới. Task/lock `FROZEN` vẫn hiện là blocked để không làm mất dấu ownership hold.

Thay đổi chỉ ở nhánh phát triển. Dashboard trên cổng 8876, Registry, credential files, tasks, worktrees và các lock đóng băng không bị sửa/restart/deploy. Việc triển khai trước đó được owner yêu cầu trực tiếp (“Triển khai lun đi, kh cần đợi 19:55”); yêu cầu hiện tại không cho phép triển khai lần nữa, nên bản sửa source này chưa được cài vào production.

## Source và kiểm thử

| Gate | Kết quả | Bằng chứng |
|---|---|---|
| Lifecycle mapping, mọi transition chính | PASS | 9 test Node trong `frontend/agent-world/src/state.test.js` |
| FROZEN, trạng thái không nhận diện, observation cũ/timestamp tương lai | PASS | Test stale giữ nguyên FROZEN, đưa RUNNING/review cũ về UNKNOWN |
| Python regression | PASS | `post-review-full-regression.txt`: `Ran 235 tests ... OK` |
| Frontend test | PASS | `npm test`: 9/9 |
| Production bundle | PASS | `npm run build`, Three.js/Vite pin hiện có, tạo `web/agent-world/agent-world.js` |
| Dependency advisory | PASS | `npm audit --audit-level=high`: 0 vulnerabilities |
| Diff whitespace check | PASS | `git diff --check` (chỉ báo chuẩn hóa CRLF khi Git ghi file) |
| Backend auth/RBAC | PASS, không đổi | Full suite 235 test hiện có; thay đổi mới chỉ là read-only frontend mapping |

Mapping đã kiểm tra gồm `QUEUED`, `TASK_ASSIGNED`, `ACKNOWLEDGED`, `DEVELOPMENT`, Self-QA/submission, `SYNC_REQUEST`, feedback/rework, review pass, PREPARE/VALIDATE, integration QA, approval pending, `ACCEPTED`, `INTEGRATED`, `FROZEN`, UNKNOWN và trạng thái tương lai không nhận diện.

## Hosted CI và policy migration

PR #4 vẫn mở, chưa merge. Check mới nhất trước commit sửa này là run `39184826232`, job `117844923574`, trên head `7a87fcc`; job kết thúc exit 2 sau 3 giây. [GitHub Actions job](https://github.com/nguyenkhiemkhiem079-boop/Command-Center-Sync/actions/runs/39184826232/job/117844923574?pr=4).

Base policy hiện có `approval_state=PENDING_OWNER_APPROVAL`, chỉ assignment `CI-PILOT` với phạm vi `ci-pilot/`; workflow trusted-base đang gọi cố định assignment đó. Do đó `OWNER_APPROVED_BASE_POLICY_REQUIRED` là kết quả fail-closed dự kiến. Sau khi sửa approval state, PR #4 vẫn không được bao phủ bởi CI-PILOT; thêm nữa PR có `server.py` và `tests/` đang được policy đánh dấu protected. Không đổi policy, workflow, protection hoặc assignment trong source candidate.

Đã chuẩn bị [SCOPE_POLICY_MIGRATION_REVIEW.md](SCOPE_POLICY_MIGRATION_REVIEW.md) để reviewer độc lập xem xét một assignment riêng, ràng buộc repo/PR/head branch và ngoại lệ đường dẫn chính xác nếu owner quyết định chấp thuận. Tài liệu đánh dấu rõ proposal không phải policy trusted và không thể làm CI xanh. Cổng CI giữ nguyên; PR #4 không được merge cho tới khi policy migration được owner duyệt và check thật pass.

## Dashboard đang chạy và giới hạn xác minh live

Quan sát Windows lúc kiểm tra:

- Listener cổng `8876`: PID `45384`, `python.exe` tại `C:\Users\khiem.nguyen\AppData\Local\Programs\Python\Python312\python.exe`, chạy `C:\KTOOL\CommandCenter\MCP\server.py --port 8876`.
- `/health` và `/ui`: HTTP 200.
- `/ui/api/snapshot`, `/ui/api/run-studio`, `/ui/api/cockpit`: HTTP 401 khi gọi không kèm phiên; authentication gate còn hoạt động.
- Hash SHA-256 bundle production `C:\KTOOL\CommandCenter\MCP\web\agent-world\agent-world.js`: `15dede23ade895d9958a0d66724e2681639dedc7a71a44ffd11ecd4a5b19f3e4`.
- Hash SHA-256 bundle source candidate `web/agent-world/agent-world.js`: `2f59c19b0c61cbd346c77461e4e008e33ba8fb92bdae6c70e357751eb402d5df`.

Hai lần gọi công cụ quan sát cửa sổ Windows bị timeout. Cửa sổ Edge nhìn thấy có tiêu đề Google Sheets; cửa sổ Chrome chính hiện là Picture-in-picture. Tôi không đọc profile/token và không dùng phiên khác. Vì không có phiên đã xác thực để mở, thao tác Agent World/Fleet/Timeline, camera, lọc mission, logout, refresh/reconnect và console trên live Dashboard được ghi **BLOCKED**, không lấy staging thay cho live. Screenshot production không thu thập được. Screenshot ở mục GPU dưới đây chỉ là staging.

## GPU, bộ nhớ và WebGL

Máy báo **NVIDIA GeForce RTX 3050, 4 GB**, không có RTX 3060 Ti. Dùng Chrome hiển thị 155.0.8059.41 trên staging loopback, profile/Registry/token dùng một lần; renderer WebGL2 được kiểm tra qua `WEBGL_debug_renderer_info`:

`ANGLE (NVIDIA, NVIDIA GeForce RTX 3050 (0x00002584) Direct3D11 vs_5_0 ps_5_0, D3D11)`

Trong 180,007 ms: 4,500 cụm WebGL draw, khoảng 25 draw batches/giây (scene giới hạn tối đa 30 fps). Heap JS đo bằng Chrome `performance.memory`: đầu 7,832,196 byte; cuối 8,271,601 byte; đỉnh lấy mẫu mỗi giây 13,357,356 byte; 180 mẫu. Heap cuối gần mức đầu; Chrome GC làm heap dao động. Đây là soak ngắn 3 phút, không chứng minh ổn định mission nhiều giờ. GPU utilization/VRAM không được Chrome harness cung cấp và vẫn `UNKNOWN`.

WebGL context loss/restore test: PASS; fallback xuất hiện khi mất context, canvas trở lại sau restore. Runtime exception: 0; off-origin requests: 0. Console có 401 trước login staging và 404 favicon; authenticated staging requests sau login thành công. Bài test dùng Registry/credential tạm và không đại diện cho dữ liệu Anti thật.

Screenshot staging: [agent-world-chrome-hardware-gpu.png](AGENT_WORLD_SCREENSHOTS/agent-world-chrome-hardware-gpu.png). SHA-256: `f3d5a556a80381e0afccbe5f50f762658418ea44ffd635e7298868717641fd1f`. JSON đo: `AGENT_WORLD_SCREENSHOTS/browser-hardware-gpu-e2e.json`. RTX 3060 Ti target gate: **NOT_EXECUTED**.

## Acceptance và việc còn lại

| Gate | Trạng thái |
|---|---|
| State accuracy + stale behavior | PASS |
| Regression/build/dependency audit | PASS |
| Production service/API reachability | PASS (health/UI 200; protected APIs 401 unauthenticated) |
| Live authenticated UI interaction and screenshots | BLOCKED — không tìm thấy phiên browser có Dashboard; công cụ UI timeout |
| Physical hardware WebGL on current machine | PASS trên RTX 3050 staging |
| Long-session/VRAM/RTX 3060 Ti performance | NOT_EXECUTED |
| Hosted scope policy / PR #4 required check | BLOCKED — owner-approved trusted-base migration còn thiếu |
| Real Antigravity/Teamwork observations | UNKNOWN / NOT_EXECUTED; Agent World giữ read-only |
| New production deployment, merge or release | NOT_EXECUTED; yêu cầu owner approval vẫn áp dụng |

Artifact hashes, source diff, CI run and current pushed commit will be appended after the validated development commit is pushed. Không có thay đổi nào lên production trong đợt QA này.
