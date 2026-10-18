# PILOT — Two real Antigravity Teamwork Sessions (Windows)

## 1. Prerequisites
- CODEX Windows profile, ANTI-01 and ANTI-02 Windows profiles configured with separate authorized Google sign-in, MCP adapter and role token.
- Two actual K-TOOL Git worktrees; confirm `git rev-parse HEAD` and unique paths, not on protected master.
- Coordinator health `UP`; log in Dashboard with Codex token; do not expose token.
- Confirm Antigravity Teamwork exists in each actual profile. The MCP bridge does NOT launch `/teamwork-preview` on its own.

## 2. Pick two safe tasks
- Candidate: ARCH-01 Envelope Wall Areas bounded change set vs DOC-01 Sheet/Schedule Export bounded change set.
- Codex MUST inspect actual repo first. If there is a shared file/dependency, these tasks are NOT parallel. Pick a different disjoint pair.
- Real base SHA, Functional Contracts, paths, acceptance tests, preview expectations and failure rollback criteria must be in task.

## 3. Contract + assign
- Codex creates both tasks with `requires_preview=true` (or explicit false for a task where preview genuinely does not apply), scope path per worker.
- Assign ANTI-01 / ANTI-02. Registry ensures scoped parent-child lock conflict blocked (`CANT_EDIT`).
- Each worker runs Teamwork Preview if supported, calls MCP get_task + heartbeat, then commits only to its own worktree branch.

## 4. Self QA & submit
- Before submit each worker documents actual command/output for build/test, changed_paths and preview. Worker calls `submit_self_qa` with four checks scope,diff,regression,safety.
- A failed self QA or out-of-scope file must not sync. Once ready, worker submits exact same SHA via `submit_result`.

## 5. Codex review + feedback
- Codex independently checks commit SHA, actual changed_paths, .NET8 build, regression, Revit geometry and any available preview. Use `review_task` with explicit issue IDs and proof for CHANGES_REQUESTED.
- Anti acknowledges feedback with fencing token, fixes in SAME ownership, self QA again, new SHA and resubmit. Repeat until acceptance.
- For 3 repeated failures/no progress, escalate and seek baseline clarification instead of infinite token burn; keep lock.

## 6. Sync
- Codex only after code reviewed may open/approve PR through user-authorized repository workflow; required CI and manual Revit host acceptance remain separate.
- Only after worker stopped, verified integration commit and user-authorized close may ownership be relinquished.

## 7. Pilot PASS gates
- Two actual signed-in Teamwork sessions documented, NOT just two MCP clients.
- Concurrent independent non-overlapping tasks demonstrated.
- 409 CANT_EDIT demonstrated by attempting parent/child lock; existing protected code remains untouched.
- Self-QA failed candidate blocked, successful candidate submitted.
- At least one reviewer REWORK cycle with structured feedback and a newer SHA verified end-to-end.
- QA passing candidate has build/test/preview evidence verified independently by Codex.
- No forbidden file modifications; no unintended auto merge or release.
- Revit 2025 native runtime host tests verified separately or honestly NOT_EXECUTED.

**This document is a manual pilot plan. No real Windows/Antigravity runtime acceptance has been performed in the present environment.**
