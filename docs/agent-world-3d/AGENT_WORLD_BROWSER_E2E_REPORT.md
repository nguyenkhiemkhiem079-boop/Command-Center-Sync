# Agent World browser end-to-end report

Result: PASS for source Dashboard staging only.

- Browser: Windows Chrome `155.0.8059.41`, headless, viewport 1600×1100.
- Renderer: ANGLE / Vulkan SwiftShader software renderer.
- Server: disposable source `server.py` on an ephemeral loopback port.
- Data: fresh temporary SQLite Registry and temporary CODEX credential; no task/activity was seeded.
- Actions verified: authenticated login, Agent World navigation, WebGL2 canvas creation, 2D Fleet switch, CODEX inspector selection, Event Timeline switch, return to 3D, ANTI-01 camera preset, screenshot capture.
- Failure mode: a second Chrome session with WebGL disabled visibly displayed the fallback message and Open 2D Fleet action; Fleet and Timeline navigation remained available.
- Network: zero off-origin resource requests; static bundle loaded from same-origin allowlisted endpoint.
- Console: zero JavaScript exceptions. The initial unauthenticated snapshot before login and missing favicon returned 401/404 respectively; successful post-login data calls returned 200.
- Screenshots: `AGENT_WORLD_SCREENSHOTS/agent-world-chrome-staging.png` and `AGENT_WORLD_SCREENSHOTS/agent-world-chrome-no-webgl.png`.
- Machine rendering limits: SwiftShader does not measure physical GPU performance. A real Chrome/Edge interactive desktop and RTX 3060 Ti performance pass remains NOT_EXECUTED.

The deployed dashboard at `http://127.0.0.1:8876/ui` was not changed. A prior inspection found the installed source did not provide `/ui/api/cockpit` (404), so this source staging result does not establish that Agent World works on the currently installed version.
