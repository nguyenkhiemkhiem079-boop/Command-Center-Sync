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

## Task lifecycle projection

The controller's task and integration lifecycles are separate. The frontend preserves these distinctions:

| Backend state | Agent World state | Separate gate fields |
|---|---|---|
| `CODE_REVIEWED`, `PASS_CODE_REVIEW` | `REVIEW_PASSED` | `reviewState=PASSED`, `integrationState=INTEGRATION_PENDING`, `acceptanceState=NOT_ACCEPTED` |
| `PREPARE`, `VALIDATE` | `INTEGRATION_PENDING` | Integration has not completed |
| `INTEGRATION_QA*` | `INTEGRATION_QA` | Combined integration QA is running or recorded |
| `APPROVAL_PENDING` | `APPROVAL_PENDING` | `approvalState=PENDING`, not accepted/integrated |
| `ACCEPTED` | `ACCEPTED` | Accepted by the controller's independent verifier; not proof of protected merge/release |
| `INTEGRATED`, `COMMITTED`, `COMPLETE` | `INTEGRATED` | Integration is complete; release is still a separate approval |
| `FROZEN` | `BLOCKED` | Frozen ownership remains visible and is never implied accepted |
| Unrecognized state | `UNKNOWN` | No positive inference |

The projection also exposes `observationState` and per-task `freshness`. A controller observation older than five minutes, or more than one minute in the future, is stale. Stale operational task/session states become `UNKNOWN`; an explicitly recorded `FROZEN` task or lock remains blocked as a safety hold. Missing timestamps are labeled `UNKNOWN` freshness and are never replaced with the browser's current time. This is presentation safety, not a controller state transition.
