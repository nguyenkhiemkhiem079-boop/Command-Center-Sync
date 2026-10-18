# 42 PARTIAL items — dependency-ordered audit

Audit baseline: `eb87bbed0f435585c035807fda320b9a4087095e`, with post-baseline local verifier changes in the current working tree. The 42 PARTIAL classifications are from `MASTER_FEATURE_CROSSWALK.md`; this document records the remaining behavior and dependency for each. No item becomes VERIFIED solely because a class, route, page, or test exists.

| Feature | Current | Remaining behavior / dependency |
|---|---|---|
| W1.01 | PARTIAL | Six worker-facing roles and negative authorization tests exist; configure a protected Owner security principal and test it against the deployed service. Depends on separate reviewer/security principal. |
| W1.02 | PARTIAL | Inspector separates MCP, runtime, and provider identity; independent provider sessions remain UNKNOWN until supervised observation is captured. |
| W1.03 | PARTIAL | Per-client token references are implemented; same-Windows-user processes still share OS authority. Strong isolation requires a separate principal or hosted verifier. |
| W1.05 | PARTIAL | Git commit/tree/ancestry checks exist. The new hosted verifier is source-only and unexecuted; activation depends on a protected workflow source and approved assignment. |
| W1.07 | PARTIAL | Immutable hashed contracts exist locally. Owner baseline-change approval and a protected authoritative contract revision are not configured. |
| W1.09 | PARTIAL | Risk classes and fail-closed production behavior exist. Approval effects need a protected Owner principal and end-to-end permission test. |
| W1.10 | PARTIAL | Request types, expiry, one-time decision and replay rejection are tested locally. The protected Owner UI/action path is still disabled. |
| W1.11 | PARTIAL | Controller event sequence exists. A separately protected or externally anchored integrity record is missing. |
| W1.12 | PARTIAL | Dry-run, backup and rollback checks exist. Applying migration to the live Registry remains intentionally unapproved and unexecuted. |
| W2.01 | PARTIAL | Mission/Wave/Team/Assignment/Subagent entities exist. Full lifecycle conditions, replan semantics and operator acceptance remain incomplete. |
| W2.02 | PARTIAL | Scope, epoch and dependencies are represented. Required outputs, exact review policy and live task-contract retrieval need a complete pinned schema. |
| W2.03 | PARTIAL | Durable queue, ACK and bounded retries are tested. A supported Antigravity transport and real delivery acknowledgment remain unavailable. |
| W2.04 | PARTIAL | Resource-aware scheduler exists locally. Scheduling from independently verified runtime capabilities cannot be tested until real sessions are observed. |
| W2.07 | PARTIAL | Worktree create/revalidate/ownership tests exist. ANTI-01/02 worktrees have not been bound to concurrent real sessions. |
| W2.08 | PARTIAL | Scope policy and the current protected scope check work for CI-PILOT; direct push is blocked. Broader task scopes, full QA enforcement and protected-base policy evolution are not configured. |
| W2.09 | PARTIAL | Durable fan-out/checkpoints exist. Parent continuation still needs complete approval/terminal-state semantics and actual two-team execution. |
| W2.12 | PARTIAL | Local child scopes/tools can be narrowed. Native Antigravity subagent tool inheritance has not been verified. |
| W2.13 | PARTIAL | Disposable Git transaction tests pass. No authorized production integration writer, full QA check, or owner approval is connected. |
| W2.15 | PARTIAL | Ruleset `25346465` protects `integration/command-center-qa` with scope check and one independent approval. Full QA check is not required, and the policy permits only CI-PILOT. |
| W3.01 | PARTIAL | Claims are separated from local verification. Trusted hosted QA source has been added locally; no actual hosted signed result exists yet. |
| W3.02 | PARTIAL | Local feedback/rework state is tested. Real Anti feedback and correction commits have not been demonstrated. |
| W3.04 | PARTIAL | Failover states and review queue exist. Codex liveness/quota state is not measured through a supported provider interface. |
| W3.05 | PARTIAL | Bundle/patch and source hashes are available. Independent signed hosted attestation is not activated or connected to Registry acceptance. |
| W3.06 | PARTIAL | Coordinator interruption/restart is tested. Windows restart and termination of old Antigravity contexts are NOT_EXECUTED. |
| W3.08 | PARTIAL | Git transaction retries are journaled. Idempotency coverage for every external side effect and provider tool is incomplete. |
| W3.09 | PARTIAL | Emergency Stop freezes new work and integrations. Antigravity process-tree termination is not verified and must remain UNKNOWN. |
| W3.11 | PARTIAL | Combined local regression exists. A trusted hosted combined-QA run on the exact integration candidate is missing. |
| W3.12 | PARTIAL | Mission aggregator handles local checkpoints, defects and approvals. No accepted mission with two real Antigravity teams exists. |
| W3.13 | PARTIAL | Persistent supervisor records deterministic local timeouts. Runtime health, quota and native session state remain UNKNOWN. |
| W4.01 | PARTIAL | Adapter reports unsupported capability instead of fabricating it. Teamwork launch/observe/steer/resume/stop remain unsupported or unverified. |
| W4.02 | PARTIAL | State vocabulary distinguishes connection from execution. No reproducible `TEAMWORK_ACTIVE` evidence has been collected. |
| W4.03 | PARTIAL | Identity layers are distinct. Independent Google provider sessions have not been verified. |
| W4.04 | PARTIAL | Controller agent tree renders registry structure. Live child/session nodes have not been demonstrated. |
| W4.05 | PARTIAL | Revision viewer exists. Full authoring/publish controls and authorized contract changes need protected approvals. |
| W4.06 | PARTIAL | Staging Run Studio panels render controller data. A real authorized mission is not available for end-to-end run state. |
| W4.07 | PARTIAL | Parser/inspector fields exist. PID, uptime, stop cause and session evidence are not wired to verified Anti process observations. |
| W4.08 | PARTIAL | Safe event metadata is shown. Real tool lifecycle events from active Antigravity sessions are absent. |
| W4.10 | PARTIAL | Local Git diff/checkpoint view is tested. Protected hosted QA, all ownership violations and live integration conflicts are not represented together. |
| W4.12 | PARTIAL | Evidence references and feedback appear. Signed hosted artifact retrieval and signature verification are unavailable until the workflow is protected and run. |
| W4.13 | PARTIAL | Frozen ownership is visible and unsafe resume is disabled. Verified process-stop and safe-resume operations are not connected. |
| W4.14 | PARTIAL | Local task counts exist. Verified accepted-task timing, reopened defects and provider resource/cost metrics are incomplete or UNKNOWN. |
| W4.15 | PARTIAL | Authenticated API polling exists. Authenticated stream, durable cursor and replay protection are incomplete. |

## Dependency order and current work

1. **Trust root first:** protect the actual default branch, select a distinct reviewer, review the verifier workflow/profile, then execute a real hosted run. Current source includes a workflow, isolated runner and attestor, but this gate remains blocked because the default branch has no ruleset and integration scope is CI-PILOT-only.
2. **Evidence and governance:** connect signed GitHub artifact verification to `trust_vault`, map hosted run, candidate, task contract and owner epoch from an authoritative protected source, then test forged/replayed/stale results.
3. **Worksharing/dispatcher:** complete required output/review fields and verified runtime ACK; expand scopes only through a protected policy migration. Do not change the active integration ruleset to bypass its current policy.
4. **Transactions/feedback/recovery:** require the full hosted QA check on the exact candidate, test CAS and recovery in staging, then test real worker feedback when supervised sessions are available.
5. **Dashboard/runtime:** bind timeline, session inspector, evidence and recovery controls to the verified controller/API. Keep unavailable provider telemetry as UNKNOWN.
6. **Two-Teamwork pilot:** only after official supported sessions are actually observed with overlap, separate worktrees and permitted operations. Until then the native session gate remains BLOCKED; simulated workers do not count.

