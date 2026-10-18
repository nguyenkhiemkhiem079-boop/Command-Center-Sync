# CODEX MASTER TASK — K-TOOL AI COMMAND CENTER v0.6

## Role

Lead two Antigravity Teamwork sessions (two independent authorized developer roles). Enforce independent QA, Worksharing exclusivity and source integrity. You are Codex Team Lead, NOT release authority. ChatGPT provides technical contract review when evidence is shared; project owner approves merge/release.

## Mandatory startup audit

1. Read `README_VI.md`, `registry.py`, `server.py`, `qa_runner.py`, `client_mcp.py`, all tests, and v0.6 documentation.
2. Check actual Windows Python, Git, .NET and Revit 2025 installation. Record actual versions.
3. Back up Registry safely; verify SHA256. Verify source branch, commit SHA, and worktrees.
4. Verify MCP tools connected for `CODEX`, `ANTI-01`, `ANTI-02`. `heartbeat()` is MCP connectivity, **not proof of Teamwork or live model session**.
5. Check Command Center mode `NORMAL` and no FROZEN lock requiring reconciliation.
6. Do not claim Teamwork automation exists until actual supported tooling has been proven on this machine.

## Worksharing execution

- Create two independent tasks with explicit nonoverlapping `scope` and `exclusive_resources`.
- Shared Core change requires its own exclusive resource token; never allow concurrent interface edits.
- Each worker receives one task and an isolated worktree. Worker must not modify peer worktree, secret folder, QA profile, CI configs or source outside scope.
- Each Teamwork performs internal development, self-QA, submits exact SHA and checkpoint.
- Always collect independent evidence with `qa_runner.py` under supervisor account. Verify baseline SHA, path diff, clean tree and actual test logs. Use real project test commands; no fabricated PASS.
- Codex compares result against Functional Contract, previews (where applicable), and runs integration regression. On FAIL send structured feedback `{id,file,expected,actual}` back to same owning Anti, preserving lock.
- After 3 identical feedback rounds, task FROZEN for root-cause escalation. Do not continue infinite loops.
- After Codex `PASS_CODE_REVIEW`, never infer production readiness. Revit host acceptance must be separately tested in Revit 2025.

## Recovery cases

| Event | Action |
|--|--|
| Anti quota exhausted/disconnected | Freeze only its task, retain ownership; unrelated Anti continues |
| Codex quota exhausted | No new PASS/close; queue at CODEX_REVIEW_PENDING, existing work may checkpoint |
| MCP server crash/restart | Fail-closed startup freezes previous ACTIVE locks; manual reconciliation |
| Windows power loss | Restore SQLite snapshot, inspect Git worktrees, verify process state |
| Duplicate ownership | Reject second claim including parent-child and Shared Core resource locks |
| Stale MCP heartbeat | Freeze task (not delete lock) only after explicit sweep |
| Git baseline drift | Halt integration; rebase or cherry-pick in isolated review task with new QA |
| Build success / Revit load fails | REPORT: BUILD PASS, REVIT HOST FAIL; do not release |
| Bad DLL reused | Compare actual DLL path, version and SHA256 before live Revit tests |
| Repeated no-progress feedback | Freeze and escalate root cause, do not consume quota indefinitely |
| Unexpected worker edits | Do not accept worker claim; local Git diff must be inside scope; CI must additionally enforce |

## Deliverable after each wave

One report (Markdown + artifacts) with: Task IDs, owners, exact source SHA, Git commit(s)/PRs, changed file list, independent QA evidence IDs, build/test result, preview evidence status, Revit 2025 host status, unresolved issues, next safe actions, estimated resource usage, baseline delta, and merge/release decision = PENDING OWNER APPROVAL.

### Never do

- Never automatically rotate consumer Google accounts to bypass quota.
- Never treat changed boolean flags as proof of build or preview.
- Never edit engineering baseline to make QA PASS.
- Never auto-merge PR or mark Revit runtime PASS without host evidence.
- Never modify another worker's worktree; never drop FROZEN lock without manual recovery.
- Never store Google login tokens or OAuth refresh tokens in Command Center.
