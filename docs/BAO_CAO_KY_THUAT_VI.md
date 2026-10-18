# BÁO CÁO KỸ THUẬT K-TOOL — FOUR WAVES & OMS

Ngày 18/10/2026. Kết luận: mã hardening đã kiểm thử và push nhánh phát triển; CHƯA đạt toàn bộ End-to-End. Không merge, release hoặc triển khai bản hardening lên installation đang chạy. Hai phiên Teamwork thật và protected CI/principal độc lập còn BLOCKED.

## Hiện trạng và đối soát nguồn

Máy Windows APEXSC-02, một user khiem.nguyen. Python 3.12.10, Git 2.55, .NET SDK 8.0.425, Codex CLI và agy có sẵn. Không tạo Windows user. Installation bảo tồn: C:/KTOOL/CommandCenter/MCP, Dashboard http://127.0.0.1:8876/ui. Listener thực chỉ 127.0.0.1. Registry, token và pilot worktrees không reset. Bản v0.7 identity migration trước hardening giữ nguyên giá trị credentials; CODEX/ANTI-01/ANTI-02 có token references riêng. Không đọc/đưa thông tin đăng nhập Google vào báo cáo.

Source baseline đã nhập và sửa Windows trước đây: c2dbdb5. Source hiện tại so với installation được ghi trong evidence/deployment-delta.json. Reconciliation ban đầu ghi evidence/reconciliation.json. Không tìm thấy audit v0.6.1 được cung cấp; không giả định đã đối chiếu tài liệu thiếu. Tham khảo file master v0.7 và audit nguồn thực.

Remote do chủ dự án chỉ định: https://github.com/nguyenkhiemkhiem079-boop/Command-Center-Sync.git. Nhánh feature/command-center-four-wave-oms. Remote ban đầu rỗng; không có protected integration branch để merge. Chưa tạo PR do chưa có base integration branch. Push thành công; remote SHA khớp. Không khẳng định branch protection hoặc hosted CI đã cấu hình.

## Phân loại yêu cầu sau implementation

| Yêu cầu | Phân loại | Bằng chứng / giới hạn |
|---|---|---|
| Identity riêng, adapter role, chống redirect token | IMPLEMENTED_AND_VERIFIED | subprocess MCP/RBAC và redirect tests; same-user logical isolation |
| Evidence schema, Git/profile/artifact/epoch binding | IMPLEMENTED_AND_VERIFIED | adversarial suite; local consistency không phải execution provenance |
| Trusted production verification principal / hosted CI adapter | BLOCKED | fail-closed; không callback/boolean nào bật production acceptance |
| Contract hash, revision immutable, owner approval mặc định deny | IMPLEMENTED_AND_VERIFIED | controller tests; vận hành qua API còn hạn chế |
| Multiple scope, parent-child collision, shared locks, fencing | IMPLEMENTED_AND_VERIFIED | actual Git diff/junction + registry tests |
| Durable DAG, acknowledgment, ownership, wave barrier | IMPLEMENTED_AND_VERIFIED | 21 controller tests; provider completion không accept |
| Tiếp tục parent sau child approval / replanning lịch sử đầy đủ | PARTIAL | parent dừng CHILDREN_ACCEPTED_APPROVAL_PENDING; chưa có approved continuation E2E |
| Transaction sync, combined QA, CAS, durable journal | IMPLEMENTED_AND_VERIFIED | 14 disposable Git tests; production Central writer BLOCKED |
| Failover, freeze, feedback, same-root-cause escalation | IMPLEMENTED_AND_VERIFIED | lead loss/3-cycle regression tests |
| Verified process stop, checkpoint bundle, SQLite restore | IMPLEMENTED_AND_VERIFIED | handle/creation identity proof + recovery tests; không chứng minh descendant tree đã dừng |
| Windows reboot / real provider quota exhaustion | IMPLEMENTED_UNVERIFIED | NOT_EXECUTED; chỉ coordinator crash và quota event mô phỏng |
| Antigravity headless parser/capability adapter | IMPLEMENTED_AND_VERIFIED | denied_actions không PASS dù terminal SUCCESS; raw reasoning bị loại bỏ |
| Hai Antigravity accounts/Teamwork chạy đồng thời | BLOCKED | chưa có supported start/monitor backend hoặc overlap evidence |
| OMS Run Studio / original UI / browser | IMPLEMENTED_AND_VERIFIED | Chrome localhost8877 temporary Registry; screenshot + DOM; không production deployment |
| Independent provider cost/quota telemetry | MISSING | UNKNOWN, không suy diễn từ phản hồi agent |
| Authorized API-backed coding workers | BLOCKED | chưa có endpoint/credentials/budget được duyệt; giữ nguyên kiến trúc hai team |
| Revit 2025 host acceptance / K-TOOL feature thật | BLOCKED | disposable pilot không thay real host test; không sửa Rebar logic |

## QA và mười gate

Lệnh từ source: C:/KTOOL/CommandCenter/venv/Scripts/python.exe -m unittest discover -s tests -v. Kết quả cuối 151 tests, 114.416s, OK. Log: evidence/full-regression-final.log. Đây là kiểm thử local Windows, không hosted CI hay native Teamwork acceptance.

| Gate | Kết quả | Thực thi / bằng chứng |
|---|---|---|
| 1 Source integrity / additive migration | PASS | git fsck --full, diff --check; existing-row preservation tests |
| 2 Auth / role / client secret references | PASS | test_client_identity, test_legacy_boundaries; actual three stdio adapters; không OS isolation |
| 3 Trusted production QA provenance | BLOCKED | test_trust_vault rejects false proofs; protected principal chưa có |
| 4 Worksharing exclusivity | PASS | test_scope_gate, test_orchestration; CANT_EDIT, stale epoch, junction |
| 5 Concurrent scheduler / DAG / barrier | PASS | hai assignment independent + real concurrent fixture workers; không phải Anti thật |
| 6 Transactional integration | PASS | test_transaction_sync 14; conflict/combined QA/CAS/crash; disposable refs only |
| 7 Codex feedback/rework | PASS | local harness failing oracle -> structured feedback -> same-owner correction -> real retest; không native Anti proof |
| 8 Recovery / interruption | PASS | test_recovery_manager + process drill; actual OS reboot NOT_EXECUTED |
| 9 Windows Dashboard / MCP | PASS | actual CODEX status RPC; Chrome UI temp Registry, backup; installation cổng8876 giữ nguyên |
| 10 Native Anti teams / real K-TOOL/Revit | BLOCKED | BLOCKED_TWO_ACCOUNT_TEAMWORK; Revit runtime NOT_EXECUTED |

Full process drill: 23 checks PASS, actual HTTP/coordinator subprocess crash/restart/SQLite backup; legacy boolean resume bị deny. Positive safe resume chỉ qua controller-owned process proof. Không bật lại khóa bằng checkbox.

Disposable two-worker pilot: TEST_HARNESS_NOT_ANTIGRAVITY. Base d45b7106b7e27e49ce8a2c43373c70dcaf35fd3f; A 141ec9c4091af31a08b9ab2abcc202c376656f01; B 02b4ea91f3ebf9e0b12d53d1eec8040ce84096fd; integration 0d7d319c570c20c4ff769e12eac9b98702748757. Hai worker subprocess có overlap thời gian. Một vòng sửa lỗi; cả self-tests và independent combined oracle đã chạy. Patch/bundle/result/logs nằm evidence/disposable-pilot. Đây là bằng chứng workflow, không gọi đó là Antigravity Self-QA hay Teamwork thực.

## MCP và runtime capability

| Kết nối | Thực tế | Trạng thái |
|---|---|---|
| Codex -> installed MCP | RPC status thật trả actor CODEX và tasks; freeze hai pilot giữ lock | PASS |
| ANTI-01/02 adapters -> localhost test server | real subprocess discovery/invocation + role denials | PASS local adapter |
| Antigravity -> MCP trong headless | attempted tool calls bị permission denial; có conversation IDs trong log đã parser | BLOCKED |
| Native Teamwork start/monitor | chưa được capability-tested thành công | BLOCKED |
| Hai tài khoản Google độc lập | hai MCP identities không chứng minh hai Google sessions | NOT_EXECUTED |
| Revit 2025 | không chạy plugin acceptance | NOT_EXECUTED |

Hai pilot task installed được CODEX chuyển FROZEN, lock_released=false, do không có active execution xác minh và user chọn manual launch. Không sửa output worker. Hướng dẫn tiếp tục: docs/SUPERVISED_MANUAL_LAUNCH_VI.md. Không thêm allow rules, không skip permissions, không quay vòng tài khoản.

## So sánh router, OMS và capability chính thức

9router SHA 87a74e1bda3677193c6f71a7e2100c90311f0689; n9router baaf27e6748fe71a5f59a1dd12e5be7bb8fe3d3f. Account registry, request routing, health và dashboard là kiến trúc API provider. Không phải chứng cứ nhiều IDE/Teamwork session độc lập. Không deploy OAuth interception, MITM hoặc consumer quota rotation. Xem docs/router-research.md.

OMS SHA fcc439858f73fe51dfa9a39ecb89155965488f1b; OMA 7534a8da2de669d196ff474f94a2d9ed286f1886. KEEP logical ownership và Codex QA; ADAPT pinned revisions/hierarchy/wave barriers/steering; BUILD controller/event Dashboard gốc; UNSUPPORTED remote Teamwork chưa có backend. OMS core MIT khác Console Sustainable Use License/NOTICE; không sao chép Console. Xem docs/oms-crosswalk.md. Official Antigravity headless/MCP/teamwork/auth research và observed CLI flags ở docs/runtime-feasibility.md; headless không tự chứng minh remote Teamwork.

Khuyến nghị: giữ persistent controller, hai Development owners và manual launch được giám sát. Chỉ bổ sung API worker adapter khi owner duyệt endpoint/credential scope/model/budget; router không thay native session gate. Không kết luận multi-account bất khả thi từ một lần bị deny.

## Dashboard thực tế

Chrome kiểm thử trên http://127.0.0.1:8877/ui bằng temporary Registry và credential test, không thay production DB. Login, navigation, Run Studio, UNKNOWN telemetry, SQLite Backup và recovery-disabled control đã kiểm tra. Zero captured JS errors. Run Studio screenshot: evidence/browser/run-studio.png. Recovery cuối được xác minh bằng DOM; full-page screenshot recovery timeout nên không báo ảnh đó thành công. Session UI không có real teams, empty controller cards hiển thị NOT_RECORDED. Approval/human requests phần UI read-only; chưa có owner-authenticated production approval controls. Preview dừng sau QA; ảnh giữ lại để duyệt bản source.

## Migration, rollback và giới hạn bảo vệ

Chưa triển khai hardening. Muốn triển khai cần duyệt code SHA nêu dưới, backup online SQLite bằng API backup hiện có, giữ nguyên roles/token stores, copy source vào staging riêng, chạy additive ControlStore migration trên bản sao DB trước, chạy regression và role/browser smoke, rồi mới stop/restart service đã xác minh. Không chạy provisioning với rotate, không xóa registry. Thay service thực phải là bước được owner phê duyệt.

Rollback: nếu chưa deploy, installation không cần rollback. Nếu deployment sau này thất bại, stop đúng service, giữ failed DB/evidence riêng, khôi phục source snapshot + DB backup integrity-verified cùng thời điểm; không ghi đè live DB đang mở. Không git reset/force-push hoặc ghi đè worker branches. New cc_* tables additive, không drop legacy records; không tự downgrade DB bằng cách xóa bảng. Stop proof mất sau coordinator restart thì FROZEN và human recovery, không nhập checkbox để bỏ qua.

Shared Windows user có thể sửa local code/DB/files. Hashes phát hiện corruption nhưng không chống principal độc hại tính lại hash. Không claim security boundary NTFS. Protected CI policy/suite/approval identity/repository permission phải ở principal khác. Scope workflow cung cấp fail-closed template; base policy và branch protection chưa configured; không có hosted PASS. Transaction refs chỉ refs/ktool-disposable/*, owner fixture không là approval production. Crash giữa Git CAS và journal cần owner inspection, không auto-replay.

## Git và bàn giao

1a9fc535493c0ccffcf070ba8218a9a98749af53 Wave 4: add explicit MCP identities, truthful runtime bridge and original Run Studio
f9b6ac13aea41463b3730de9938177f7980617fe Wave 3: require verified process recovery and preserve failover ownership
188c27c65880588426ee4c9d387cc3ed9e912175 Wave 2: persist hierarchical scheduling, scope locks and transactional disposable integration
43b30fd5d6e7988131db5c9d3199d09fc3c798b9 Wave 1: validate immutable QA bindings and fail closed without protected trust


Source SHA kiểm thử: 1a9fc535493c0ccffcf070ba8218a9a98749af53. Tất cả bốn commit đã push dedicated branch; không merge/release. File inventory: affected-files.txt; source diff: source-diff.patch; Git bundle kèm bàn giao. Báo cáo không chứa token store hoặc live Registry. SHA256SUMS xác minh file integrity, không chứng minh độc lập về kết quả QA.

Các bước còn cần owner: (1) duyệt triển khai hardening source cụ thể; (2) thực hiện manual sign-in/Teamwork launch trong từng phiên được hỗ trợ; (3) chọn protected CI/security principal và integration branch policy; (4) nếu native two-account chưa khả dụng, duyệt cấu hình API coding workers, giữ native gate unresolved; (5) phê duyệt feature K-TOOL nhỏ và chạy Revit2025 thật khi đủ điều kiện. Không đánh dấu mission full complete.
