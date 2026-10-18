# Worksharing và worker smoke test

## Production Registry — chỉ đọc

- `PILOT-ANTI01`: owner `ANTI-01`, `FROZEN`, fencing epoch 1, scope `architectural/envelope`.
- `PILOT-ANTI02`: owner `ANTI-02`, `FROZEN`, fencing epoch 2, scope `documentation/schedules`.
- Không có active lock trong bảng lock; hai task FROZEN được giữ nguyên. Không tái sử dụng fencing epoch hoặc worktree của chúng.
- `UI-SMOKE`: `QUEUED`, chưa gán owner.
- Probe được gọi nhầm bằng CODEX hợp lệ đã tạo `OVERNIGHT-RBAC-CODEX`: `QUEUED`, không owner/lock. Không có API xóa an toàn; giữ lại và báo chủ dự án.

## Phép thử thật qua MCP

| Phép thử | Kết quả |
|---|---|
| ANTI-01 status identity và đọc `PILOT-ANTI01` | PASS, task vẫn FROZEN |
| ANTI-02 status identity và đọc `PILOT-ANTI02` | PASS, task vẫn FROZEN |
| ANTI-01 đọc task của ANTI-02 | Bị từ chối `ROLE_DENIED` |
| ANTI-01/02 tạo task | Bị từ chối `ROLE_DENIED` |
| ANTI-01/02 gọi review_task | Bị từ chối `ROLE_DENIED` |
| Hai Anti sửa task/worktree độc lập từ phiên Antigravity | NOT_EXECUTED |

## Disposable local harness

Lệnh: `C:\KTOOL\CommandCenter\venv\Scripts\python.exe C:\KTOOL\CommandCenter\MCP\tests\e2e_local_harness.py --out <repo>\docs\overnight-readiness\evidence\local-fixture`.

Kết quả đã quan sát: PASS; hai fixture worker subprocess chồng thời gian, task scopes riêng, independent QA bắt lỗi ở A, feedback/rework một vòng, A và B đạt test, integration candidate kết hợp đạt. Harness dùng worker giả lập do test tạo, không dùng Antigravity, không dùng production DB/token. `result.json` ghi rõ `TEST_HARNESS_NOT_ANTIGRAVITY` và `real_teamwork_concurrency: NOT_EXECUTED`.

Không cấp task mới cho worker trong production Registry trước khi operator xác nhận hai phiên app thực tế và chuẩn bị disposable repository/worktrees mới.
