# Reliability acceptance matrix — v0.6

| ID | Case | Gate | Status on 18 Oct 2026 |
|--|--|--|--|
| REL-01 | Codex quota outage | No auto PASS / merge; pending Codex decision | Documented; external quota detection NOT_VERIFIED |
| REL-02 | MCP crash/restart | Startup freeze + RECOVERY_REQUIRED | Unit-tested |
| REL-03 | Duplicate write scope | Atomic scope lock and fencing | Unit-tested; Windows ACL NOT_VERIFIED |
| REL-04 | Stale heartbeat | Freeze, NEVER auto relinquish | Unit-tested |
| REL-05 | Incorrect claimed QA | Real SHA + Git diff + build/test command evidence required | Unit-tested using temporary Git repo; real K-TOOL NOT_EXECUTED |
| REL-06 | Remote Teamwork not actually connected | State NOT_VERIFIED until live demonstration | Designed; live Windows NOT_EXECUTED |
| REL-07 | Shared Core conflict | Exclusive resource token independent of directory | Unit-tested |
| REL-08 | Different base/dependency | Dependency blocks until predecessor CLOSED | Unit-tested; real rebase conflicts NOT_VERIFIED |
| REL-09 | Contract tampering | Contract persists in DB; changes require new task | Existing behavior, not OS tamper-proof |
| REL-10 | Infinite rework | Freeze after 3 identical issue sets | Unit-tested |
| REL-11 | Windows restart/power cut | SQLite backup + reconcile locks | Unit-tested restart logic; live power-loss NOT_EXECUTED |
| REL-12 | Teamwork subagent overreach | Scope ownership, explicit worker limits | Registry tested; native Teamwork enforcement NOT_VERIFIED |
| REL-13 | Revit DLL build but load fails | Separate status; no Revit PASS inference | Defined; Revit Host NOT_EXECUTED |
| REL-14 | Stale DLL / old build loaded | Compare DLL SHA/path at host test | Procedural only |
| REL-15 | CPU/RAM starvation | Limit parallel heavy jobs to max 2 on 32 GB RAM | Policy only; Windows resource monitor NOT_CONFIGURED |
| REL-16 | Leaked MCP/Git token | Keep private creds, Windows ACL, secret scan | Loopback auth tested; NTFS/CI NOT_CONFIGURED |
| REL-17 | Emergency stop | Freeze all locks; block new work | Local HTTP + unit-tested; OS process stop NOT_IMPLEMENTED |
| REL-18 | Safe manual resume | Verify backup/process, issue new fencing token | Unit-tested; relies on operator confirmations |
| REL-19 | Independent integration QA | QA runner real SHA/diff/build/test | Local Git fixture tested; K-TOOL build NOT_EXECUTED |
| REL-20 | GitHub protected merge | Required checks, signed or reviewed release artifact | Planned; NOT_CONFIGURED |

`PASS` in unit tests is not evidence of authentic Codex / Antigravity Teamwork, Windows ACL or Revit 2025 host execution.
