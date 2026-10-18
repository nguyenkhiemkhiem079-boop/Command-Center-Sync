# Dashboard v0.6 — Recovery Center

1. Chạy `02_START_DASHBOARD.bat`, mở `http://127.0.0.1:8876/ui`, đăng nhập với CODEX token đã cấp.
2. Menu **Recovery Center**: xem `NORMAL`, `EMERGENCY_STOP`, `RECOVERY_REQUIRED` và số khóa FROZEN.
3. **Emergency Stop** đóng băng task ở Registry và không giao task mới. Nó **không giết các Antigravity processes** đang chạy.
4. **Kiểm tra heartbeat cũ**: chỉ đóng băng những task có heartbeat quá hạn, không tự nhả khóa.
5. Khi cần hồi phục, dừng/cô lập Windows process cũ, chạy `py -3 backup_registry.py`, kiểm tra snapshot rồi bấm **Mở lại Control Plane**. Chỉ sau đó khôi phục từng FROZEN task cùng owner (fencing mới).
6. Task Board có thêm Shared Resources & Dependencies. Tab Worksharing Locks hiển thị Scope và resource locks.
7. Task chỉ có thể Codex PASS sau khi chạy `qa_runner.py` thành công với commit đúng vòng; nguồn dữ liệu Dashboard không thay cho Revit live QA.

**Ghi chú:** Bảo vệ NTFS/GitHub required checks và tự điều khiển Antigravity Teamwork chưa được xây xong. Đây là giao diện v0.6 cho Registry tại localhost.
