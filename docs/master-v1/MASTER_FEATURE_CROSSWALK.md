# MASTER FEATURE CROSSWALK v1.0

Đối soát source e80e26f và delta Human Requests hiện tại. VERIFIED chỉ cho phạm vi local được ghi rõ, không suy ra full runtime/production acceptance. Source hardening chưa deploy. Không có bằng chứng kỹ thuật đủ để kết luận multi-account là UNSUPPORTED; trạng thái native hai accounts là BLOCKED.

| ID | Trạng thái | Chức năng | Nguồn bằng chứng | Giới hạn / việc tiếp theo |
|---|---|---|---|---|
| W1.01 | PARTIAL | RBAC | server.py + registry.py | CODEX/ANTI role checks; six principal roles chưa đầy đủ |
| W1.02 | PARTIAL | Identity/account inspector | anti_runtime.py | Chưa có inspector ba lớp, không đọc OAuth |
| W1.03 | PARTIAL | Credential references | tests/test_client_identity.py | Separate references/redirect tests có; provisioner chưa kiểm tra explicit broad ACLs; cùng user LOGICAL_ONLY |
| W1.04 | BLOCKED | Trusted vault | trust_vault.py | Local bindings có; protected verifier/principal chưa cấu hình |
| W1.05 | PARTIAL | Git/QA verification | tests/test_trust_vault.py | Real commits/ancestry/tree checked; hosted candidate CI chưa có |
| W1.06 | BLOCKED | Protected QA profiles | ci_scope_gate.py | Pin digests có; protection ngoài principal worker còn thiếu |
| W1.07 | PARTIAL | Knowledge registry | orchestration.py | Hashed contracts/revisions; taxonomy ADR/API/rules provenance cần hoàn thiện |
| W1.08 | VERIFIED | Workflow revision | tests/test_orchestration.py | Pin immutable content hashes trong local controller |
| W1.09 | MISSING | Risk approval engine | source audit | Chưa có risk policy LOW/MEDIUM/HIGH/CRITICAL |
| W1.10 | PARTIAL | Human requests | tests/test_human_requests.py | Sáu loại/deadline/decision timestamp đã thêm; external owner auth/UI còn thiếu |
| W1.11 | PARTIAL | Tamper-evident audit | orchestration.py cc_events | Local events không được gọi tamper-proof; thiếu protected external anchor |
| W1.12 | PARTIAL | Installer/migrations | scripts + ControlStore | Additive migration + backup có; full upgrade/rollback lifecycle còn thiếu |
| W2.01 | PARTIAL | Hierarchy | orchestration.py | Mission/Wave/Team/Assignment/Subagent có; all-level conditions chưa đủ |
| W2.02 | PARTIAL | Assignment contract | orchestration.py | Scope/epoch/dependencies pinned; required output/review policy cần schema rõ |
| W2.03 | PARTIAL | Durable dispatcher | orchestration.py | Persist + ACK/idempotency có; transport delivery/outbox timeout retry chưa đủ |
| W2.04 | PARTIAL | Scheduler | orchestration.py dispatch | Capabilities/resources/maxworkers có; runtime health attestation thiếu |
| W2.05 | PARTIAL | Fleet DAG | tests/test_orchestration.py | Cycle/dependency/shared locks checked; fleet UI graph chưa có |
| W2.06 | VERIFIED | Exclusive locks | tests/test_scope_gate.py | Parent-child/resource/fencing/frozen/relinquish local sandbox verified |
| W2.07 | PARTIAL | Worktree manager | tests/e2e_local_harness.py | Real worktrees pilot có; controller-owned generic lifecycle còn thiếu |
| W2.08 | BLOCKED | Protected diff boundary | ci_scope_gate.py | Actual diffs/junction tests có; protected required CI chưa cấu hình |
| W2.09 | PARTIAL | Durable fanout/fanin | orchestration.py | Atomic queue/checkpoints có; approved parent continuation chưa đủ |
| W2.10 | VERIFIED | Wave barrier | tests/test_orchestration.py | Early child/provider completion không làm wave accepted |
| W2.11 | VERIFIED | Steering inbox | tests/test_orchestration.py | Target/context/ACK/owner restrictions; advisory only |
| W2.12 | PARTIAL | Subagent inheritance | orchestration.py add_subagent | Scope/tools narrowed; real native subagent enforcement chưa verified |
| W2.13 | PARTIAL | Transaction sync | tests/test_transaction_sync.py | 14 local Git tests; production integration backend blocked |
| W2.14 | BLOCKED | Central safety | transaction_sync.py | Disposable CAS verified, no production writer/approval/CI |
| W2.15 | BLOCKED | PR/protection | Git remote audit | Dev push có; base integration/required checks/owner policy chưa cấu hình |
| W3.01 | PARTIAL | Three-layer QA | trust_vault + harness | Claim separation có; real trusted independent CI thiếu |
| W3.02 | PARTIAL | Feedback loop | orchestration.py + harness | Defect iteration and same-owner correction local; native Anti chưa chạy |
| W3.03 | PARTIAL | Root-cause escalation | test_orchestration.py | Three unchanged fingerprints freeze task; chưa normalized root-cause grouping |
| W3.04 | PARTIAL | Codex failover | orchestration.py | Mode/checkpoint/review queue có; automatic lead liveness detection thiếu |
| W3.05 | PARTIAL | Source checkpoints | recovery_manager.py | Git/bundle/hash recovery local có; every checkpoint artifact linkage cần mở rộng |
| W3.06 | PARTIAL | Crash/restart | process_recovery_drill.py | Actual coordinator crash; Windows reboot NOT_EXECUTED |
| W3.07 | VERIFIED | Fencing | test_orchestration.py | Stale epochs/checkpoints denied after safe resume |
| W3.08 | PARTIAL | Idempotent retry | transaction_sync.py | CAS journal/recovery no replay; external tool sideeffects chưa bao phủ |
| W3.09 | PARTIAL | Emergency Stop | registry + orchestration | Freeze/newwork block verified; only owned process stop, descendant tree UNKNOWN |
| W3.10 | VERIFIED | SQLite backup/restore | test_recovery_manager.py | Actual isolated restore + integrity + corruption rejection |
| W3.11 | PARTIAL | Combined regression | transaction_sync.py + harness | Actual combined local suite; production protected CI chưa có |
| W3.12 | PARTIAL | Result aggregator | snapshot + wave_report | Local summaries có; full mission final acceptance aggregator thiếu |
| W3.13 | PARTIAL | Mission supervisor | orchestration.py | Dependency/state policy có; durable overdue watchdog thiếu |
| W4.01 | PARTIAL | Runtime adapter | anti_runtime.py | Headless parser/modes có; supported native start/monitor chưa verified |
| W4.02 | PARTIAL | Verified bridge | anti_runtime.py | Tool denial checked; full live session lifecycle chưa kết nối controller |
| W4.03 | MISSING | Account isolation inspector | source audit | Không suy diễn identities thành Google sessions |
| W4.04 | PARTIAL | Agent tree | web/dashboard.js | Controller-backed table/tree có; live runtime permissions chưa đủ |
| W4.05 | PARTIAL | Workflow Studio | web/dashboard.js | Revision viewer có; editor/designer và gates chưa có |
| W4.06 | PARTIAL | Run Studio | docs/qa/run-studio.png | Browser read-only panels verified; real mission runtime chưa có |
| W4.07 | PARTIAL | Session inspector | anti_runtime.py | Process metadata có; authenticated inspector chưa wired |
| W4.08 | PARTIAL | Tool timeline | cc_events + runtime parser | Safe summaries có; durable normalized live stream thiếu |
| W4.09 | MISSING | Approval inbox | Run Studio read-only | Không có external owner auth + actual approve/reject UI |
| W4.10 | PARTIAL | Git Diff inspector | web/dashboard.js | QA/file metadata có; full safe diff/conflicts/CI viewer thiếu |
| W4.11 | MISSING | Fleet DAG visualizer | source audit | Có DAG backend, chưa có graph visualization |
| W4.12 | PARTIAL | Evidence review center | web/dashboard.js | References/feedback có; protected artifact retrieval chưa có |
| W4.13 | PARTIAL | Recovery Center | browser recovery DOM | Freeze/backup/disabled unsafe resume có; verified recovery operator UI thiếu |
| W4.14 | PARTIAL | Performance | ControlStore.snapshot | Counts có; durations/reopen/resource/verified cost còn UNKNOWN |
| W4.15 | PARTIAL | Event streaming/API | server.py + web | Auth API/polling có; authenticated stream/replay cursor thiếu |
| W4.16 | BLOCKED | Real Windows two-agent pilot | runtime-feasibility.md | Windows browser/MCP local có; native two-session overlap chưa verified |
