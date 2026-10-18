# Agent World runtime state contract

## Evidence labels

- `VERIFIED`: set only when a controller record contains an explicit verified Teamwork-active state and verification class. The current cockpit adapter does not emit such evidence; current runtime is UNKNOWN.
- `AGENT_REPORTED`: a worker-originated claim. It is not treated as proof of session execution or QA.
- `UNKNOWN`: missing, stale, malformed, or unverified observation. This is the default for runtime, provider account, branch/worktree, quota, and external session state.

## Data sources and allowed inference

| Display field | Source | Permitted inference |
|---|---|---|
| Configured role | Authenticated role/cockpit projection | Identity is configured, not signed into Antigravity |
| MCP contact | Existing controller metadata | MCP reachability only if the controller reports it; no Teamwork inference |
| Assignment and task state | Run Studio/Registry projection | Recorded task metadata only |
| Ownership/lock | Controller snapshot | Logical ownership; does not prove NTFS isolation |
| Checkpoint | Recorded checkpoint reference | A record exists; not independent QA or accepted output |
| Teamwork session | Verified runtime attestation, if provided | Active only with explicit `TEAMWORK_ACTIVE` plus `VERIFIED` evidence |
| Events | Controller timeline | Historical recorded event; replay is labeled, no gap-filling |
| Integration/CI/approval | Controller record only | UNKNOWN unless an actual source record supplies the value |

The adapter rejects unsafe labels, bounds display strings, maps FROZEN to BLOCKED, and never infers IN_PROGRESS or ACCEPTED from an unknown state. Rendering is read-only and cannot approve, dispatch, merge, or release work.
