# AGENT_RUNTIME_CAPABILITY_MATRIX — Full Fix delta

Source `552197b91b09c955d0fb48f96e329eba20b98f64`; evidence date18/10/2026. Supersedes earlier progress claims; full acceptance remains false.

| Capability | Actual evidence | Status |
|---|---|---|
| Installed live CODEX/ANTI-01/ANTI-02 stdio adapters | Existing installed probe: 36 tools each | PASS_LOCAL_MCP_ONLY |
| Candidate staging CODEX adapter | tests/probe_mcp_readonly.py, 45 tools, status/identity/outbox/mission_result actual calls | PASS_LOCAL_MCP_ONLY |
| AGY_HEADLESS MCP task actions | Captured two actual CLI logs contain denied_actions despite terminal SUCCESS; parser rejects | BLOCKED_PERMISSION_DENIED |
| TEAMWORK_NATIVE remote launch/observe | No permitted verified end-to-end interface tested | NOT_EXECUTED |
| SUPERVISED_IDE | Owner selected manual launch; operator must start permitted sessions | PENDING_OPERATOR |
| Two provider accounts concurrently authenticated | Separate MCP credentials are insufficient | BLOCKED_TWO_ACCOUNT_TEAMWORK |
| agy remote-control status | Exit0, hashed raw observation only; no daemon launched | UNKNOWN_TEAMWORK |
| Quota/cost | No verified provider usage data | UNKNOWN |

No bypass/allow-rule, token swapping, OAuth interception or account rotation was added. Headless availability does not prove Teamwork control. Next: operator opens two officially permitted sessions, supplies non-secret session/runtime IDs and time overlap; observe exact workspace, role ACK, real edits/self-QA/checkpoint/rework. Keep frozen ownership until prior context safely verified stopped/isolated. Do not infer impossibility from unverified concurrency.
