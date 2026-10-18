# Three.js asset and license manifest

| Asset | Version/source | License | Runtime origin |
|---|---|---|---|
| Three.js | npm `three@0.186.1`, pinned in package and lock file | MIT; bundled notice at `web/agent-world/three-LICENSE.txt` | Same-origin `/ui/agent-world/agent-world.js` |
| OrbitControls | `three/addons/controls/OrbitControls.js` from the pinned Three.js package | Same Three.js MIT distribution | Bundled into the same static ESM asset |
| Vite | npm `vite@8.3.4`, pinned in package and lock file; build-time only | MIT | Not used by the deployed Python server |
| Office models/textures | Procedural geometry and locally generated canvas labels | Original project code; no third-party model assets | No remote asset loads |

The source package is locked by `frontend/agent-world/package-lock.json`. Production runtime requires neither Node.js nor a CDN. Chrome network evidence on staging recorded zero off-origin requests. Dependency installation and bundle generation are developer/build operations only. The package license is retained alongside the compiled artifact.
