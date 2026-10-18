# OMS / OMA crosswalk cho K-TOOL

Ngày kiểm tra: 2026-10-18. Nghiên cứu chỉ đọc; không cài upstream, chạy installer, reset database hoặc sao chép Console.

## Nguồn và phiên bản cố định

- OMS HEAD: `fcc439858f73fe51dfa9a39ecb89155965488f1b`, xác minh bằng `git ls-remote https://github.com/ringlochid/oh-my-subagents.git HEAD`.
- OMA HEAD: `7534a8da2de669d196ff474f94a2d9ed286f1886`, xác minh bằng `git ls-remote https://github.com/first-fluke/oh-my-agent.git HEAD`.
- agent-reach dev route yêu cầu GitHub CLI. `gh --version` thất bại: command không có trong PATH; không thấy ở Program Files/GitHub CLI hoặc WinGet/Links. Fallback đọc GitHub/raw chính chủ qua web; không đăng nhập hoặc thay credential.

OMS mô tả controller giữ ownership, wave, checkpoint và revision bền vững, với lead chấp nhận kết quả. [README](https://github.com/ringlochid/oh-my-subagents/blob/fcc439858f73fe51dfa9a39ecb89155965488f1b/README.md).

OMA cung cấp vai trò, workflow và file kết quả; checks do dự án cung cấp quyết định nghiệm thu. README ghi installer Windows ẩn Antigravity; không dùng OMA như bằng chứng Antigravity Windows được hỗ trợ. [README](https://github.com/first-fluke/oh-my-agent/blob/7534a8da2de669d196ff474f94a2d9ed286f1886/README.md).

## Giấy phép: core và console tách biệt

| Thành phần | Kết quả từ nguồn | Quyết định K-TOOL |
|---|---|---|
| OMS core | [MIT](https://github.com/ringlochid/oh-my-subagents/blob/fcc439858f73fe51dfa9a39ecb89155965488f1b/LICENSE) | Chỉ tham khảo mô hình; chưa vendor code |
| OMS console | [Sustainable Use License](https://github.com/ringlochid/oh-my-subagents/blob/fcc439858f73fe51dfa9a39ecb89155965488f1b/console/LICENSE) khác core; hạn chế mục đích dùng/phân phối | Không sao chép source, design tokens, stylesheets, markup hoặc canvas |
| OMS console NOTICE | [NOTICE](https://github.com/ringlochid/oh-my-subagents/blob/fcc439858f73fe51dfa9a39ecb89155965488f1b/console/NOTICE) xác nhận vật liệu n8n-derived và vấn đề brand placeholder | Giao diện K-TOOL nguyên bản, không dùng brand upstream |
| OMA root | [MIT](https://github.com/first-fluke/oh-my-agent/blob/7534a8da2de669d196ff474f94a2d9ed286f1886/LICENSE) | Chỉ tham khảo vai trò/workflow; chưa audit giấy phép mọi dependency, không vendor UI |

Đây là kiểm tra văn bản giấy phép để quyết định phạm vi implementation; không xác nhận giấy phép mọi dependency upstream.

## KEEP / ADAPT / BUILD / UNSUPPORTED

Các hàng dưới là đánh giá K-TOOL từ source local; không khẳng định upstream đã cài hay runtime được nghiệm thu.

| Khả năng | Quyết định | Đối chiếu local / implementation |
|---|---|---|
| Registry SQLite + role CODEX/ANTI-01/ANTI-02 | KEEP | `registry.py`, `server.py`; giữ database/token đang tồn tại |
| Worksharing scope lock, fencing, frozen ownership | KEEP | Registry giữ làm nguồn quyền task; không thay bằng upstream |
| Self-QA rồi independent Codex QA | KEEP | `qa_runner.py`, QA metadata và feedback endpoints; không agent self-approval |
| Team hierarchy, waves, immutable revision concept | ADAPT | `orchestration.py` ControlStore; source controller là nguồn dữ liệu duy nhất |
| Checkpoint/result references | ADAPT | File evidence vẫn là file thường; web chỉ trình bày reference, không đọc tùy ý |
| Run Studio mission/hierarchy/revision/wave panels | BUILD | HTML/CSS/JS nguyên bản mở rộng Dashboard hiện có |
| Steering inbox / human requests | BUILD | Read-only hiển thị controller records; chưa có nút delivery/approval |
| Evidence vault | BUILD | Allowlist metadata và reference; không expose reasoning/credential fields |
| Performance | BUILD | UNKNOWN khi không có metric thực; không ước tính quota hoặc chi phí |
| Automatic remote Teamwork control | UNSUPPORTED | Không có adapter chính thức đã được chứng minh; MCP không chứng minh Teamwork |
| Hai account Antigravity chạy đồng thời | UNSUPPORTED_UNTIL_VERIFIED | Cần session, auth và execution evidence riêng |
| Strong isolation với một Windows user | UNSUPPORTED | LOGICAL_ONLY; NTFS cùng user không bảo vệ chống process cùng principal |
| Auto-merge / release | UNSUPPORTED_WITHOUT_OWNER_APPROVAL | Không thêm cơ chế publish tự động |

## Kiểm thử và giới hạn

`python -m unittest tests.test_run_studio tests.test_dashboard tests.test_dashboard_v07 -q`: 14 tests PASS, gồm 4 test Run Studio mới với fixture `TEST_FIXTURE`. `node --check web/dashboard.js`: PASS. Các test này là sandbox/unit HTTP, không phải Teamwork hoặc Revit acceptance.

`GET /ui/api/run-studio` cần session CODEX; gọi lazy `ControlStore(store.dbfile).snapshot('CODEX')`. Endpoint trả 503 nếu module chưa có, lỗi nội bộ trả thông báo chung. UI không có mission mẫu, hiển thị source/last_verified_at hoặc UNKNOWN, không đọc referenced files. Chưa thực hiện browser QA trong phạm vi subtask này; cần root kiểm tra sau tích hợp ControlStore/schema.


## Bổ sung HTTP/MCP control interface

Adapter MCP thêm 14 operation, role lấy duy nhất từ bearer credential đã xác minh; không nhận role do request tự khai. Nhóm đọc: `control_snapshot`, `get_assignment`, `read_approved_contract`. Worker: `acknowledge_assignment`, `assignment_checkpoint`, `assignment_submit_claim`, `steering_ack`. Điều phối: `propose_contract`, `publish_revision`, `create_mission`, `queue_wave`, `dispatch`, `steer`, `human_request`. Không expose approve, accept, integration, recovery boolean hoặc release. Nhóm mutation kiểm tra legacy control mode trước khi gọi ControlStore; Emergency Stop HTTP cập nhật cả hai store. Startup sau backup gọi reconciliation của cả hai schema.

Run Studio đã alias schema thật: `status`, `mission`, `team`, `parent`, revision `hash`, checkpoint `body` và performance counters. Wave `created` được ghi rõ là ngày tạo, không phải bắt đầu execution.

Kiểm thử bổ sung: 6 Run Studio tests PASS. Full suite với PATH Python312 chạy 102 tests, 1 import ERROR ở `test_client_identity` vì interpreter này chưa có package `mcp`; không ghi toàn bộ suite PASS. Cần chạy MCP integration tests bằng venv đã cài dependencies. Không tự cài mới hoặc deploy trong subtask này.
