import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { createChibiAgent, createChibiAssetPool, CHIBI_COLORS } from './chibi.js';

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
