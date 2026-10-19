# Giai đoạn 2 — Animation và tương tác Chibi

**Trạng thái:** PASS trên unit/regression và Chrome staging. Không triển khai vào Dashboard live.

## Thay đổi

- `frontend/agent-world/src/chibi.js`: thêm trạng thái runtime fail-closed, dấu `?` cho UNKNOWN, `!` cho FROZEN/BLOCKED, gear/bàn phím chỉ cho trạng thái đang làm đã xác minh; thêm blink/nhún nhẹ cho runtime đã xác minh, chuyển động làm việc chỉ khi cả session và assignment có bằng chứng VERIFIED/FRESH/CONTROLLER; hover và nhảy chọn agent.
- `frontend/agent-world/src/main.js`: ánh xạ dữ liệu controller vào avatar; vòng/ring đổi theo ownership state; kết nối pointer hover/click với inspector và giữ camera preset/view cũ; dừng cập nhật scene khi view không phải 3D.
- `frontend/agent-world/src/chibi.test.js`: kiểm tra UNKNOWN, MCP-only, worker-reported, VERIFIED in-progress, FROZEN, reduced motion, hover và click feedback.
- `web/agent-world/agent-world.js`: bundle local được build từ Three.js đã pin sẵn.

## Bằng chứng

- `npm test`: **16/16 PASS**.
- `npm run build`: **PASS**, Vite 8.3.4; Three.js 0.186.1 được bundle local.
- `python -m unittest tests.test_agent_world tests.test_dashboard_v07 tests.test_dashboard -q`: **29/29 PASS**.
- `python tests/run_agent_world_browser_staging.py`: **PASS**, disposable registry, Chrome 155, 7 camera preset screenshots, Fleet 2D/Timeline/selection/fallback hoạt động; 0 runtime exception, 0 request ngoài localhost. Console có 401 trước login và 404 từ route âm tính/path traversal test; không phải lỗi runtime.

Ảnh: `AGENT_WORLD_SCREENSHOTS/agent-world-chrome-staging-camera-*.png`.

## Giới hạn

Chưa thay material bằng toon 3 bậc/outline/bóng tiếp xúc; phần đó thuộc Giai đoạn 3. Browser staging đang dùng SwiftShader nên không dùng làm bằng chứng hiệu năng GPU. Không có dữ liệu agent thực tế trong disposable registry; không tuyên bố Teamwork hoặc coding thật. Dashboard live, API, schema, auth, CSP và Registry không đổi.
