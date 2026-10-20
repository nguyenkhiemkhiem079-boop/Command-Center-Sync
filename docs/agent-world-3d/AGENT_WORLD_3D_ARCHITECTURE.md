# Agent World 3D architecture

## Placement and trust boundary

Agent World is a read-only view inside the existing Dashboard. `web/index.html` adds one navigation item without replacing Run Studio or Fleet Cockpit. `web/dashboard.js` fetches the existing authenticated `/ui/api/snapshot`, `/ui/api/run-studio`, and `/ui/api/cockpit` projections and passes normalized data into a lazily loaded module. The view never writes task state or opens SQLite.

The Python server serves only three exact Agent World asset paths and one CSS path. Data APIs retain existing session, CSRF and role authorization. No general file route was added. Existing same-origin CSP remains in force. Three.js is bundled locally as a static ES module by Vite; Vite is not needed when the Python server runs.

## Modules

- `frontend/agent-world/src/state.js`: input validation, normalized task/agent/event projection, and fail-closed runtime evidence classification.
- `frontend/agent-world/src/main.js`: procedural low-poly scene, office zones, scene picking, camera presets, timeline and fleet views, context-loss fallback, responsive behavior, resource disposal and bounded render loop.
- `web/agent-world/agent-world.js`: checked-in static ESM production bundle containing Three.js and OrbitControls.
- `web/agent-world.css`: isolated styles for the new view.
- `server.py`: exact static asset routing; no Dashboard deployment was performed.

## Scene mapping

Six office zones represent CODEX command, ANTI-01, ANTI-02, independent QA, Git integration and recovery. Office geometry is illustrative. The configured CODEX/ANTI identities have static, neutral observation avatars with visible UNKNOWN runtime badges when no independent runtime proof exists. Tasks, lock states, checkpoints, review events and assignment paths are rendered only from controller/Registry projections. An explicit verified Teamwork runtime signal would be required before an avatar is moved into a “working” position; current source API supplies UNKNOWN, so no coding animation is emitted.

Mission filters are kept in frontend view state. Polling updates the existing scene objects rather than rebuilding the Dashboard on each refresh. Changing Dashboard route disposes controls and WebGL resources; logout clears controller snapshots and disposes the scene.

## Failure handling

The module requests WebGL2, never a WebGL1 substitute. Missing authenticated controller data, unavailable WebGL2, mobile layout, or WebGL context loss displays the explicit fallback and retains the 2D Fleet view. Camera orbit/zoom/pan are constrained. Pixel ratio is capped at 1.4; the render loop is capped at approximately 30 fps and paused when hidden, outside the visible route, or outside the world view. Reduced-motion disables camera damping and CSS motion.

## Deployment boundary

Changes are confined to the development branch `feature/agent-world-3d`. The installed app at `C:\KTOOL\CommandCenter\MCP` and port 8876 were not modified, restarted, or deployed. The deployed `/ui/api/cockpit` previously returned 404; staging proves source behavior only, not installed-version behavior.
