# CODEX_FAILOVER_AND_RECOVERY_REPORT — Full Fix delta

Source `552197b91b09c955d0fb48f96e329eba20b98f64`; evidence date18/10/2026. Supersedes earlier progress claims; full acceptance remains false.

Modes NORMAL / LEAD_UNAVAILABLE / RECOVERY_REQUIRED / EMERGENCY_STOP preserve mission/assignments/ownership. Previously authorized checkpoints and Self-QA claims may continue during lead loss; review queues wait for CODEX. Worker never becomes final reviewer. Supervisor tick makes no provider calls and grants no fallback privileges.

Actual local process recovery drill: 23 checks PASS; actual coordinator crash/restart, Git/SQLite isolated restore and integrity, stale fencing, frozen locks and safe context checks tested. New source bundle/log/contract/epoch checkpoint envelopes reject tamper. New backup integrity failure stops certification. Emergency controls block new work/integration; Antigravity termination is not claimed. Windows reboot and real provider quota exhaustion NOT_EXECUTED (quota interruption policy tested as fixture). Production frozen locks retained.
