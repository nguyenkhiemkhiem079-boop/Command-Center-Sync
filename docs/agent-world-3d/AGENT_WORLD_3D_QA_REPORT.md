# Agent World 3D QA report

Date: 2026-10-19 (Asia/Bangkok). Source base: `127607f05f98a53ad7447dfa2f24721554ed6361`. Branch: `feature/agent-world-3d`; latest deployed source head: `cf755c69783a66fd14ade5cc248f816f5eb4effd`.

Validated source commit: `1b195cc3a44cafa754f7653284cd43297bec240d` (pushed). Review PR: [#4](https://github.com/nguyenkhiemkhiem079-boop/Command-Center-Sync/pull/4), targeting `feature/full-fix-e2e-acceptance`; not merged.

## Automated gates

| Gate | Result | Evidence |
|---|---|---|
| 1. Architecture and route isolation | PASS | `tests/test_agent_world.py`; exact asset routing, unknown path and traversal return 404 |
| 2. Real data mapping and evidence labels | PASS | `frontend/agent-world/src/state.test.js`; controller projection remains source-labeled; Teamwork defaults UNKNOWN |
| 3. Permission/session handling | PASS | Authenticated cockpit tests return 401 before login; existing CSP and session controls retained |
| 4. Rendering and disposal | PASS | Browser WebGL2 canvas; route/logout disposal code; context loss/restoration handlers |
| 5. Performance behavior | PARTIAL | DPR cap, 30 fps cap, hidden-view pause verified in source; headless GPU is SwiftShader, no RTX target measurement |
| 6. Accessibility and reduced motion | PARTIAL | Keyboard controls, visible focus and reduced-motion implementation; manual assistive-tech audit not run |
| 7. UX and responsive modes | PASS | 1600x1100 Chrome screenshot; 2D Fleet and Timeline interaction exercised |
| 8. API integration and security headers | PASS | Disposable source server: login, snapshot, Run Studio and Cockpit requests; zero off-origin requests; CSP regression tests |
| 9. WebGL fallback / mobile | PASS (fallback) / PARTIAL (mobile) | Chrome with `--disable-webgl` displayed a visible fallback and retained 2D Fleet; physical mobile browser not exercised |
| 10. Regression | PASS | Full Python unittest suite: 235 tests passed; frontend Node tests: 6 passed; Vite bundle built |

`npm audit --audit-level=high`: 0 vulnerabilities. `npm ls --all --depth=1` confirmed pinned Three.js 0.186.1 and Vite 8.3.4; reported unmet packages are optional dependencies not used by this build.

Hosted `Trusted base scope policy` check: **FAIL closed / PR quarantined** at head `5d555059e6f70b346264acdf5d55b5312de43084` (run `39154581560`, job `117755042235`). The trusted-base workflow checked out `127607f05f98a53ad7447dfa2f24721554ed6361`, required `.github/scope-policy.json`, then the verifier returned `OWNER_APPROVED_BASE_POLICY_REQUIRED` and `quarantine=true`. The same failure was independently reproduced on the code commit `1b195cc3a44cafa754f7653284cd43297bec240d`. This is a missing approved policy prerequisite, not an Agent World path violation. No policy or branch-protection change was included. See `hosted-scope-check.json` and the linked GitHub run.

## Browser evidence

The staging harness launched local Chrome `155.0.8059.41` with fresh temporary profiles, a disposable SQLite Registry and temporary CODEX token. It logged in through the application, opened Agent World, verified a WebGL2 canvas, switched to 2D Fleet and Event Timeline, inspected CODEX, used the ANTI-01 camera preset, returned to 3D and wrote `AGENT_WORLD_SCREENSHOTS/agent-world-chrome-staging.png`. A second Chrome run with WebGL disabled verified the visible fallback and produced `AGENT_WORLD_SCREENSHOTS/agent-world-chrome-no-webgl.png`. Network capture found zero off-origin requests. The observed 3D renderer was ANGLE/SwiftShader; this validates browser functionality, not RTX 3060 Ti throughput. The disposable server, tokens, database and browser profiles were removed after each run.

The browser emitted initial expected unauthorized snapshot requests before login and favicon 404 during page startup; authenticated API requests succeeded afterward. No JavaScript runtime exceptions were observed. These startup messages are not application operation failures. A no-WebGL run initially exposed a hidden fallback pane; after correction, a second screenshot confirmed the explanation and Fleet link are visible.

## Re-QA and incremental live deployment (2026-10-19)

The full locked Python 3.12 regression was rerun: **235/235 PASS** (`retest-20261019.txt`). Frontend tests were rerun at **6/6 PASS**, Vite production build succeeded, and `npm audit --audit-level=high` found **0 vulnerabilities**; log is stored with the deployment evidence. To check compatibility with the older installed v0.7 server, the old server, Registry and orchestration modules were copied into a disposable directory with a fresh SQLite Registry and one-time credential; the Agent World route patch and current bundled assets passed authenticated Chrome 155 WebGL2 and no-WebGL browser tests. The JSON results and screenshots are in `C:\KTOOL\CommandCenter\deployments\20261019-AGENT-WORLD-3D-cf755c6\browser-compat`.

At the owner's request, the additive Dashboard change is now live at `http://127.0.0.1:8876/ui`. Seven files were installed after backing them up. The verified coordinator health, page, styles, dashboard script, 3D bundle and license returned HTTP 200. Unauthenticated snapshot, Run Studio and Cockpit endpoints all returned HTTP 401. The online SQLite backup passed integrity check; the hash from startup matched the pre-deployment snapshot, so Registry data remained unchanged. Evidence and rollback files are in `C:\KTOOL\CommandCenter\deployments\20261019-AGENT-WORLD-3D-cf755c6`. No production source branch merge or release was made.

## Safety and limits

The live Dashboard was updated only as requested; credentials and role configuration were not read or changed, and no K-TOOL Revit source was touched. Provider/runtime state remains UNKNOWN. Therefore real Antigravity session, two-agent activity and Teamwork acceptance remain BLOCKED, not passed. The change is an additive local UI deployment and did not merge a protected branch or release production source. Target GPU performance and Revit 2025 runtime remain NOT_EXECUTED.
