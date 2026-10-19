import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { createChibiAgent, createChibiAssetPool, CHIBI_COLORS, isVerifiedWorking, setChibiHovered, triggerChibiJump, updateChibiAgent } from './chibi.js';

function meshes(root) {
  const result = [];
  root.traverse((object) => { if (object.isMesh) result.push(object); });
  return result;
}

test('role silhouettes are distinct and share scene-scoped geometry/material assets', () => {
  const pool = createChibiAssetPool();
  const codex = createChibiAgent('CODEX', 'UNKNOWN', pool);
  const anti01 = createChibiAgent('ANTI-01', 'ASSIGNED', pool);
  const anti02 = createChibiAgent('ANTI-02', 'BLOCKED', pool);
  const qa = createChibiAgent({ id: 'QA-01', role: 'INDEPENDENT_QA_RUNNER' }, 'UNKNOWN', pool);

  assert.equal(codex.userData.roleKind, 'CODEX');
  assert.equal(anti01.userData.roleKind, 'ANTI-01');
  assert.equal(anti02.userData.roleKind, 'ANTI-02');
  assert.equal(qa.userData.roleKind, 'QA');
  assert.ok(meshes(codex).some((object) => object.geometry.type === 'CylinderGeometry' && object.material.color.getHex() === CHIBI_COLORS.chef));
  assert.ok(meshes(anti01).some((object) => object.material.color.getHex() === CHIBI_COLORS.anti01));
  assert.ok(meshes(anti02).some((object) => object.material.color.getHex() === CHIBI_COLORS.anti02));
  assert.ok(meshes(qa).some((object) => object.geometry.type === 'TorusGeometry' && object.material.color.getHex() === CHIBI_COLORS.ink));
  assert.equal(codex.userData.head.geometry, anti01.userData.head.geometry);
  assert.equal(codex.userData.head.material, anti01.userData.head.material);
  assert.equal(pool.geometries.size < meshes(codex).length + meshes(anti01).length, true);
});

test('status ring colors follow the state legend and unknown remains neutral', () => {
  const pool = createChibiAssetPool();
  const cases = [
    ['ASSIGNED', CHIBI_COLORS.assigned], ['ACKNOWLEDGED', CHIBI_COLORS.assigned],
    ['IN_PROGRESS', CHIBI_COLORS.inProgress], ['FROZEN', CHIBI_COLORS.blocked],
    ['BLOCKED', CHIBI_COLORS.blocked], ['UNKNOWN', CHIBI_COLORS.unknown],
    ['AWAITING_QA', CHIBI_COLORS.unknown],
  ];
  for (const [state, expected] of cases) {
    const avatar = createChibiAgent('ANTI-01', state, pool);
    assert.equal(avatar.userData.ring.material.color.getHex(), expected, state);
    assert.equal(avatar.userData.visualState, state);
  }
});

test('each avatar is a separate interactive group while pooled assets stay within the scene', () => {
  const pool = createChibiAssetPool();
  const first = createChibiAgent('ANTI-01', 'UNKNOWN', pool);
  const second = createChibiAgent('ANTI-02', 'UNKNOWN', pool);
  assert.notEqual(first, second);
  assert.equal(first.userData.agentId, 'ANTI-01');
  assert.equal(second.userData.agentId, 'ANTI-02');
  assert.ok(first.userData.ring.isMesh);
  assert.ok(first.userData.head.isMesh);
  assert.ok(first.userData.eyes.every((eye) => eye.isMesh));
  assert.ok(first.userData.arms.every((arm) => arm.isGroup));
  assert.ok(pool.THREE === THREE);
});

test('unknown runtime stays neutral and never performs verified work animation', () => {
  const avatar = createChibiAgent('ANTI-01', 'ASSIGNED', createChibiAssetPool());
  updateChibiAgent(avatar, 12);
  assert.equal(avatar.userData.runtimeState, 'UNKNOWN');
  assert.equal(avatar.userData.marker.visible, true);
  assert.equal(avatar.userData.keyboard.visible, false);
  assert.equal(avatar.userData.motionState, 'IDLE');
  assert.equal(avatar.userData.arms.every((arm) => arm.rotation.x === 0), true);
  assert.equal(triggerChibiJump(avatar, 12), true);
  updateChibiAgent(avatar, 12.16);
  assert.ok(avatar.position.y > 0.2, 'selection feedback is allowed without implying work activity');
  assert.equal(avatar.userData.keyboard.visible, false);
});

const verifiedRunning = (overrides = {}) => ({
  runtime: 'RUNNING_VERIFIED', evidenceClass: 'VERIFIED',
  tasks: [{ state: 'IN_PROGRESS', freshness: 'FRESH', evidence: 'CONTROLLER_RUNTIME_EVENT' }],
  ...overrides,
});

test('work animation gate accepts only RUNNING_VERIFIED with fresh controller evidence', () => {
  const invalid = [
    ['ASSIGNED', { runtime: 'ASSIGNED' }],
    ['LAUNCH_REQUESTED', { runtime: 'LAUNCH_REQUESTED' }],
    ['UNKNOWN', { runtime: 'UNKNOWN' }],
    ['NOT_VERIFIED', { runtime: 'TEAMWORK_ACTIVE', evidenceClass: 'AGENT_REPORTED' }],
    ['FROZEN', { tasks: [{ state: 'FROZEN', freshness: 'FRESH', evidence: 'CONTROLLER_RUNTIME_EVENT' }] }],
    ['BLOCKED', { tasks: [{ state: 'BLOCKED', freshness: 'FRESH', evidence: 'CONTROLLER_RUNTIME_EVENT' }] }],
    ['missing runtime', { runtime: undefined }],
    ['missing evidence class', { evidenceClass: undefined }],
    ['missing task fields', { tasks: [{}] }],
    ['missing task collection', { tasks: undefined }],
    ['stale observation', { tasks: [{ state: 'IN_PROGRESS', freshness: 'STALE', evidence: 'CONTROLLER_RUNTIME_EVENT' }] }],
    ['unknown freshness', { tasks: [{ state: 'IN_PROGRESS', freshness: 'UNKNOWN', evidence: 'CONTROLLER_RUNTIME_EVENT' }] }],
    ['registry-only in progress', { tasks: [{ state: 'IN_PROGRESS', freshness: 'FRESH', evidence: 'REGISTRY_RECORD' }] }],
  ];
  for (const [label, patch] of invalid) assert.equal(isVerifiedWorking(verifiedRunning(patch)), false, label);
  assert.equal(isVerifiedWorking(verifiedRunning()), true);
});

test('assignment, launch, unknown and unverified states remain idle; unknown uses question mark', () => {
  const pool = createChibiAssetPool();
  const cases = [
    ['ASSIGNED', { runtime: 'UNKNOWN', evidenceClass: 'UNKNOWN' }, false],
    ['LAUNCH_REQUESTED', { runtime: 'TEAMWORK_ACTIVE', evidenceClass: 'VERIFIED' }, true],
    ['UNKNOWN', { runtime: 'UNKNOWN', evidenceClass: 'UNKNOWN' }, false],
    ['NOT_VERIFIED', { runtime: 'TEAMWORK_ACTIVE', evidenceClass: 'AGENT_REPORTED' }, false],
    ['STALE', verifiedRunning({ tasks: [{ state: 'IN_PROGRESS', freshness: 'STALE', evidence: 'CONTROLLER_RUNTIME_EVENT' }] }), true],
  ];
  for (const [state, agent, runtimeVerified] of cases) {
    const avatar = createChibiAgent('ANTI-01', state, pool, { runtimeVerified, agent: { ...agent, tasks: agent.tasks || [{ state, freshness: 'FRESH', evidence: 'CONTROLLER_RUNTIME_EVENT' }] } });
    updateChibiAgent(avatar, 3);
    assert.equal(avatar.userData.motionState, 'IDLE', state);
    assert.equal(avatar.userData.keyboard.visible, false, state);
    assert.equal(avatar.userData.gear.visible, false, state);
    if (state === 'UNKNOWN' || state === 'ASSIGNED' || state === 'NOT_VERIFIED') assert.equal(avatar.userData.marker.visible, true, state);
  }
});

test('only fresh RUNNING_VERIFIED controller evidence animates; stale evidence stays idle', () => {
  const pool = createChibiAssetPool();
  const stale = createChibiAgent('ANTI-02', 'IN_PROGRESS', pool, { runtimeVerified: true, agent: verifiedRunning({ tasks: [{ state: 'IN_PROGRESS', freshness: 'STALE', evidence: 'CONTROLLER_RUNTIME_EVENT' }] }) });
  const working = createChibiAgent('ANTI-01', 'IN_PROGRESS', pool, { runtimeVerified: true, agent: verifiedRunning() });
  updateChibiAgent(stale, 3); updateChibiAgent(working, 3);
  assert.equal(stale.userData.motionState, 'IDLE');
  assert.equal(stale.userData.keyboard.visible, false);
  assert.equal(working.userData.motionState, 'WORKING_VERIFIED');
  assert.equal(working.userData.keyboard.visible, true);
  assert.notEqual(working.userData.gear.rotation.z, 0);
  assert.ok(working.userData.arms.some((arm) => arm.rotation.x !== 0));
});

test('frozen and blocked avatars remain rigid with a warning and cannot be animated', () => {
  for (const state of ['FROZEN', 'BLOCKED']) {
    const avatar = createChibiAgent('ANTI-02', state, createChibiAssetPool(), { runtimeVerified: true, agent: verifiedRunning() });
    updateChibiAgent(avatar, 5);
    assert.equal(avatar.userData.runtimeState, 'BLOCKED');
    assert.equal(avatar.userData.exclamation.visible, true);
    assert.equal(avatar.userData.marker.visible, false);
    assert.equal(avatar.userData.keyboard.visible, false);
    assert.equal(avatar.userData.motionState, 'BLOCKED');
    assert.equal(avatar.userData.arms.every((arm) => arm.rotation.x === 0), true);
    assert.equal(triggerChibiJump(avatar, 5), false);
  }
});

test('a verified worker that becomes frozen stops its work indicators immediately', () => {
  const avatar = createChibiAgent('ANTI-01', 'IN_PROGRESS', createChibiAssetPool(), { runtimeVerified: true, agent: verifiedRunning() });
  updateChibiAgent(avatar, 9);
  assert.equal(avatar.userData.motionState, 'WORKING_VERIFIED');
  avatar.userData.runtimeState = 'BLOCKED';
  avatar.userData.exclamation.visible = true;
  avatar.userData.keyboard.visible = false;
  avatar.userData.gear.visible = false;
  updateChibiAgent(avatar, 9.1);
  assert.equal(avatar.userData.motionState, 'BLOCKED');
  assert.equal(avatar.userData.gear.rotation.z, 0);
  assert.equal(avatar.userData.arms.every((arm) => arm.rotation.x === 0), true);
  assert.equal(avatar.userData.exclamation.visible, true);
});

test('reduced motion disables work animation while preserving accessible hover and known-state click feedback', () => {
  const avatar = createChibiAgent('CODEX', 'ASSIGNED', createChibiAssetPool(), { runtimeVerified: true, agent: verifiedRunning() });
  updateChibiAgent(avatar, 6, true);
  assert.equal(avatar.userData.motionState, 'IDLE');
  assert.equal(avatar.userData.gear.rotation.z, 0);
  assert.equal(triggerChibiJump(avatar, 6), true);
  setChibiHovered(avatar, true);
  assert.equal(avatar.userData.hoverHalo.visible, true);
  assert.equal(avatar.scale.x, 1.1);
  setChibiHovered(avatar, false);
  assert.equal(avatar.userData.hoverHalo.visible, false);
  assert.equal(avatar.scale.x, 1);
});

test('polish uses pooled three-band toon shading, thin outline shells and contact shadows', () => {
  const pool = createChibiAssetPool();
  const first = createChibiAgent('CODEX', 'UNKNOWN', pool);
  const second = createChibiAgent('ANTI-01', 'ASSIGNED', pool);
  assert.ok(first.userData.head.material.isMeshToonMaterial);
  assert.equal(first.userData.head.material.gradientMap, second.userData.head.material.gradientMap);
  assert.equal(pool.textures.size, 1);
  assert.equal(first.userData.contactShadow.geometry.type, 'CircleGeometry');
  assert.ok(meshes(first).some((object) => object.userData.chibiOutlineShell));
  assert.equal(pool.geometries.get('contact-shadow'), second.userData.contactShadow.geometry);
});
