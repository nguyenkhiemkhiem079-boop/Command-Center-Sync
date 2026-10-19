# Giai đoạn 3 — Polish, GPU và QA

**Kết quả:** Chất lượng source/test PASS. Mục tiêu hiệu năng 50 FPS: **FAIL trên phép đo soak nền này**; con số bị giới hạn bởi Chrome background throttling và không đại diện benchmark GPU tương tác ở foreground. Dashboard live chưa được cập nhật.

## Thay đổi

- Chuyển các phần chibi sang `MeshToonMaterial` với gradient 3 bậc local, outline shell mỏng và bóng tiếp xúc tròn; tái sử dụng material/geometry qua asset pool.
- Thêm phím chọn agent có thể dùng bàn phím, giữ camera preset, selection/inspector hiện hữu. World tự chuyển 2D-first ở màn hình hẹp.
- Render loop dừng khi view ẩn/tab ẩn, tôn trọng reduced-motion, resource disposal khử trùng geometry/material/texture và xử lý WebGL context loss/restore.
- Ghi bộ đếm `renderer.render()` để đo submission thực, tách khỏi nhịp `requestAnimationFrame`.

## Bằng chứng

- `npm test`: **17/17 PASS**.
- `npm run build`: **PASS**, Three.js `0.186.1` được đóng gói local; bundle 963.48 KB (gzip 221.83 KB).
- `python -m unittest tests.test_agent_world tests.test_dashboard_v07 tests.test_dashboard -q`: **29/29 PASS**.
- Chrome 155 staging dùng WebGL2 và renderer thật `ANGLE (NVIDIA GeForce RTX 3050, Direct3D11)`. Không có runtime exception hay request ngoài localhost. Hai lỗi console là 401 của API trước login trong test harness và 404 của route âm tính; không phải exception JS/CSP.
- Soak hiển thị 60.006 giây: 438 lượt `renderer.render()` (7.3/s), RAF 16.5/s; JS heap lấy mẫu 60 lần, đầu 10.03 MB, cuối 7.36 MB, peak 13.48 MB. Cửa sổ Chrome chạy nền/bị throttling nên phép đo hiệu năng bị nhiễu; không kết luận RTX 3050 không đạt 50 FPS ở foreground. Browser không cung cấp VRAM GPU qua harness này.
- Harness thử WebGL context loss/restore trong môi trường staging: `lost=true`, `restored=true`, fallback hiện ra và canvas trở lại. Ảnh camera GPU và report nằm ở `AGENT_WORLD_SCREENSHOTS/agent-world-chrome-hardware-gpu-camera-*.png` và `browser-hardware-gpu-e2e.json`.

## Giới hạn và an toàn

GPU phát hiện được là RTX 3050, không phải RTX 3060 Ti trong mục tiêu tham chiếu. Cần phép đo foreground có kiểm soát để xác nhận FPS 50. Không chạy kiểm tra WebGL restore trên Dashboard production. Không có Teamwork/session thật trong disposable Registry; avatar ở trạng thái UNKNOWN và không biểu diễn hoạt động. Không đổi API, schema, auth, CSP, trang Fleet/Timeline, Registry production hay task FROZEN. Chưa triển khai tới `127.0.0.1:8876`.
