import * as THREE from 'three';

const COLORS = Object.freeze({
  ink: 0x18253a,
  skin: 0xffd5ad,
  cheek: 0xf08c93,
  chef: 0xf8fbff,
  codex: 0x9c88ff,
  anti01: 0xf3bd45,
  anti02: 0xff925b,
  coat: 0xf5f8fc,
  coatShade: 0xbac9dc,
  goggles: 0x79dce8,
  assigned: 0x5ca3ff,
  inProgress: 0x66dbac,
  blocked: 0xff6673,
  unknown: 0x8097b4,
});

export function createChibiAssetPool(THREEApi = THREE) {
  return { THREE: THREEApi, geometries: new Map(), materials: new Map() };
}

const geometry = (pool, key, create) => {
  if (!pool.geometries.has(key)) pool.geometries.set(key, create());
  return pool.geometries.get(key);
};
const material = (pool, key, color, options = {}) => {
  if (!pool.materials.has(key)) pool.materials.set(key, new pool.THREE.MeshStandardMaterial({ color, roughness: 0.8, ...options }));
  return pool.materials.get(key);
};
const mesh = (pool, parent, geom, mat, position, scale = [1, 1, 1]) => {
  const result = new pool.THREE.Mesh(geom, mat);
  result.position.set(...position); result.scale.set(...scale); result.castShadow = true;
  parent.add(result); return result;
};

function roleKind(role) {
  const value = String(typeof role === 'string' ? role : `${role?.id || ''} ${role?.role || ''}`).toUpperCase();
  if (value.includes('CODEX')) return 'CODEX';
  if (value.includes('ANTI-01')) return 'ANTI-01';
  if (value.includes('ANTI-02')) return 'ANTI-02';
  if (value.includes('QA') || value.includes('QUALITY')) return 'QA';
  return 'SUBAGENT';
}

function ringColor(state) {
  const value = String(state || 'UNKNOWN').toUpperCase();
  if (['ASSIGNED', 'ACKNOWLEDGED', 'TASK_ASSIGNED'].includes(value)) return COLORS.assigned;
  if (value === 'IN_PROGRESS') return COLORS.inProgress;
  if (['FROZEN', 'BLOCKED'].includes(value)) return COLORS.blocked;
  return COLORS.unknown;
}

function addChefHat(pool, group) {
  const { THREE: T } = pool;
  const white = material(pool, 'chef-white', COLORS.chef);
  mesh(pool, group, geometry(pool, 'chef-band', () => new T.CylinderGeometry(0.34, 0.34, 0.12, 10)), white, [0, 2.0, 0]);
  mesh(pool, group, geometry(pool, 'chef-crown', () => new T.CylinderGeometry(0.27, 0.31, 0.25, 10)), white, [0, 2.16, 0]);
  const puff = geometry(pool, 'chef-puff', () => new T.SphereGeometry(0.2, 8, 6));
  for (const [x, y, z, scale] of [[-0.17, 2.27, 0, [1, 0.86, 1]], [0, 2.34, 0, [1.03, 1, 1]], [0.17, 2.27, 0, [1, 0.86, 1]]]) {
    mesh(pool, group, puff, white, [x, y, z], scale);
  }
}

function addHelmet(pool, group, color, prefix) {
  const { THREE: T } = pool;
  const helmet = material(pool, `${prefix}-helmet`, color);
  const brim = geometry(pool, 'helmet-brim', () => new T.CylinderGeometry(0.52, 0.52, 0.095, 12));
  mesh(pool, group, brim, helmet, [0, 1.98, 0]);
  const dome = geometry(pool, 'helmet-dome', () => new T.SphereGeometry(0.43, 12, 7, 0, Math.PI * 2, 0, Math.PI / 2));
  mesh(pool, group, dome, helmet, [0, 2.01, 0], [1, 0.92, 0.92]);
  const strap = material(pool, 'helmet-strap', COLORS.ink);
  mesh(pool, group, geometry(pool, 'helmet-strap-geometry', () => new T.BoxGeometry(0.035, 0.23, 0.54)), strap, [0, 1.81, 0.19]);
}

function addQaGoggles(pool, group) {
  const { THREE: T } = pool;
  const frame = material(pool, 'qa-goggle-frame', COLORS.ink);
  const lens = material(pool, 'qa-goggle-lens', COLORS.goggles, { metalness: 0.12, roughness: 0.3 });
  const ring = geometry(pool, 'qa-goggle-ring', () => new T.TorusGeometry(0.13, 0.035, 6, 12));
  for (const x of [-0.16, 0.16]) {
    mesh(pool, group, geometry(pool, 'qa-goggle-lens-disc', () => new T.CircleGeometry(0.105, 12)), lens, [x, 1.52, 0.508]);
    mesh(pool, group, ring, frame, [x, 1.52, 0.52]);
  }
  mesh(pool, group, geometry(pool, 'qa-goggle-bridge', () => new T.BoxGeometry(0.12, 0.035, 0.035)), frame, [0, 1.52, 0.52]);
}

export function createChibiAgent(role, state = 'UNKNOWN', pool = createChibiAssetPool()) {
  const { THREE: T } = pool;
  const kind = roleKind(role);
  const id = typeof role === 'string' ? role : String(role?.id || kind);
  const group = new T.Group();
  group.name = `chibi-${id}`;
  const outfitColor = kind === 'CODEX' ? COLORS.codex : kind === 'QA' ? COLORS.coat : kind === 'ANTI-01' ? 0x48aab7 : kind === 'ANTI-02' ? 0x5b87c6 : 0x6a7790;
  const clothes = material(pool, `outfit-${kind}`, outfitColor);
  const skin = material(pool, 'skin', COLORS.skin, { roughness: 0.9 });
  const dark = material(pool, 'dark', COLORS.ink);
  const black = material(pool, 'eye-black', 0x101827, { roughness: 0.35 });
  const white = material(pool, 'eye-highlight', 0xffffff, { roughness: 0.25 });
  const blush = material(pool, 'cheek', COLORS.cheek, { roughness: 0.85 });
  const sphere = geometry(pool, 'sphere-lowpoly', () => new T.SphereGeometry(1, 12, 8));

  for (const x of [-0.16, 0.16]) {
    mesh(pool, group, geometry(pool, 'boot', () => new T.SphereGeometry(0.18, 8, 6)), dark, [x, 0.16, 0.04], [1, 0.76, 1.25]);
    mesh(pool, group, geometry(pool, 'leg', () => new T.CapsuleGeometry(0.13, 0.17, 3, 8)), clothes, [x, 0.38, 0]);
  }
  const torso = mesh(pool, group, sphere, clothes, [0, 0.72, 0], [0.4, 0.39, 0.31]);
  torso.userData.chibiPart = 'torso';
  if (kind === 'QA') {
    const coat = material(pool, 'qa-coat', COLORS.coat);
    mesh(pool, group, sphere, coat, [0, 0.75, 0.09], [0.43, 0.39, 0.27]);
    mesh(pool, group, geometry(pool, 'qa-coat-button', () => new T.SphereGeometry(0.035, 6, 4)), material(pool, 'qa-coat-shade', COLORS.coatShade), [0, 0.76, 0.365]);
  }
  const armGeometry = geometry(pool, 'arm', () => new T.CapsuleGeometry(0.12, 0.22, 3, 8));
  const arms = [];
  for (const side of [-1, 1]) {
    const pivot = new T.Group(); pivot.position.set(side * 0.34, 0.88, 0.02); group.add(pivot);
    mesh(pool, pivot, armGeometry, clothes, [side * 0.1, -0.08, 0.02], [1, 1.05, 1]);
    mesh(pool, pivot, sphere, skin, [side * 0.11, -0.22, 0.1], [0.14, 0.13, 0.13]);
    arms.push(pivot);
  }

  const head = mesh(pool, group, sphere, skin, [0, 1.47, 0], [0.59, 0.58, 0.53]);
  head.userData.chibiPart = 'head';
  const eyes = [];
  for (const x of [-0.19, 0.19]) {
    const eye = mesh(pool, group, geometry(pool, 'eye', () => new T.SphereGeometry(0.092, 8, 6)), black, [x, 1.53, 0.48], [1, 1.08, 0.55]);
    mesh(pool, group, geometry(pool, 'eye-highlight', () => new T.SphereGeometry(0.027, 6, 4)), white, [x - 0.026, 1.559, 0.527]);
    eyes.push(eye);
  }
  mesh(pool, group, geometry(pool, 'nose', () => new T.SphereGeometry(0.055, 7, 5)), skin, [0, 1.39, 0.523], [1, 0.8, 0.7]);
  for (const x of [-0.34, 0.34]) mesh(pool, group, geometry(pool, 'cheek', () => new T.SphereGeometry(0.075, 7, 5)), blush, [x, 1.34, 0.412], [1.15, 0.72, 0.45]);
  mesh(pool, group, geometry(pool, 'mouth', () => new T.SphereGeometry(0.065, 8, 4)), dark, [0, 1.245, 0.501], [1, 0.32, 0.3]);

  if (kind === 'CODEX') addChefHat(pool, group);
  else if (kind === 'ANTI-01') addHelmet(pool, group, COLORS.anti01, 'anti01');
  else if (kind === 'ANTI-02') addHelmet(pool, group, COLORS.anti02, 'anti02');
  else if (kind === 'QA') addQaGoggles(pool, group);

  const ringMaterial = material(pool, `ring-${state}`, ringColor(state), { roughness: 0.45, metalness: 0.05, emissive: ringColor(state), emissiveIntensity: 0.2 });
  const ring = mesh(pool, group, geometry(pool, 'state-ring', () => new T.RingGeometry(0.49, 0.55, 28)), ringMaterial, [0, 0.045, 0]);
  ring.rotation.x = -Math.PI / 2;
  group.userData.agentId = id;
  group.userData.roleKind = kind;
  group.userData.visualState = String(state || 'UNKNOWN').toUpperCase();
  group.userData.head = head;
  group.userData.eyes = eyes;
  group.userData.arms = arms;
  group.userData.ring = ring;
  group.userData.workIndicators = [];
  group.userData.pool = pool;
  group.userData.motionState = 'IDLE';
  return group;
}

export { COLORS as CHIBI_COLORS, ringColor as chibiRingColor };
