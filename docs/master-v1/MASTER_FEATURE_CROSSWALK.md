# MASTER FEATURE CROSSWALK — Full Fix delta

Source base `eb87bbed0f435585c035807fda320b9a4087095e`; current candidate is this base plus the uncommitted trusted-hosted-QA source in the working tree. Deployed source remains `c377d103da179e3ef1f5d48a11d8d9e6d1ee5a3d`.
210 regression tests executed on Windows, 190.193s, OK; local shared principal, not production-trusted QA. The new hosted verifier is source-only and has not run in GitHub Actions.
Counts: {"PARTIAL": 42, "BLOCKED": 5, "IMPLEMENTED_AND_VERIFIED": 9}. IMPLEMENTED_AND_VERIFIED applies only to the explicitly stated local contract. All rows remain undeployed in the new candidate. No NOT_EXECUTED is aggregated into PASS.
Native two independent Antigravity Teamwork sessions: BLOCKED pending permitted supervised runtime evidence; technical impossibility is not established.

| ID | Status | Evidence and remaining limit |
|---|---|---|
| W1.01 | PARTIAL | governance.py; test_governance: six backend roles, opaque authenticated principal, wrong-owner/spoof/replay denial; protected OWNER principal chưa cấu hình |
| W1.02 | PARTIAL | cockpit.py + test_cockpit: inspector ba lớp; provider/runtime UNKNOWN; không truy xuất OAuth |
| W1.03 | PARTIAL | test_private_acl + test_client_identity: Windows broad ACE removal/junction denial tested; live tokens preserved; cùng user LOGICAL_ONLY |
| W1.04 | BLOCKED | trust_vault.py; Local bindings có; protected verifier/principal chưa cấu hình |
| W1.05 | PARTIAL | test_trust_vault: actual Git/tree/ancestry/profile binding; hosted CI-PILOT scope runs thật có; chưa protected full QA provenance |
| W1.06 | BLOCKED | ci_scope_gate.py; Pin digests có; protection ngoài principal worker còn thiếu |
| W1.07 | PARTIAL | governance.py: immutable hashed knowledge versions/provenance; engineering baseline approval vẫn blocked external principal |
| W1.08 | IMPLEMENTED_AND_VERIFIED | tests/test_orchestration.py; Pin immutable content hashes trong local controller |
| W1.09 | PARTIAL | test_governance: LOW/MEDIUM/HIGH/CRITICAL và scope escalation; production critical execution luôn fail-closed |
| W1.10 | PARTIAL | test_governance + test_human_requests: expiry/actor/one-time fixture/replay/tamper rejection; protected owner UI chưa enabled |
| W1.11 | PARTIAL | orchestration.py cc_events; Local events không được gọi tamper-proof; thiếu protected external anchor |
| W1.12 | PARTIAL | upgrade dry-run thật PASS; backup CHECK corruption rejected; additive migration/restore tested; candidate live upgrade chưa được duyệt |
| W2.01 | PARTIAL | orchestration.py; Mission/Wave/Team/Assignment/Subagent có; all-level conditions chưa đủ |
| W2.02 | PARTIAL | orchestration.py; Scope/epoch/dependencies pinned; required output/review policy cần schema rõ |
| W2.03 | PARTIAL | test_dispatch_delivery: atomic outbox, payload hash, ACK, bounded retry/timeouts/restart; actual Anti transport pending supervised session |
| W2.04 | PARTIAL | durable dispatcher resources/capabilities/health checks; unverified production runtime cannot dispatch |
| W2.05 | IMPLEMENTED_AND_VERIFIED | test_orchestration + browser Fleet DAG: local cycle/dependency/resources/graph verified; no native runtime claim |
| W2.06 | IMPLEMENTED_AND_VERIFIED | tests/test_scope_gate.py; Parent-child/resource/fencing/frozen/relinquish local sandbox verified |
| W2.07 | PARTIAL | worktree_manager.py + 3 actual Git tests: exact registered root, branch/base/owner uniqueness/revalidation; actual worker resume pending |
| W2.08 | PARTIAL | Actual active ruleset 25346465 enforces `Trusted base scope policy`; PR #1 CI-PILOT passed and PR #2 OUT_OF_SCOPE/PROTECTED_PATH was rejected, confirmed by owner. Direct push/non-fast-forward blocked. Broader task scopes and full trusted QA enforcement are not configured. |
| W2.09 | PARTIAL | orchestration.py; Atomic queue/checkpoints có; approved parent continuation chưa đủ |
| W2.10 | IMPLEMENTED_AND_VERIFIED | tests/test_orchestration.py; Early child/provider completion không làm wave accepted |
| W2.11 | IMPLEMENTED_AND_VERIFIED | tests/test_orchestration.py; Target/context/ACK/owner restrictions; advisory only |
| W2.12 | PARTIAL | orchestration.py add_subagent; Scope/tools narrowed; real native subagent enforcement chưa verified |
| W2.13 | PARTIAL | tests/test_transaction_sync.py; 14 local Git tests; production integration backend blocked |
| W2.14 | BLOCKED | transaction_sync.py; Disposable CAS verified, no production writer/approval/CI |
| W2.15 | PARTIAL | Active ruleset 25346465 protects `integration/command-center-qa`: PR required, one independent approval, stale approval dismissed, last-push approval, strict `Trusted base scope policy`, no bypass, deletion/non-fast-forward blocked. `Trusted Independent QA` is not yet required; scope policy remains CI-PILOT-only. |
| W3.01 | PARTIAL | trust_vault + harness; Claim separation có; real trusted independent CI thiếu |
| W3.02 | PARTIAL | orchestration.py + harness; Defect iteration and same-owner correction local; native Anti chưa chạy |
| W3.03 | IMPLEMENTED_AND_VERIFIED | test_dispatch_delivery: normalized repeated root cause across defect IDs freezes after three non-improving rounds; local policy scope |
| W3.04 | PARTIAL | orchestration.py; Mode/checkpoint/review queue có; automatic lead liveness detection thiếu |
| W3.05 | PARTIAL | mission_recovery.py: actual bundle/source/log hashes, epoch/contract/workflow binding; local consistency verified, not protected attestation |
| W3.06 | PARTIAL | process_recovery_drill.py; Actual coordinator crash; Windows reboot NOT_EXECUTED |
| W3.07 | IMPLEMENTED_AND_VERIFIED | test_orchestration.py; Stale epochs/checkpoints denied after safe resume |
| W3.08 | PARTIAL | transaction_sync.py; CAS journal/recovery no replay; external tool sideeffects chưa bao phủ |
| W3.09 | PARTIAL | registry + orchestration; Freeze/newwork block verified; only owned process stop, descendant tree UNKNOWN |
| W3.10 | IMPLEMENTED_AND_VERIFIED | test_recovery_manager.py; Actual isolated restore + integrity + corruption rejection |
| W3.11 | PARTIAL | transaction_sync.py + harness; Actual combined local suite; production protected CI chưa có |
| W3.12 | PARTIAL | mission_recovery mission_result aggregates checkpoints/defects/requests/blockers; real complete two-Teamwork mission pending |
| W3.13 | PARTIAL | SupervisedHTTPServer periodic deterministic supervisor_tick; test_supervisor_service: timeout freeze, locks preserved, bounded errors; native liveness UNKNOWN |
| W4.01 | PARTIAL | anti_runtime.py; Headless parser/modes có; supported native start/monitor chưa verified |
| W4.02 | PARTIAL | anti_runtime.py; Tool denial checked; full live session lifecycle chưa kết nối controller |
| W4.03 | PARTIAL | browser Fleet identity inspector shows MCP/runtime/provider separately UNKNOWN; no independent Google sessions verified |
| W4.04 | PARTIAL | original Fleet hierarchy SVG/controller actual records browser-tested; runtime/subagent live evidence pending |
| W4.05 | PARTIAL | web/dashboard.js; Revision viewer có; editor/designer và gates chưa có |
| W4.06 | PARTIAL | docs/qa/run-studio.png; Browser read-only panels verified; real mission runtime chưa có |
| W4.07 | PARTIAL | inspector metadata+parser exists; actual Anti runtime observations not wired/verified |
| W4.08 | PARTIAL | controller safe metadata timeline with sequence/time/source; no private bodies/reasoning; native tool lifecycle unavailable |
| W4.09 | BLOCKED | Approval Inbox read-only by design; no protected owner security principal, backend refuses production approval |
| W4.10 | PARTIAL | cockpit immutable checkpoint Git diff actual-browser tested, redaction+wrong SHA/path negative tests; hosted full QA/conflict UI incomplete |
| W4.11 | IMPLEMENTED_AND_VERIFIED | original controller DAG SVG with ownership/dependency edges; browser staged fixture verified, not native Teamwork |
| W4.12 | PARTIAL | web/dashboard.js; References/feedback có; protected artifact retrieval chưa có |
| W4.13 | PARTIAL | actual controller FROZEN ownership/mode inspector; unsafe resume disabled; end-to-end operator process recovery UI incomplete |
| W4.14 | PARTIAL | ControlStore.snapshot; Counts có; durations/reopen/resource/verified cost còn UNKNOWN |
| W4.15 | PARTIAL | server.py + web; Auth API/polling có; authenticated stream/replay cursor thiếu |
| W4.16 | BLOCKED | runtime-feasibility.md; Windows browser/MCP local có; native two-session overlap chưa verified |
