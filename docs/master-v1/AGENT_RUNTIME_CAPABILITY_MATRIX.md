# Agent runtime capability matrix

| Capability | Status | Evidence |
|---|---|---|
| Installed CODEX MCP status/freeze | VERIFIED | ../qa report + external evidence/mcp-final-status.json |
| Three adapter stdio discovery/RBAC | VERIFIED local | test_client_identity |
| AGY_HEADLESS NDJSON parser/conversation | VERIFIED adapter only | test_anti_runtime; CLI help observed |
| Real headless MCP tool permission | BLOCKED | real trials denied_actions; user giữ deny |
| Native Teamwork external start/observe/steer | BLOCKED | no verified backend; không kết luận bất khả thi |
| SUPERVISED_IDE/manual launch | Pending operator | existing operator guide; không tự launch xác minh |
| Two independent authenticated accounts | BLOCKED | MCP credentials không chứng minh Google account isolation |
| Provider quota/cost | UNKNOWN | chưa có verified usage endpoint |
| API coding workers | BLOCKED | chưa có authorized endpoint/key/budget |
| Revit2025 host | NOT_EXECUTED | không có runtime acceptance |

Không đọc OAuth stores hoặc raw reasoning. Xem ../runtime-feasibility.md cho official references và observed limitations.
