# Runtime feasibility — K-TOOL

Audit date: 2026-10-18. Runtime metadata is evidence of a process, never independent
code QA or Revit acceptance. No consumer credentials, OAuth stores or internal
reasoning were inspected. Only structured status/tool metadata was extracted from
existing local pilot logs; raw payloads are not reproduced here.

## Supported surfaces and gates

| Mode | Detection | Dispatch and acceptance |
|---|---|---|
| `AGY_HEADLESS` | Existing executable plus observed `--print`, `--output-format`, `--conversation` help flags | Explicit task, fixed argv, assigned cwd, bounded timeout; no silent retry |
| `TEAMWORK_NATIVE` | `BLOCKED_NO_VERIFIED_START_MONITOR_BACKEND` even if caller supplies a Boolean or fabricated capability dictionary | `SUPERVISED_MANUAL_LAUNCH` required; tool denials remain in force; no retries or automated native launch |
| `SUPERVISED_IDE` | Conservative fallback | Returns a human-dispatch requirement; does not invent IDE remote control |
| API coding worker | No authorized API endpoint/credential contract supplied | `UNAVAILABLE_NO_AUTHORIZED_API_CONFIGURATION`; no network probe or consumer-router credential reuse |

Installed `agy --help` was executed read-only. It exposes print, stream JSON,
conversation UUID, print timeout, sandbox and permissions flags. No account switch,
login, credential lookup, third-party router execution or dependency installation
was performed. The adapter never adds `--dangerously-skip-permissions`.

The [official headless documentation](https://antigravity.google/docs/cli/headless/)
describes NDJSON init/step/result events, conversation resumption and tool error
metadata. The adapter resumes a specific UUID, never whichever conversation was
most recent. It discards response text, reasoning, usage, tool arguments/output
and raw stderr. Only bounded status/tool metadata and UUIDs enter its report.
Documented success does not override observed denials: denial counters are a local
observed extension, not a field guaranteed by that documentation.

[Official Teamwork documentation](https://antigravity.google/docs/teamwork/)
describes `/teamwork-preview`, paid-plan availability and a scoping/approval flow
before autonomous milestones. [Official subagents documentation](https://antigravity.google/docs/subagents/)
describes delegated background agents. These are native conversation workflows,
not equivalent to switching the provider account serving an inference request.
[Official MCP documentation](https://antigravity.google/docs/mcp/) identifies
`.agents/mcp_config.json` as a workspace config. Successful MCP authentication
establishes tool access, not native Teamwork execution or entitlement.

## Local pilot evidence and parser rules

Both existing `evidence-v07/agy-01-teamwork.jsonl` and
`evidence-v07/agy-02-teamwork.jsonl` finish with `SUCCESS`, an empty response and
one denied action. Each contains two tool steps in `ERROR`. The new parser reports
`BLOCKED`, retains denial/error counts and discards all raw content. Neither is
accepted as completed native Teamwork work.

Any denied action or timeout produces `BLOCKED`; tool failures, changed
conversation IDs, malformed/out-of-order streams, missing/duplicate terminal
results, empty final response and nonzero exits produce `FAIL` unless a blocking
condition takes precedence. A clean process produces `COMPLETED_UNVERIFIED`, never
`PASS`. Integration acceptance requires actual diff/build/tests/preview evidence.

`Assignment` carries worker/task/scope/fencing metadata. It does not enforce
Registry ownership or filesystem ACLs itself; the dispatcher must obtain a live
Registry lock before launching. Same-user execution remains `LOGICAL_ONLY`.

Supervision launches exactly one explicit argv with `shell=False`, closes stdin,
discards stderr and bounds NDJSON lines and queues. On timeout it requests Windows
`taskkill /PID <owned child> /T /F`, then terminates its direct child if needed.
This is not a Windows Job Object or a proof that detached grandchildren are gone.
Cleanup failures are reported; no task is restarted and no lock is released.

## Reproduction

```powershell
# Use the existing authorized Python venv; no global pip required.
python -m unittest discover -s tests -p test_anti_runtime.py -v
agy --help
```

The suite uses Python fixture subprocesses, not live paid agents. It also parses
both existing local pilot logs if present, without reproducing their contents.
Router findings and immutable source links are in `router-research.md`.
