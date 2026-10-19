import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { createChibiAgent, createChibiAssetPool, CHIBI_COLORS, setChibiHovered, triggerChibiJump, updateChibiAgent } from './chibi.js';

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

test('verified in-progress work animates while MCP-only and reported claims remain idle', () => {
  const pool = createChibiAssetPool();
  const mcpOnly = createChibiAgent('ANTI-01', 'ASSIGNED', pool, { runtimeVerified: false, workingVerified: true });
  const reported = createChibiAgent('ANTI-02', 'ASSIGNED', pool, { runtimeVerified: true, workingVerified: false });
  const working = createChibiAgent('ANTI-01', 'IN_PROGRESS', pool, { runtimeVerified: true, workingVerified: true });
  updateChibiAgent(mcpOnly, 3); updateChibiAgent(reported, 3); updateChibiAgent(working, 3);
  assert.equal(mcpOnly.userData.motionState, 'IDLE');
  assert.equal(reported.userData.motionState, 'IDLE');
  assert.equal(working.userData.motionState, 'WORKING_VERIFIED');
  assert.notEqual(working.userData.gear.rotation.z, 0);
  assert.ok(working.userData.arms.some((arm) => arm.rotation.x !== 0));
});

test('frozen avatars remain rigid with a warning and cannot be animated or selected as active work', () => {
  const avatar = createChibiAgent('ANTI-02', 'FROZEN', createChibiAssetPool(), { runtimeVerified: true, workingVerified: true });
  updateChibiAgent(avatar, 5);
  assert.equal(avatar.userData.runtimeState, 'BLOCKED');
  assert.equal(avatar.userData.exclamation.visible, true);
  assert.equal(avatar.userData.keyboard.visible, false);
  assert.equal(avatar.userData.motionState, 'IDLE');
  assert.equal(avatar.userData.arms.every((arm) => arm.rotation.x === 0), true);
  assert.equal(triggerChibiJump(avatar, 5), false);
});

test('reduced motion disables work animation while preserving accessible hover and known-state click feedback', () => {
  const avatar = createChibiAgent('CODEX', 'ASSIGNED', createChibiAssetPool(), { runtimeVerified: true, workingVerified: true });
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
