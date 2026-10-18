# Failover & Recovery

NORMAL/LEAD_UNAVAILABLE/RECOVERY_REQUIRED/EMERGENCY_STOP có. Lead loss cho phép previously authorized checkpoint, chuyển review chờ Codex, không cho worker tự duyệt. Stale epochs/checkpoints bị deny. Frozen locks không tự nhả.

OwnedProcessRegistry dùng process handle/creation identity và opaque proof; không arbitrary PID/checkbox. Khi controller restart mất ownership handle -> fail-closed, cần human recovery; descendant tree UNKNOWN. SQLite actual backup/restore integrity tested. 23-check standalone coordinator process drill PASS ở baseline. Windows reboot và actual Google quota exhaustion NOT_EXECUTED. Automatic lead detector/overdue watchdog và complete result aggregator còn PARTIAL.
