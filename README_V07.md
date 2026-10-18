# K-TOOL Command Center v0.7 single-Windows-user pilot

Giữ source v0.6 và Registry hiện có; migration không bootstrap lại, không đổi token, không tạo Windows users.
Đọc [runbook local](docs/SINGLE_WINDOWS_V07.md) và [client identities](docs/CLIENT_IDENTITIES_V07.md).

Ba MCP identity riêng, authenticated Dashboard, Worksharing Registry, trusted Git scope gate, QA feedback và recovery đều có test.
Phân biệt local/test-harness PASS với Antigravity/Teamwork/CI/Revit chưa được kiểm chứng.
Không auto merge/release. `SHA256_MANIFEST.json` gốc chỉ dùng truy nguồn baseline; dùng manifest bàn giao mới cho source đã sửa.
