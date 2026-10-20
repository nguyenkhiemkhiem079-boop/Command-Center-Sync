# Báo cáo triển khai Agent World 3D

Ngày triển khai: 19-10-2026 (Asia/Bangkok). Bản source: `feature/agent-world-3d` tại `cf755c69783a66fd14ade5cc248f816f5eb4effd`. Địa chỉ Dashboard: `http://127.0.0.1:8876/ui`.

Agent World 3D đã được thêm vào Dashboard đang chạy tại `C:\KTOOL\CommandCenter\MCP`. Bản triển khai giữ Dashboard v0.7 đang cài và chỉ bổ sung bảy file đã thử trên bản sao tương thích: route server cho asset allowlist và Cockpit đã xác thực; nút điều hướng; adapter trang; module Three.js cục bộ; CSS và license. Không thay Registry, cấu hình role/token, MCP client, worktree hay source K-TOOL Revit. Coordinator được khởi động lại bằng cùng Python 3.12 và port loopback `8876`.

Trước khi chép file, SQLite online backup `registry-20261019T011357513516Z.db` được xác minh bằng `PRAGMA integrity_check=ok`, SHA-256 `5f98da1b61295fb4a938d3c17f8d1ea568bab67f30082d95778e68f72cd263d5`. Snapshot khi coordinator khởi động có cùng SHA; Registry không đổi qua lần triển khai. Bản sao file cũ, hash trước/sau, log khởi động, manifest và browser evidence nằm trong `C:\KTOOL\CommandCenter\deployments\20261019-AGENT-WORLD-3D-cf755c6`.

## QA sau triển khai

| Kiểm tra | Kết quả | Bằng chứng |
|---|---|---|
| Python regression, Python 3.12 với dependency lock có hash | PASS, 235/235 | `retest-20261019.txt` trong thư mục này |
| Frontend test, production build, npm audit | PASS, 6/6; build thành công; 0 lỗ hổng mức high | `C:\KTOOL\CommandCenter\deployments\20261019-AGENT-WORLD-3D-cf755c6\frontend-retest.log` |
| Chrome trên bản staging dựng từ server/orchestration v0.7 đang cài | PASS, WebGL2 | `browser-compat\webgl.json` và `webgl.png` |
| Chrome với WebGL tắt, fallback 2D | PASS | `browser-compat\fallback.json` và `fallback.png` |
| Staging xác thực bằng Registry/token dùng một lần; snapshot, Run Studio, Cockpit | PASS; API trả dữ liệu sau đăng nhập | Hai browser JSON ở trên; credential/Registry staging không chứa dữ liệu production |
| Không tải asset ngoài origin; lỗi JS runtime | PASS, 0 external request, 0 runtime exception | Browser JSON; console chỉ có các 401 trước đăng nhập và favicon 404 dự kiến |
| Live health và static assets | PASS; `/health`, `/ui`, Dashboard và asset Three.js/license trả 200 | `deployment-evidence.json` trong thư mục triển khai |
| Live API không có session | PASS; snapshot, Run Studio, Cockpit đều trả 401 `LOGIN_REQUIRED` | `deployment-evidence.json`; kiểm soát đăng nhập vẫn hoạt động |
| Revit runtime, RTX 3060 Ti performance, Teamwork Antigravity thật | NOT_EXECUTED / BLOCKED | Chưa có Revit runtime hoặc hai session Teamwork độc lập được xác minh |

Browser staging chạy Chrome `155.0.8059.41` với SwiftShader. Đây là kiểm chứng render và thao tác UI trên trình duyệt Windows, không đo hiệu năng GPU vật lý. Live API có thể hiện Agent World sau khi operator đăng nhập bằng CODEX token hiện có; token không được truy xuất hoặc đưa vào báo cáo. MCP connectivity không được xem là bằng chứng Teamwork.

## Khôi phục

Để rollback, dừng đúng tiến trình coordinator hiện tại sau khi xác minh command line, rồi khôi phục các file trong `before\` theo thư mục đích ban đầu. Khởi động lại `server.py --port 8876` bằng Python 3.12. Không cần restore SQLite vì migration hoặc thay đổi Registry không được thực hiện; chỉ khôi phục Registry từ snapshot nếu có bằng chứng độc lập cho thấy dữ liệu đã thay đổi ngoài dự kiến. Giữ nguyên role/token files.
