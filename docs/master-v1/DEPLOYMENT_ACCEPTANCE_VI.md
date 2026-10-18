# Nghiệm thu deployment local — 18/10/2026

Owner đã yêu cầu: “Triển khai lun đi, kh cần đợi 19:55”. Đã triển khai source c377d103da179e3ef1f5d48a11d8d9e6d1ee5a3d của feature/master-scope-v1-governance lên C:/KTOOL/CommandCenter/MCP. Đây là deployment bản đã có, không phải full completion của 56 mục Master Scope.

Dashboard đang chạy: http://127.0.0.1:8876/ui. Listener thực 127.0.0.1, PID23652; launcher44844. Service dùng venv đã có; pip check PASS. Không cài thêm user, không reset credentials, không merge/force-push/release. Native Antigravity vẫn supervised manual launch.

## Đã thực thi

- Source regression155/155 trước deployment, source code7f6629f; c377d10 thêm tài liệu không thay code.
- Tạo protected deployment folder, online SQLite snapshot integrity ok; source trước khi overwrite được lưu riêng. Không dùng legacy upgrade script có file inventory thiếu.
- Migration rehearsal trên bản sao DB: Registry + ControlStore hai lần; 3 task và2lock rows nguyên vẹn; human_requests_schema_version=2; PRAGMA integrity_check ok.
- Xác minh listener PID/path rồi stop đúng coordinator; thay100 tracked source files, giữ private/token stores và mọi file cấu hình cục bộ không thuộc manifest.
- Restart server.py --port8876 bằng venv, WindowStyle Hidden. Startup tự backup SQLite trước additive migration.
- Real fresh stdio MCP: CODEX/ANTI-01/ANTI-02, list36tools mỗi adapter, status đúng identity, human_request.deadline được discover. CODEX đọc controller snapshot; worker snapshot và cross-owner get_task bị403. Không gọi heartbeat giả agent hoặc tạo task thử trong live Registry.
- Kiểm tra sau deploy:100 source file hashes khớp,4 credential-reference hashes không đổi,3task/2lock toàn bộ row không đổi, live DB integrity ok và migrationv2 có.
- Actual Windows Chrome login localhost, overview/task counts/frozen locks, Run Studio và Recovery verified. Legacy resume disabled. Zero captured JS errors. Ảnh deployment-dashboard.png; DOM files trong evidence-deploy của workspace. Tab Dashboard giữ mở để owner dùng.

## Phạm vi nghiệm thu

Installation/restart/migration preservation/three MCP adapter roles/browser: PASS theo bằng chứng ở deployment-live-validation.json. MCP adapter tests không chứng minh Antigravity IDE đã kết nối hoặc hai Google accounts độc lập. Dashboard agent runtime NOT_VERIFIED là đúng; không gán trạng thái adapter smoke test thành native session evidence.

Protected trusted CI/principal: BLOCKED_NOT_CONFIGURED. Hai real Teamwork sessions: BLOCKED_TWO_ACCOUNT_TEAMWORK. Revit2025 host: NOT_EXECUTED. Human approval inbox/six-role RBAC/risk engine/dispatcher retry và những gaps khác vẫn theo crosswalk, không được tính thành đã hoàn tất sau deployment.

## Backup và rollback

Protected local folder: C:/KTOOL/CommandCenter/deployments/20261018-DEPLOY-c377d10. pre-deploy.json chỉ nằm local: exact overwritten/new-file inventory, pre-deployment source hashes, credential-reference digests và original task/lock snapshots. database-backup chứa online snapshot+SHA/integrity manifest; source-before chứa đúng các source file từng tồn tại; stage là source c377d10. Không upload folder backup, token store hoặc live DB.

Nếu cần rollback: ngừng cấp task, giữ mọi checkpoint mới, xác minh đúng coordinator path/PID và stop; so sánh source manifest để phát hiện edits sau deploy; phục hồi từng file cũ từ source-before. File mới cần cách ly theo manifest, không recursive-delete đường dẫn tính toán. Không đổi credential files. Nếu DB đã có giao dịch mới, không đè snapshot cũ: preserve current DB rồi reconcile trước. Nếu cần restore DB đã được duyệt, dùng SQLite snapshot đã integrity-verified khi service dừng, giữ failed/current DB cùng sidecars ở vùng backup, không copy đè DB đang mở. Khởi động rồi recheck integrity/RBAC/frozen locks/browser. Không drop cc_* để downgrade. Legacy unsafe resume vẫn không được dùng làm chứng cứ worker dừng.

Deployment này không đổi Git branches/worktrees của hai team. Hai task pilot FROZEN, lock_released=false. Muốn chạy tiếp cần operator thực hiện manual launch đúng workspace/session và Codex xác minh execution context trước khi cấp epoch mới; không tự bỏ qua permission denial.
