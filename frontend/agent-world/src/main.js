import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { normalizeAgentWorld } from './state.js';

const palette = {
  navy: 0x0b1729, floor: 0x10223a, tile: 0x142b47, edge: 0x31506f,
  cyan: 0x41d9e8, blue: 0x5ca3ff, violet: 0x9c88ff, amber: 0xf3bd61,
  red: 0xff7580, green: 0x66dbac, white: 0xd8e8fa, muted: 0x8097b4,
};
const STATUS_COLOR = {
  ASSIGNED: palette.blue, ACKNOWLEDGED: palette.cyan, IN_PROGRESS: palette.green,
  AWAITING_QA: palette.amber, FEEDBACK_REQUESTED: palette.violet,
  BLOCKED: palette.red, ACCEPTED: palette.green, UNKNOWN: palette.muted,
};
const PRESETS = {
  overview: { position: [15, 18, 22], target: [0, 0, 0], label: 'Isometric overview' },
  top: { position: [0, 26, 0.05], target: [0, 0, 0], label: 'Top view' },
  codex: { position: [0, 10, 9], target: [0, 0, 0], label: 'Codex station' },
  anti01: { position: [-8, 10, 8], target: [-6, 0, 1], label: 'ANTI-01 station' },
  anti02: { position: [8, 10, 8], target: [6, 0, 1], label: 'ANTI-02 station' },
  qa: { position: [1, 10, -9], target: [0, 0, -6], label: 'Independent QA lab' },
};
const makeMaterial = (color, opts = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.78, metalness: 0.08, ...opts });

function textTexture(title, subtitle = '') {
  const canvas = document.createElement('canvas');
  canvas.width = 512; canvas.height = 128;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#d8e8fa'; ctx.font = '700 36px Segoe UI, sans-serif';
  ctx.fillText(String(title).slice(0, 28), 14, 52);
  ctx.fillStyle = '#8da4c2'; ctx.font = '500 22px Segoe UI, sans-serif';
  ctx.fillText(String(subtitle).slice(0, 42), 16, 88);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function badge(title, subtitle, position, width = 4.1) {
  const material = new THREE.MeshBasicMaterial({ map: textTexture(title, subtitle), transparent: true, side: THREE.DoubleSide, depthWrite: false });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, width / 4), material);
  mesh.position.set(...position); mesh.rotation.x = -Math.PI / 2; mesh.userData.disposeTexture = true;
  return mesh;
}

function box(parent, dimensions, position, material, options = {}) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(...dimensions), material);
  mesh.position.set(...position); mesh.castShadow = false; mesh.receiveShadow = false;
  if (options.name) mesh.name = options.name;
  if (options.detail) mesh.userData.detail = options.detail;
  parent.add(mesh); return mesh;
}

function makeAvatar(agent) {
  const group = new THREE.Group();
  const isCodex = agent.id === 'CODEX';
  const color = isCodex ? palette.violet : (agent.id === 'ANTI-01' ? palette.cyan : palette.blue);
  const bodyMat = makeMaterial(color);
  const darkMat = makeMaterial(0x17283e);
  const faceMat = makeMaterial(0xd6e8f4, { roughness: 0.48 });
  const body = new THREE.Mesh(new THREE.CylinderGeometry(0.31, 0.42, 0.8, 6), bodyMat);
  body.position.y = 0.72; body.castShadow = false; group.add(body);
  const head = new THREE.Mesh(new THREE.IcosahedronGeometry(0.34, 0), faceMat);
  head.position.y = 1.36; group.add(head);
  const visor = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.12, 0.47), darkMat);
  visor.position.set(0, 1.37, 0.23); group.add(visor);
  const eyeMat = new THREE.MeshBasicMaterial({ color });
  for (const x of [-0.105, 0.105]) {
    const eye = new THREE.Mesh(new THREE.SphereGeometry(0.035, 6, 5), eyeMat);
    eye.position.set(x, 1.38, 0.475); group.add(eye);
  }
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.5, 0.035, 5, 16), makeMaterial(color, { emissive: color, emissiveIntensity: 0.28 }));
  ring.rotation.x = Math.PI / 2; ring.position.y = 0.08; group.add(ring);
  group.userData.agentId = agent.id;
  group.userData.isCodex = isCodex;
  return group;
}

function makeDesk(scene, x, z, color, agentId, workstation) {
  const group = new THREE.Group(); group.position.set(x, 0, z); group.userData.agentId = agentId; group.userData.workstation = workstation;
  const wood = makeMaterial(0x253b55); const leg = makeMaterial(0x516b84); const screen = makeMaterial(0x183952, { emissive: color, emissiveIntensity: 0.12, roughness: 0.4 });
  box(group, [2.6, 0.16, 1.2], [0, 1.08, 0], wood);
  for (const dx of [-1.08, 1.08]) for (const dz of [-0.42, 0.42]) box(group, [0.1, 1.0, 0.1], [dx, 0.5, dz], leg);
  box(group, [1.2, 0.78, 0.12], [0, 1.65, -0.36], leg);
  const display = box(group, [1.12, 0.68, 0.08], [0, 1.67, -0.275], screen, { name: `screen-${agentId}-${workstation}` });
  display.userData.glowMaterial = screen;
  box(group, [0.48, 0.05, 0.3], [0, 1.18, 0.3], makeMaterial(0x526982));
  const chair = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.36, 0.12, 8), makeMaterial(0x263c55));
  chair.position.set(0, 0.56, 1.08); group.add(chair);
  const back = box(group, [0.68, 0.86, 0.12], [0, 0.94, 1.4], makeMaterial(0x263c55));
  back.rotation.x = -0.12;
  scene.add(group); return { group, display, screen };
}

function buildOffice(scene, model, records) {
  const mats = {
    floor: makeMaterial(palette.floor), tile: makeMaterial(palette.tile), wall: makeMaterial(0x1a324d),
    glass: new THREE.MeshPhysicalMaterial({ color: 0x5ca3ff, transparent: true, opacity: 0.12, roughness: 0.25, metalness: 0.12, depthWrite: false }),
    cyan: makeMaterial(palette.cyan, { emissive: palette.cyan, emissiveIntensity: 0.25 }),
    blue: makeMaterial(palette.blue, { emissive: palette.blue, emissiveIntensity: 0.2 }),
  };
  box(scene, [26, 0.32, 20], [0, -0.28, -1], mats.floor);
  const grid = new THREE.GridHelper(26, 26, 0x33506d, 0x203c5b); grid.position.y = -0.105; scene.add(grid);
  const zones = [
    { id: 'CODEX', title: 'CODEX COMMAND', x: 0, z: 1.5, w: 5.8, h: 5.1, color: palette.violet, subtitle: 'Supervisor · runtime UNKNOWN' },
    { id: 'ANTI-01', title: 'ANTI-01 DEVELOPMENT', x: -7, z: 0, w: 6.2, h: 6.4, color: palette.cyan, subtitle: 'Research · Build · Self-QA · Git' },
    { id: 'ANTI-02', title: 'ANTI-02 DEVELOPMENT', x: 7, z: 0, w: 6.2, h: 6.4, color: palette.blue, subtitle: 'Research · Build · Self-QA · Git' },
    { id: 'QA', title: 'INDEPENDENT QA LAB', x: 0, z: -7, w: 7.2, h: 4.2, color: palette.amber, subtitle: 'Evidence recorded by controller' },
    { id: 'GIT', title: 'GIT INTEGRATION', x: 8, z: -7, w: 6.1, h: 4.2, color: palette.green, subtitle: 'Central protected · approval required' },
    { id: 'RECOVERY', title: 'RECOVERY CENTER', x: -8, z: -7, w: 6.1, h: 4.2, color: palette.red, subtitle: 'Frozen ownership is retained' },
  ];
  const interactive = [];
  for (const zone of zones) {
    const slab = box(scene, [zone.w, 0.14, zone.h], [zone.x, -0.04, zone.z], mats.tile, {
      name: `zone-${zone.id}`, detail: { kind: 'zone', id: zone.id, title: zone.title, subtitle: zone.subtitle },
    });
    interactive.push(slab);
    const border = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(zone.w, 0.15, zone.h)), new THREE.LineBasicMaterial({ color: zone.color, transparent: true, opacity: 0.6 }));
    border.position.copy(slab.position); scene.add(border);
    scene.add(badge(zone.title, zone.subtitle, [zone.x, 0.12, zone.z - zone.h / 2 + 0.5], Math.min(5.2, zone.w - 0.35)));
  }
  // Short glass dividers separate work zones while retaining the overview.
  for (const [x, z, sx, sz] of [[-3.7, 0, 0.12, 5.8], [3.7, 0, 0.12, 5.8], [0, -4.3, 7, 0.1]]) {
    const pane = box(scene, [sx, 1.7, sz], [x, 0.82, z], mats.glass); pane.material = mats.glass;
  }

  const deskRecords = [
    { agent: 'CODEX', x: 0, z: 1.7, station: 'Review & Mission' },
    { agent: 'ANTI-01', x: -7, z: 0.2, station: 'Research / Implementation / Self-QA / Git' },
    { agent: 'ANTI-02', x: 7, z: 0.2, station: 'Research / Implementation / Self-QA / Git' },
  ];
  for (const item of deskRecords) {
    const agent = model.agents.find((entry) => entry.id === item.agent);
    const desk = makeDesk(scene, item.x, item.z, item.agent === 'CODEX' ? palette.violet : (item.agent === 'ANTI-01' ? palette.cyan : palette.blue), item.agent, item.station);
    const avatar = makeAvatar(agent || { id: item.agent });
    // Without a verified active session, keep the avatar at a neutral observation marker beside the desk.
    const active = agent?.teamwork === 'TEAMWORK_ACTIVE' && agent?.evidenceClass === 'VERIFIED';
    avatar.position.set(item.x + (active ? 0 : -1.55), 0, item.z + 2.0);
    avatar.userData.detail = { kind: 'agent', id: item.agent };
    scene.add(avatar);
    const identityBadge = badge(item.agent, `${agent?.teamwork || 'UNKNOWN'} · ${agent?.evidenceClass || 'UNKNOWN'}`, [item.x + (active ? 0 : -1.55), 1.95, item.z + 2.0], 2.8);
    scene.add(identityBadge); records.agents.set(item.agent, { avatar, desk, active, agent, badge: identityBadge });
    interactive.push(avatar, desk.group);
    if (item.agent !== 'CODEX') {
      const stationNames = ['Research', 'Implementation', 'Self-QA', 'Git checkpoint'];
      stationNames.forEach((name, index) => {
        const sx = item.x - 2.35 + index * 1.55; const sz = -2.15;
        const shell = makeMaterial(0x1a2c43);
        box(scene, [1.15, 0.72, 0.72], [sx, 0.34, sz], shell);
        box(scene, [0.95, 0.46, 0.045], [sx, 0.39, sz + 0.39], makeMaterial(0x203d56, { emissive: palette.muted, emissiveIntensity: 0.08 }));
        scene.add(badge(name.toUpperCase(), 'NO EVENT RECORDED', [sx, 0.92, sz - 0.04], 1.5));
      });
    }
  }
  const subagentOffsets = new Map();
  for (const subagent of model.subagents || []) {
    const parentId = ['ANTI-01', 'ANTI-02'].includes(subagent.parent) ? subagent.parent : null;
    const parent = parentId ? deskRecords.find((item) => item.agent === parentId) : { x: -8, z: -7 };
    const offsetKey = parentId || 'UNKNOWN_PARENT';
    const index = subagentOffsets.get(offsetKey) || 0; subagentOffsets.set(offsetKey, index + 1);
    const x = parent.x + (index % 2 === 0 ? 1.6 : -1.6); const z = parent.z - 2.2 - Math.floor(index / 2) * 1.4;
    const avatar = makeAvatar({ id: subagent.id, role: 'SUBAGENT' });
    avatar.position.set(x, 0, z); avatar.userData.detail = { kind: 'agent', id: subagent.id };
    scene.add(avatar); records.agents.set(subagent.id, { avatar, desk: null, active: false, agent: subagent });
    interactive.push(avatar);
    scene.add(badge(subagent.id, `${parentId || 'PARENT UNKNOWN'} · ${subagent.state || 'UNKNOWN'}`, [x, 1.9, z], 2.4));
  }

  for (const [x, z, label, color, detail] of [
    [0, -6.8, 'BUILD · TEST · EVIDENCE', palette.amber, { kind: 'zone', id: 'QA', title: 'Independent QA Lab' }],
    [8, -6.8, 'BRANCHES → CANDIDATE → CENTRAL', palette.green, { kind: 'zone', id: 'GIT', title: 'Git Integration Center' }],
    [-8, -6.8, 'FROZEN · CHECKPOINT · RESUME GATE', palette.red, { kind: 'zone', id: 'RECOVERY', title: 'Recovery Center' }],
  ]) {
    const mat = makeMaterial(0x1b2e46);
    const consoleMesh = box(scene, [3.0, 0.68, 0.24], [x, 0.52, z], mat, { detail });
    const status = box(scene, [2.76, 0.48, 0.035], [x, 0.55, z + 0.14], makeMaterial(color, { emissive: color, emissiveIntensity: 0.22 }));
    status.userData.displayLabel = label; interactive.push(consoleMesh, status);
  }

  const center = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.65, 0.12, 8), makeMaterial(0x213b58));
  center.position.set(0, -0.1, -2.4); scene.add(center);
  return { interactive, zones, materials: mats };
}

function detailText(agent, task) {
  if (agent) {
    const taskText = agent.tasks.length ? agent.tasks.map((entry) => `${entry.id} · ${entry.state} · ${entry.scope}`).join('\n') : 'No assignment recorded';
    const inherited = agent.role === 'SUBAGENT' ? `\nParent team: ${agent.parent}\nParent assignment: ${agent.assignment}\n` : '';
    return `${agent.id} · ${agent.role}\nMCP: ${agent.mcp}\nAntigravity runtime: ${agent.runtime}\nTeamwork: ${agent.teamwork}\nEvidence: ${agent.evidenceClass}${inherited}\nGit branch/worktree: UNKNOWN unless explicitly recorded\nSource: ${agent.source}\nObserved: ${agent.lastObservedAt}\nAssignments:\n${taskText}`;
  }
  if (task) return `${task.id} · ${task.title}\nOwner: ${task.owner}\nState: ${task.state} (controller/Registry record)\nScope: ${task.scope}\nWave: ${task.wave}\nMission: ${task.mission}\nCheckpoint recorded: ${task.checkpoint ? 'YES — controller metadata' : 'NO'}\nEvidence class: ${task.evidence}`;
  return 'Select an agent, workstation, task path or office zone to inspect controller-recorded metadata.';
}

function agentWorldMarkup(model) {
  const missionLabel = model?.mission || 'UNKNOWN';
  const missionOptions = (model?.missions || []).map((mission) => `<option value="${escapeText(mission)}">${escapeText(mission)}</option>`).join('');
  return `<section id="agent-world-root" class="aw-shell" aria-label="Agent World 3D operational view">
    <div class="aw-topline"><div><b>AGENT WORLD</b><span>Controller data · ${escapeText(model?.source || 'UNKNOWN')} · ${escapeText(model?.observedAt || 'UNKNOWN')}</span></div><label>Mission <select id="aw-mission" aria-label="Filter mission"><option value="all">All recorded missions</option>${missionOptions || `<option value="${escapeText(missionLabel)}">${escapeText(missionLabel)}</option>`}</select></label></div>
    <div class="aw-viewtabs" role="tablist" aria-label="Agent World view"><button type="button" data-aw-view="world" role="tab" aria-selected="true">3D World</button><button type="button" data-aw-view="fleet" role="tab" aria-selected="false">2D Fleet</button><button type="button" data-aw-view="timeline" role="tab" aria-selected="false">Event Timeline</button><span class="aw-source-pill">VERIFIED activity only · runtime defaults UNKNOWN</span></div>
    <div class="aw-layout"><div class="aw-stage">
      <div id="aw-world-pane" class="aw-world-pane"><canvas id="aw-canvas" tabindex="0" aria-label="Interactive low-poly agent office; see adjacent text for agent states"></canvas><div id="aw-fallback" class="aw-fallback" hidden role="status"></div><div class="aw-hud"><span>AGENT WORLD · LIVE REGISTRY PROJECTION</span><span id="aw-status">Reading controller metadata…</span></div></div>
      <div id="aw-fleet-pane" class="aw-list-pane" hidden></div>
      <div id="aw-timeline-pane" class="aw-list-pane" hidden><div class="aw-filters"><label>Agent <select id="aw-agent-filter"><option value="all">All</option><option>CODEX</option><option>ANTI-01</option><option>ANTI-02</option></select></label><label>Type <select id="aw-type-filter"><option value="all">All recorded events</option></select></label><label>Wave <select id="aw-wave-filter"><option value="all">All recorded waves</option></select></label><label>Since <input type="datetime-local" id="aw-time-filter"></label><span>Historical records are labeled REPLAY; no events are invented.</span></div><div id="aw-timeline-list"></div></div>
      <div class="aw-camera" aria-label="Camera presets">${Object.entries(PRESETS).map(([key, value]) => `<button type="button" data-camera="${key}" title="${value.label}">${escapeText(value.label)}</button>`).join('')}<button type="button" data-camera="overview">Reset</button></div>
    </div><aside class="aw-inspector" aria-live="polite"><div class="aw-inspector-head"><div class="aw-eyebrow">LIVE CONTROLLER OBSERVATION</div><h2 id="aw-selected-title">Agent overview</h2><span id="aw-evidence-class" class="aw-evidence">UNKNOWN</span></div><pre id="aw-detail">${escapeText(detailText(null, null))}</pre><div class="aw-summary" id="aw-summary"></div><div class="aw-legend"><b>State legend</b><span><i class="dot assigned"></i> Assigned</span><span><i class="dot active"></i> Controller says in progress</span><span><i class="dot blocked"></i> Frozen / blocked</span><span><i class="dot unknown"></i> Runtime unknown</span></div><p class="aw-disclaimer">MCP connection, assignment and self-QA records do not prove an Antigravity session or active coding. This scene is read-only.</p></aside></div>
  </section>`;
}
function escapeText(value) { return String(value ?? '').replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch])); }

export function mountAgentWorld({ host, initialModel, initialMissionFilter = 'all' } = {}) {
  const root = host?.querySelector('#agent-world-root');
  if (!root) return { update() {}, dispose() {} };
  const canvas = root.querySelector('#aw-canvas');
  const model = initialModel || normalizeAgentWorld({ cockpit: null });
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
  const list = [];
  let disposed = false; let frameTime = 0; let dirty = true; let selected = null; let currentModel = model;
  let view = 'world'; let cameraTween = null; let missionFilter = initialMissionFilter;
  let webglLost = false;
  const agentObjects = new Map(); const taskLines = new Map();
  const raycaster = new THREE.Raycaster(); raycaster.params.Line.threshold = 0.2;
  const pointer = new THREE.Vector2();
  const statusNode = root.querySelector('#aw-status');
  const fallback = root.querySelector('#aw-fallback');
  const setFallback = (message) => {
    fallback.hidden = false;
    fallback.innerHTML = `<b>3D rendering unavailable</b><p>${escapeText(message)}</p><button type="button" data-aw-view="fleet">Open 2D Fleet</button>`;
    canvas.hidden = true;
  };
  if (!currentModel.available) setFallback('Controller observation is unavailable. Use the existing Fleet Cockpit or refresh the page.');
  let renderer = null; let controls = null; let scene = null; let camera = null; let office = null;

  if (currentModel.available && !window.matchMedia?.('(max-width: 760px)').matches) {
    try {
      const gl = canvas.getContext('webgl2', { antialias: true, powerPreference: 'low-power', alpha: false, preserveDrawingBuffer: false });
      if (!gl) throw new Error('This browser does not provide WebGL2.');
      scene = new THREE.Scene(); scene.background = new THREE.Color(palette.navy); scene.fog = new THREE.Fog(palette.navy, 24, 54);
      camera = new THREE.PerspectiveCamera(38, 1, 0.1, 120);
      camera.position.set(...PRESETS.overview.position);
      renderer = new THREE.WebGLRenderer({ canvas, context: gl, antialias: true, powerPreference: 'low-power' });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.4));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.08;
      renderer.setClearColor(palette.navy, 1);
      scene.add(new THREE.HemisphereLight(0x9bc9ef, 0x16243a, 2.15));
      const keyLight = new THREE.DirectionalLight(0x9bdcff, 2.2); keyLight.position.set(-8, 16, 12); scene.add(keyLight);
      const fill = new THREE.PointLight(0x3b9dcb, 18, 30); fill.position.set(6, 8, -6); scene.add(fill);
      controls = new OrbitControls(camera, canvas);
      controls.enableDamping = !reducedMotion; controls.dampingFactor = 0.08;
      controls.minDistance = 12; controls.maxDistance = 40; controls.minPolarAngle = 0.25; controls.maxPolarAngle = 1.48;
      controls.target.set(0, 0, -1); controls.minTargetRadius = 0; controls.maxTargetRadius = 18;
      controls.addEventListener('change', () => { dirty = true; });
      office = buildOffice(scene, currentModel, { agents: agentObjects });
      const floorMaterial = makeMaterial(0x10223a);
      const foundation = new THREE.Mesh(new THREE.BoxGeometry(27, 0.5, 21), floorMaterial); foundation.position.set(0, -0.62, -1); scene.add(foundation);
      installResizeObserver();
      const animationLoop = (time) => {
        if (disposed || document.hidden || view !== 'world' || root.offsetParent === null) return;
        if (time - frameTime < 33) return;
        frameTime = time; dirty = false;
        if (cameraTween) stepCameraTween(time);
        controls.update();
        renderer.render(scene, camera);
      };
      renderer.setAnimationLoop(animationLoop);
      const onContextLost = (event) => { event.preventDefault(); webglLost = true; renderer?.setAnimationLoop(null); setFallback('WebGL2 context lost. Agent data remains available in 2D Fleet.'); };
      const onContextRestored = () => {
        webglLost = false; dirty = true;
        if (view === 'world') { fallback.hidden = true; canvas.hidden = false; renderer?.setAnimationLoop(animationLoop); }
        statusNode.textContent = 'WebGL2 context restored';
      };
      canvas.addEventListener('webglcontextlost', onContextLost);
      canvas.addEventListener('webglcontextrestored', onContextRestored);
      list.push(() => canvas.removeEventListener('webglcontextlost', onContextLost), () => canvas.removeEventListener('webglcontextrestored', onContextRestored));
      root.querySelector('#aw-status').textContent = '3D ready · live refresh follows authenticated controller polling';
    } catch (error) {
      setFallback(error?.message || 'WebGL2 initialization failed.');
    }
  } else if (currentModel.available && window.matchMedia?.('(max-width: 760px)').matches) {
    setFallback('Small-screen layout starts in 2D Fleet for readability and lower GPU use.');
  }

  function installResizeObserver() {
    const resize = () => {
      if (!renderer || !camera || !canvas.isConnected) return;
      const width = Math.max(1, canvas.clientWidth); const height = Math.max(1, canvas.clientHeight);
      renderer.setSize(width, height, false); camera.aspect = width / height; camera.updateProjectionMatrix(); dirty = true;
    };
    const observer = new ResizeObserver(resize); observer.observe(canvas.parentElement); list.push(() => observer.disconnect()); resize();
  }
  function stepCameraTween(time) {
    const tween = cameraTween; if (!tween) return;
    const t = Math.min(1, (time - tween.start) / tween.duration); const eased = t * (2 - t);
    camera.position.lerpVectors(tween.fromPosition, tween.toPosition, eased);
    controls.target.lerpVectors(tween.fromTarget, tween.toTarget, eased);
    if (t >= 1) cameraTween = null;
    dirty = true;
  }
  function focusCamera(key) {
    if (!camera || !controls || !PRESETS[key]) return;
    const preset = PRESETS[key]; const dest = new THREE.Vector3(...preset.position); const target = new THREE.Vector3(...preset.target);
    if (reducedMotion) { camera.position.copy(dest); controls.target.copy(target); controls.update(); dirty = true; return; }
    cameraTween = { start: performance.now(), duration: 400, fromPosition: camera.position.clone(), toPosition: dest, fromTarget: controls.target.clone(), toTarget: target }; dirty = true;
  }

  function syncModel(next) {
    if (!next || typeof next !== 'object') return;
    currentModel = next;
    if (statusNode) statusNode.textContent = next.available ? `Source ${next.source} · ${next.observedAt}` : `Controller observation unavailable · ${next.error || 'UNKNOWN'}`;
    const agent = next.agents.find((entry) => entry.id === selected?.id);
    const task = next.tasks.find((entry) => entry.id === selected?.id);
    renderInspector(agent || null, task || null, selected?.zone);
    renderFleet(next);
    renderTimeline(next);
    updateMissionOptions(next);
    if (!scene || !next.available) return;
    const codex = agentObjects.get('CODEX')?.avatar;
    const wanted = new Set();
    for (const item of filteredTasks(next)) {
      if (!item.owner || item.owner === 'CODEX') continue;
      const worker = agentObjects.get(item.owner)?.avatar;
      if (!codex || !worker) continue;
      wanted.add(item.id);
      const signature = `${item.state}|${item.owner}|${missionFilter}`;
      const existing = taskLines.get(item.id);
      if (existing?.signature === signature) continue;
      if (existing) { scene.remove(existing.line); existing.line.geometry.dispose(); existing.line.material.dispose(); }
      const points = [new THREE.Vector3(codex.position.x, 0.22, codex.position.z), new THREE.Vector3((codex.position.x + worker.position.x) / 2, 0.22, -3.4), new THREE.Vector3(worker.position.x, 0.22, worker.position.z)];
      const geometry = new THREE.BufferGeometry().setFromPoints(points);
      const color = STATUS_COLOR[item.state] || palette.muted;
      const material = new THREE.LineDashedMaterial({ color, dashSize: item.state === 'BLOCKED' ? 0.18 : 0.3, gapSize: 0.16, transparent: true, opacity: 0.82 });
      const line = new THREE.Line(geometry, material); line.computeLineDistances();
      line.userData.detail = { kind: 'task', id: item.id }; line.userData.taskId = item.id;
      scene.add(line); taskLines.set(item.id, { line, signature });
    }
    for (const [id, record] of taskLines) if (!wanted.has(id)) { scene.remove(record.line); record.line.geometry.dispose(); record.line.material.dispose(); taskLines.delete(id); }
    for (const [id, record] of agentObjects) {
      const agent = next.agents.find((item) => item.id === id);
      if (agent && id !== 'CODEX' && id !== 'ANTI-01' && id !== 'ANTI-02') continue;
      if (agent && record.desk) {
        const active = agent.teamwork === 'TEAMWORK_ACTIVE' && agent.evidenceClass === 'VERIFIED';
        const offsetX = active ? 0 : -1.55;
        record.avatar.position.set(record.desk.group.position.x + offsetX, 0, record.desk.group.position.z + 2.0);
        record.badge.position.set(record.avatar.position.x, 1.95, record.avatar.position.z);
        const map = record.badge.material.map;
        map?.dispose(); record.badge.material.map = textTexture(agent.id, `${agent.teamwork} · ${agent.evidenceClass}`); record.badge.material.needsUpdate = true;
      }
      if (!record.desk?.screen) continue;
      const owned = filteredTasks(next).filter((item) => item.owner === id);
      const color = owned.length ? (STATUS_COLOR[owned[0].state] || palette.muted) : palette.muted;
      record.desk.screen.color.setHex(color); record.desk.screen.emissive.setHex(color);
      record.desk.screen.emissiveIntensity = owned.length ? 0.2 : 0.07;
    }
    dirty = true;
  }
  function renderInspector(agent, task, zone) {
    const title = root.querySelector('#aw-selected-title'); const detail = root.querySelector('#aw-detail'); const evidence = root.querySelector('#aw-evidence-class');
    if (!title || !detail || !evidence) return;
    if (zone) { title.textContent = zone.title || zone.id; detail.textContent = zoneDetailText(zone); evidence.textContent = 'CONTROLLER VIEW'; }
    else if (agent) { title.textContent = agent.id; detail.textContent = detailText(agent, null); evidence.textContent = agent.evidenceClass; }
    else if (task) { title.textContent = task.id; detail.textContent = detailText(null, task); evidence.textContent = task.evidence; }
    else if (selected) { title.textContent = selected.id; detail.textContent = 'This selection no longer exists in the latest controller observation.'; evidence.textContent = 'STALE'; }
    else { title.textContent = 'Agent overview'; detail.textContent = detailText(null, null); evidence.textContent = 'UNKNOWN'; }
    root.querySelector('#aw-summary').textContent = `${currentModel.agents.filter((item) => item.teamwork === 'TEAMWORK_ACTIVE' && item.evidenceClass === 'VERIFIED').length} verified Teamwork session(s) · ${currentModel.tasks.length} registry task(s) · ${currentModel.approvals.length} approval request(s)`;
  }
  function zoneDetailText(zone) {
    const owned = currentModel.tasks.filter((task) => task.owner === zone.id);
    const pending = currentModel.tasks.filter((task) => task.state === 'AWAITING_QA' || task.state === 'FEEDBACK_REQUESTED');
    const frozen = currentModel.locks.filter((lock) => lock.state === 'FROZEN');
    const lines = [zone.title || zone.id, `Source: ${currentModel.source}`, `Last observation: ${currentModel.observedAt}`];
    if (zone.id === 'CODEX') lines.push(`Mission: ${currentModel.mission}`, `Controller mode: ${currentModel.mode}`, `Pending review records: ${pending.length}`, `Development teams configured: ANTI-01, ANTI-02 (runtime status UNKNOWN)`, `Open approval requests: ${currentModel.approvals.length}`);
    else if (zone.id === 'ANTI-01' || zone.id === 'ANTI-02') lines.push(`Team: ${zone.id}`, `MCP: ${currentModel.agents.find((item) => item.id === zone.id)?.mcp || 'UNKNOWN'}`, `Antigravity runtime: ${currentModel.agents.find((item) => item.id === zone.id)?.runtime || 'UNKNOWN'}`, `Recorded assignments: ${owned.map((item) => `${item.id} · ${item.state}`).join(', ') || 'none'}`, 'Stations: Research · Implementation · Self-QA · Git checkpoint');
    else if (zone.id === 'QA') lines.push(`Assignments awaiting QA/review: ${pending.length}`, `Recorded checkpoints: ${currentModel.tasks.filter((item) => item.checkpoint).length}`, 'Self-QA is a worker claim; independent QA evidence is shown only if recorded.');
    else if (zone.id === 'GIT') lines.push('Central branch: protected state not asserted here', `Recorded locks: ${currentModel.locks.length}`, `Approval requests: ${currentModel.approvals.length}`, 'Integration candidate/CI: UNKNOWN unless recorded.');
    else if (zone.id === 'RECOVERY') lines.push(`Frozen lock records: ${frozen.length}`, 'Process stop proof: UNKNOWN', 'Resume requires controller recovery gates.');
    lines.push('3D office geometry is illustrative; task/runtime status comes only from the data source above.');
    return lines.join('\n');
  }
  function renderFleet(next) {
    const pane = root.querySelector('#aw-fleet-pane'); if (!pane) return;
    const signature = JSON.stringify({ agents: next.agents, filter: missionFilter });
    if (pane.dataset.signature === signature) return;
    pane.dataset.signature = signature;
    pane.replaceChildren();
    const fragment = document.createDocumentFragment();
    const filtered = next.agents.map((agent) => ({ ...agent, tasks: agent.tasks.filter((task) => missionFilter === 'all' || task.mission === missionFilter || task.wave === missionFilter) }));
    for (const agent of filtered) {
      const card = document.createElement('article'); card.className = 'aw-agent-card';
      const heading = document.createElement('h3'); heading.textContent = `${agent.id} · ${agent.role}`;
      const state = document.createElement('p'); state.textContent = `MCP: ${agent.mcp} · Runtime: ${agent.runtime} · Teamwork: ${agent.teamwork} · Evidence: ${agent.evidenceClass}`;
      const taskList = document.createElement('ul');
      const owned = agent.tasks.length ? agent.tasks : [];
      for (const item of owned) { const li = document.createElement('li'); li.textContent = `${item.id} · ${item.state} · ${item.scope}`; taskList.append(li); }
      if (!owned.length) { const li = document.createElement('li'); li.textContent = 'No task assignment recorded'; taskList.append(li); }
      card.append(heading, state, taskList);
      const button = document.createElement('button'); button.type = 'button'; button.className = 'btn ghost'; button.textContent = `Inspect ${agent.id}`; button.addEventListener('click', () => select({ kind: 'agent', id: agent.id })); card.append(button); fragment.append(card);
    }
    pane.append(fragment);
  }
  function renderTimeline(next) {
    const pane = root.querySelector('#aw-timeline-list'); if (!pane) return;
    const agentFilter = root.querySelector('#aw-agent-filter')?.value || 'all';
    const agentSelect = root.querySelector('#aw-agent-filter');
    const currentAgent = agentSelect?.value || 'all';
    if (agentSelect) {
      const ids = next.agents.map((agent) => agent.id);
      const signature = ids.join('|');
      if (agentSelect.dataset.agents !== signature) {
        agentSelect.replaceChildren(new Option('All', 'all'));
        for (const id of ids) agentSelect.add(new Option(id, id));
        agentSelect.dataset.agents = signature;
        if (ids.includes(currentAgent)) agentSelect.value = currentAgent;
      }
    }
    const typeSelect = root.querySelector('#aw-type-filter');
    const types = [...new Set(next.events.map((event) => event.type).filter((event) => event !== 'UNKNOWN'))].sort();
    const previous = typeSelect?.value || 'all';
    if (typeSelect && typeSelect.dataset.types !== types.join('|')) {
      typeSelect.replaceChildren(new Option('All recorded events', 'all'));
      for (const type of types) typeSelect.add(new Option(type, type));
      typeSelect.dataset.types = types.join('|');
      if ([...typeSelect.options].some((option) => option.value === previous)) typeSelect.value = previous;
    }
    const typeFilter = typeSelect?.value || 'all';
    const waveSelect = root.querySelector('#aw-wave-filter');
    const waves = [...new Set(next.waves || [])].filter(Boolean).sort();
    const oldWave = waveSelect?.value || 'all';
    if (waveSelect && waveSelect.dataset.waves !== waves.join('|')) {
      waveSelect.replaceChildren(new Option('All recorded waves', 'all'));
      for (const wave of waves) waveSelect.add(new Option(wave, wave));
      waveSelect.dataset.waves = waves.join('|');
      if ([...waveSelect.options].some((option) => option.value === oldWave)) waveSelect.value = oldWave;
    }
    const waveFilter = waveSelect?.value || 'all';
    const after = root.querySelector('#aw-time-filter')?.value ? Date.parse(root.querySelector('#aw-time-filter').value) : 0;
    const events = next.events.filter((event) => (agentFilter === 'all' || event.actor === agentFilter) && (typeFilter === 'all' || event.type === typeFilter) && (waveFilter === 'all' || event.wave === waveFilter) && (!after || (Date.parse(event.at) || 0) >= after) && (missionFilter === 'all' || event.target === missionFilter || event.mission === missionFilter));
    const signature = JSON.stringify({ events, missionFilter, agentFilter, typeFilter, waveFilter, after });
    if (pane.dataset.signature === signature) return;
    pane.dataset.signature = signature;
    pane.replaceChildren();
    if (!events.length) { const empty = document.createElement('p'); empty.className = 'aw-empty'; empty.textContent = 'REPLAY · No matching controller events recorded.'; pane.append(empty); return; }
    for (const event of events.slice().reverse().slice(0, 100)) {
      const row = document.createElement('article'); row.className = 'aw-event';
      const type = document.createElement('b'); type.textContent = event.type;
      const summary = document.createElement('span'); summary.textContent = `${event.actor} → ${event.target}`;
      const stamp = document.createElement('time'); stamp.textContent = Number.isNaN(Date.parse(event.at)) ? 'UNKNOWN time' : new Date(event.at).toLocaleString();
      const source = document.createElement('small'); source.textContent = `${event.source} · REPLAY`;
      row.append(type, summary, stamp, source); pane.append(row);
    }
  }
  function updateMissionOptions(next) {
    const select = root.querySelector('#aw-mission'); if (!select) return;
    const missions = [...new Set(next.missions || [])].filter(Boolean).sort();
    const old = select.value || missionFilter;
    const signature = missions.join('|');
    if (select.dataset.missions === signature) return;
    select.replaceChildren(new Option('All recorded missions', 'all'));
    for (const mission of missions) select.add(new Option(mission, mission));
    select.dataset.missions = signature;
    select.value = missions.includes(old) ? old : 'all';
    missionFilter = select.value;
  }
  function filteredTasks(next) { return next.tasks.filter((task) => missionFilter === 'all' || task.mission === missionFilter || task.wave === missionFilter); }
  function select(detail) {
    selected = detail;
    if (detail.kind === 'agent') renderInspector(currentModel.agents.find((item) => item.id === detail.id), null, null);
    else if (detail.kind === 'task') renderInspector(null, currentModel.tasks.find((item) => item.id === detail.id), null);
    else if (detail.kind === 'zone') renderInspector(null, null, detail);
    dirty = true;
  }
  function onPointer(event) {
    if (!renderer || view !== 'world' || !scene) return;
    const rect = canvas.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects([...(office?.interactive || []), ...[...taskLines.values()].map((entry) => entry.line)], true);
    if (hits.length) {
      let node = hits[0].object;
      while (node && !node.userData.detail && !node.userData.agentId && !node.userData.workstation) node = node.parent;
      if (node?.userData.detail) select(node.userData.detail);
      else if (node?.userData.agentId) select({ kind: 'agent', id: node.userData.agentId });
      else if (node?.userData.workstation) select({ kind: 'agent', id: node.userData.agentId });
    }
  }
  canvas.addEventListener('click', onPointer); list.push(() => canvas.removeEventListener('click', onPointer));
  const clickHandler = (event) => {
    const button = event.target.closest('[data-camera],[data-aw-view]'); if (!button || !root.contains(button)) return;
    if (button.dataset.camera) focusCamera(button.dataset.camera);
    if (button.dataset.awView) setView(button.dataset.awView);
  };
  root.addEventListener('click', clickHandler); list.push(() => root.removeEventListener('click', clickHandler));
  const filterHandler = () => { renderTimeline(currentModel); };
  root.querySelector('#aw-agent-filter')?.addEventListener('change', filterHandler);
  root.querySelector('#aw-type-filter')?.addEventListener('change', filterHandler);
  root.querySelector('#aw-wave-filter')?.addEventListener('change', filterHandler);
  root.querySelector('#aw-time-filter')?.addEventListener('change', filterHandler);
  const missionHandler = (event) => { missionFilter = event.target.value || 'all'; syncModel(currentModel); };
  root.querySelector('#aw-mission')?.addEventListener('change', missionHandler);
  list.push(() => root.querySelector('#aw-mission')?.removeEventListener('change', missionHandler));
  list.push(() => root.querySelector('#aw-agent-filter')?.removeEventListener('change', filterHandler));
  list.push(() => root.querySelector('#aw-type-filter')?.removeEventListener('change', filterHandler));
  list.push(() => root.querySelector('#aw-wave-filter')?.removeEventListener('change', filterHandler));
  list.push(() => root.querySelector('#aw-time-filter')?.removeEventListener('change', filterHandler));

  function setView(nextView) {
    if (!['world', 'fleet', 'timeline'].includes(nextView)) return;
    view = nextView;
    // Keep the world pane visible in fallback mode so its explanation and 2D link are reachable.
    root.querySelector('#aw-world-pane').hidden = nextView !== 'world';
    root.querySelector('#aw-fleet-pane').hidden = nextView !== 'fleet';
    root.querySelector('#aw-timeline-pane').hidden = nextView !== 'timeline';
    for (const button of root.querySelectorAll('[data-aw-view]')) button.setAttribute('aria-selected', String(button.dataset.awView === nextView));
    if ((!renderer || webglLost) && nextView === 'world') setFallback('WebGL2 is unavailable. Choose the 2D Fleet view.');
    dirty = true;
  }

  function disposeScene() {
    if (!scene) return;
    renderer?.setAnimationLoop(null); controls?.dispose();
    scene.traverse((item) => {
      if (item.geometry) item.geometry.dispose();
      if (item.material) {
        const materials = Array.isArray(item.material) ? item.material : [item.material];
        for (const material of materials) {
          if (material.map) material.map.dispose();
          material.dispose();
        }
      }
    });
    renderer?.dispose(); renderer?.forceContextLoss();
    scene = null; renderer = null; controls = null; camera = null;
  }

  syncModel(currentModel);
  if (window.matchMedia?.('(max-width: 760px)').matches) setView('fleet');
  return {
    update(next) { if (disposed) return; syncModel(next); },
    dispose() { if (disposed) return; disposed = true; for (const cleanup of list) cleanup(); disposeScene(); },
    setView,
    getMissionFilter() { return missionFilter; },
  };
}

export { agentWorldMarkup, normalizeAgentWorld };
