# Agent World 3D implementation checklist

| Area | Status | Evidence |
|---|---|---|
| Source reconciliation / dedicated branch | PASS | Development branch from `127607f`; current implementation diff in Git |
| Dashboard additive navigation | PASS | `tests/test_agent_world.py`; browser navigation |
| Local pinned Three.js bundle and license | PASS | npm lock/build; exact server allowlist tests |
| Authenticated API data projection | PASS | Existing snapshot/Run Studio/Cockpit source tests; controller source labels |
| Verified vs reported vs unknown runtime | PASS | Node adversarial normalization tests; browser UNKNOWN badges |
| 3D render and controls | PASS | Chrome 155 headless WebGL2 screenshot and interaction checks |
| Mobile/WebGL fallback behavior | PASS (no-WebGL fallback) / PARTIAL (mobile) | Chrome `--disable-webgl` visibly displayed fallback and preserved Fleet/Timeline; no physical mobile run |
| Full regression | PASS | Full Python suite 235/235, frontend tests 6/6, local Vite bundle build; `full-regression-tests.txt` |
| Live Dashboard deployment at 8876 | PASS (incremental UI deployment) | Live page/assets 200; authenticated APIs remain 401 without session; SQLite backup hash unchanged; `LIVE_DEPLOYMENT_REPORT_VI.md` |
| Real Antigravity sessions / Teamwork | BLOCKED | Runtime API returns UNKNOWN; no real session evidence |
| RTX 3060 Ti performance / memory | NOT_EXECUTED | Browser used headless SwiftShader; no target GPU measurement |
| PR review | PASS (opened) | PR #4 is open against `feature/full-fix-e2e-acceptance`; hosted scope policy remains failed closed |
| Protected merge / release | NOT_EXECUTED | UI deployment was explicitly requested; no protected merge or release occurred |

## Post-deployment QA and state-accuracy fix

See [POST_DEPLOYMENT_QA_REPORT_VI.md](POST_DEPLOYMENT_QA_REPORT_VI.md) for the 2026-10-19 recheck. The source candidate now distinguishes review, integration QA, approval pending, accepted and integrated states; stale controller data fails closed while retaining FROZEN holds. The production installation remains at its previously authorized version; this source correction is not deployed.

| Gate | Current result | Evidence |
|---|---|---|
| Lifecycle state mapping and stale observations | PASS | `frontend/agent-world/src/state.test.js`; 9/9 frontend tests |
| Full Python regression | PASS | `post-review-full-regression.txt`; 235 tests |
| Vite bundle and dependency audit | PASS | Build success; `npm audit --audit-level=high` reported 0 vulnerabilities |
| Hosted scope gate for PR #4 | BLOCKED / FAIL CLOSED | Run `39184826232`, job `117844923574`; `OWNER_APPROVED_BASE_POLICY_REQUIRED` |
| Trusted-base policy migration | BLOCKED pending independent owner review | `SCOPE_POLICY_MIGRATION_REVIEW.md` |
| Live authenticated Dashboard interaction | BLOCKED | `/ui` 200, data APIs 401 without active session; browser UI helper timed out; no session was altered |
| GPU WebGL and context recovery | PASS on RTX 3050 staging | 3-minute hardware-rendered Chrome soak; renderer and memory details in post-deployment report |
| RTX 3060 Ti target performance | NOT_EXECUTED | Machine reports NVIDIA RTX 3050 4 GB |
| Production deploy / merge | NOT_EXECUTED | Requires fresh owner approval; no live change made |
