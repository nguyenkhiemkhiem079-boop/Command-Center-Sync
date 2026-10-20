# Giai đoạn 0 — Khảo sát Agent World Chibi

**Kết quả:** Hoàn tất; source đang dùng nhánh `feature/agent-world-3d`. Đây là kiểm tra source/staging, không phải nghiệm thu Dashboard live.

## Quan sát source

- Scene hiện hữu và điểm mount nằm trong `frontend/agent-world/src/main.js`; Three.js được pin tại `frontend/agent-world/package.json` phiên bản `0.186.1`, đóng gói thành `web/agent-world/agent-world.js` qua Vite. Runtime không tải CDN hay asset bên ngoài.
- Dashboard Python đã whitelist route cho asset bundle và CSS Agent World. Giai đoạn này không cần route server mới. CSP hiện hữu giữ nguyên; không thêm inline script/style hay nới policy.
- Avatar ban đầu dùng primitive Three.js (cylinder/head/visor/eyes/ring). State được chuẩn hóa từ controller metadata; `UNKNOWN` là mặc định khi thiếu bằng chứng runtime.
- Dashboard navigation/view state hiện có World, Fleet 2D, Event Timeline, camera presets và Agent overview. Scope được giữ tại module 3D.

## Phạm vi thay đổi và rủi ro

Các file triển khai: `frontend/agent-world/src/chibi.js`, `src/chibi.test.js`, `src/main.js`, `web/agent-world.css`, generated `web/agent-world/agent-world.js`, cùng browser harness và ảnh/báo cáo staging. Không đổi `server.py`, API, SQLite schema, auth/session/CSRF, registry hay trang 2D.

Rủi ro chính là tăng số draw calls/đa giác do viền toon và biểu tượng; đo GPU ở Giai đoạn 3. Browser staging chạy Registry tạm riêng để không tác động dữ liệu production. Không có route nào cần thêm.

**Lưu ý:** Thiết kế chibi được triển khai theo các giai đoạn đã được chủ dự án yêu cầu thực hiện đầy đủ; báo cáo này ghi lại audit, không tạo cổng dừng/chờ.
