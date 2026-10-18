import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeAgentWorld, taskState } from './state.js';

test('missing or malformed cockpit data stays unavailable and empty', () => {
  assert.equal(normalizeAgentWorld({ cockpit: null }).available, false);
  assert.deepEqual(normalizeAgentWorld({ cockpit: [] }).agents.map((agent) => agent.id), ['CODEX', 'ANTI-01', 'ANTI-02']);
  assert.deepEqual(normalizeAgentWorld({ cockpit: { identity_layers: 'not-an-array' } }).tasks, []);
});

test('runtime is UNKNOWN without explicit verified Teamwork evidence', () => {
  const model = normalizeAgentWorld({ cockpit: { identity_layers: [{ id: 'ANTI-01', runtime: { teamwork: 'TEAMWORK_ACTIVE' } }] } });
  const anti = model.agents.find((agent) => agent.id === 'ANTI-01');
  assert.equal(anti.teamwork, 'UNKNOWN');
  assert.equal(anti.evidenceClass, 'UNKNOWN');
});

test('controller tasks and frozen locks are mapped without fake progress', () => {
  const model = normalizeAgentWorld({
    cockpit: { identity_layers: [{ id: 'ANTI-02' }], assignments: [{ id: 'TASK-2', owner: 'ANTI-02', state: 'FROZEN', scope: 'docs/', source: 'CONTROLLER' }] },
    snapshot: { tasks: [{ id: 'TASK-2', title: 'Recorded task', owner: 'ANTI-02', state: 'FROZEN' }], locks: [{ task_id: 'TASK-2', owner: 'ANTI-02', scope: 'docs/', state: 'FROZEN', fencing: 3 }] },
  });
  const task = model.tasks[0];
  assert.equal(task.state, 'BLOCKED');
  assert.equal(task.checkpoint, false);
  assert.equal(model.agents.find((agent) => agent.id === 'ANTI-02').tasks[0].id, 'TASK-2');
  assert.equal(model.locks[0].state, 'FROZEN');
});

test('task statuses fail closed and never fabricate accepted/in-progress', () => {
  assert.equal(taskState('whatevs'), 'UNKNOWN');
  assert.equal(taskState('FROZEN'), 'BLOCKED');
  assert.equal(taskState('SUBMITTED'), 'AWAITING_QA');
  assert.equal(taskState('CHANGES_REQUESTED'), 'FEEDBACK_REQUESTED');
});

test('display text is bounded and control characters are rejected', () => {
  const model = normalizeAgentWorld({ cockpit: { identity_layers: [{ id: '<svg>\u0001' }] } });
  assert.deepEqual(model.agents.map((agent) => agent.id), ['CODEX', 'ANTI-01', 'ANTI-02']);
});

test('controller assignments, subagent inheritance and event replay keep their source links', () => {
  const model = normalizeAgentWorld({
    cockpit: {
      source: 'CONTROLLER_METADATA_PROJECTION',
      identity_layers: [{ id: 'ANTI-01', runtime: { teamwork: 'UNKNOWN' } }],
      assignments: [{ id: 'ASG-1', owner: 'ANTI-01', state: 'SUBMITTED', base_sha: 'a'.repeat(40), checkpoint_id: 'b'.repeat(64) }],
      fleet: { nodes: [{ id: 'SUB-1', kind: 'SUBAGENT', owner: 'ANTI-01', parent: 'ASG-1', state: 'AUTHORIZED', source: 'CONTROLLER_METADATA_PROJECTION' }] },
      timeline: [{ id: 'E-1', at: '2026-10-19T00:00:00Z', actor: 'ANTI-01', action: 'CHECKPOINT', target: 'ASG-1' }],
    },
    studio: { assignments: [{ id: 'ASG-1', owner: 'ANTI-01', state: 'SUBMITTED', mission: 'M-1', wave: 'W-1', scope: ['docs/'], source: 'RUN_STUDIO' }], missions: [{ id: 'M-1' }] },
  });
  assert.equal(model.tasks.length, 1);
  assert.equal(model.tasks[0].checkpoint, true);
  assert.equal(model.tasks[0].state, 'AWAITING_QA');
  assert.equal(model.subagents[0].parent, 'ANTI-01');
  assert.equal(model.subagents[0].assignment, 'ASG-1');
  assert.equal(model.events[0].mission, 'M-1');
  assert.equal(model.events[0].wave, 'W-1');
});
