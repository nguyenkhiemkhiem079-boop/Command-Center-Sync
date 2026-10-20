import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeAgentWorld, OBSERVATION_TTL_MS, taskState } from './state.js';

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
  assert.equal(task.acceptanceState, 'NOT_ACCEPTED');
  assert.equal(task.checkpoint, false);
  assert.equal(model.agents.find((agent) => agent.id === 'ANTI-02').tasks[0].id, 'TASK-2');
  assert.equal(model.locks[0].state, 'FROZEN');
});

test('backend lifecycle transitions remain distinct from review through integration', () => {
  const transitions = [
    ['QUEUED', 'ASSIGNED'], ['TASK_ASSIGNED', 'ASSIGNED'], ['ACKNOWLEDGED', 'ACKNOWLEDGED'],
    ['DEVELOPMENT', 'IN_PROGRESS'], ['SELF_QA_READY', 'AWAITING_QA'], ['SUBMITTED', 'AWAITING_QA'],
    ['SYNC_REQUEST', 'AWAITING_CODEX_REVIEW'], ['WAITING_FOR_CODEX_REVIEW', 'AWAITING_CODEX_REVIEW'],
    ['CHANGES_REQUESTED', 'FEEDBACK_REQUESTED'], ['REWORK_REQUIRED', 'FEEDBACK_REQUESTED'],
    ['CODE_REVIEWED', 'REVIEW_PASSED'], ['PASS_CODE_REVIEW', 'REVIEW_PASSED'],
    ['PREPARE', 'INTEGRATION_PENDING'], ['VALIDATE', 'INTEGRATION_PENDING'],
    ['INTEGRATION_QA_IN_PROGRESS', 'INTEGRATION_QA'], ['INTEGRATION_QA', 'INTEGRATION_QA'],
    ['APPROVAL_PENDING', 'APPROVAL_PENDING'], ['ACCEPTED', 'ACCEPTED'], ['INTEGRATED', 'INTEGRATED'],
    ['FROZEN', 'BLOCKED'], ['UNKNOWN', 'UNKNOWN'], ['future-state', 'UNKNOWN'],
  ];
  for (const [source, expected] of transitions) assert.equal(taskState(source), expected, source);
});

test('review pass exposes integration pending, approval pending and acceptance as separate gates', () => {
  const now = Date.parse('2026-10-19T12:00:00Z');
  const at = new Date(now).toISOString();
  const model = normalizeAgentWorld({
    now,
    cockpit: {
      last_verified_at: at,
      assignments: [
        { id: 'REVIEW', owner: 'ANTI-01', state: 'CODE_REVIEWED', last_verified_at: at },
        { id: 'INTEGRATE', owner: 'ANTI-02', state: 'INTEGRATION_QA', last_verified_at: at },
        { id: 'APPROVE', owner: 'ANTI-01', state: 'APPROVAL_PENDING', last_verified_at: at },
        { id: 'ACCEPT', owner: 'ANTI-02', state: 'ACCEPTED', last_verified_at: at },
      ],
    },
  });
  const task = (id) => model.tasks.find((entry) => entry.id === id);
  assert.equal(task('REVIEW').state, 'REVIEW_PASSED');
  assert.equal(task('REVIEW').reviewState, 'PASSED');
  assert.equal(task('REVIEW').integrationState, 'INTEGRATION_PENDING');
  assert.equal(task('REVIEW').acceptanceState, 'NOT_ACCEPTED');
  assert.equal(task('INTEGRATE').state, 'INTEGRATION_QA');
  assert.equal(task('APPROVE').state, 'APPROVAL_PENDING');
  assert.equal(task('APPROVE').approvalState, 'PENDING');
  assert.equal(task('APPROVE').acceptanceState, 'NOT_ACCEPTED');
  assert.equal(task('ACCEPT').state, 'ACCEPTED');
  assert.equal(task('ACCEPT').acceptanceState, 'ACCEPTED');
  assert.notEqual(task('REVIEW').state, 'ACCEPTED');
});

test('stale controller observations fail closed while preserving FROZEN ownership', () => {
  const now = Date.parse('2026-10-19T12:00:00Z');
  const staleAt = new Date(now - OBSERVATION_TTL_MS - 1).toISOString();
  const model = normalizeAgentWorld({
    now,
    cockpit: {
      last_verified_at: staleAt,
      identity_layers: [{ id: 'ANTI-01', mcp: { contact: 'CONNECTED' }, runtime: { session: 'SESSION_VERIFIED', teamwork: 'TEAMWORK_ACTIVE', verification: 'VERIFIED' } }],
      assignments: [
        { id: 'OLD-RUN', owner: 'ANTI-01', state: 'RUNNING', last_verified_at: staleAt },
        { id: 'OLD-REVIEW', owner: 'ANTI-02', state: 'CODE_REVIEWED', last_verified_at: staleAt },
        { id: 'OLD-FROZEN', owner: 'ANTI-02', state: 'FROZEN', last_verified_at: staleAt },
      ],
    },
    snapshot: { locks: [
      { task_id: 'OLD-RUN', owner: 'ANTI-01', state: 'ACTIVE', fencing: 2 },
      { task_id: 'OLD-FROZEN', owner: 'ANTI-02', state: 'FROZEN', fencing: 3 },
    ] },
  });
  assert.equal(model.observationState, 'STALE');
  assert.equal(model.tasks.find((task) => task.id === 'OLD-RUN').state, 'UNKNOWN');
  assert.equal(model.tasks.find((task) => task.id === 'OLD-REVIEW').reviewState, 'UNKNOWN');
  assert.equal(model.tasks.find((task) => task.id === 'OLD-FROZEN').state, 'BLOCKED');
  assert.equal(model.tasks.find((task) => task.id === 'OLD-RUN').freshness, 'STALE');
  assert.equal(model.locks.find((lock) => lock.task === 'OLD-RUN').state, 'UNKNOWN');
  assert.equal(model.locks.find((lock) => lock.task === 'OLD-FROZEN').state, 'FROZEN');
  const anti = model.agents.find((agent) => agent.id === 'ANTI-01');
  assert.equal(anti.mcp, 'UNKNOWN');
  assert.equal(anti.teamwork, 'UNKNOWN');
});

test('stale future-dated observations do not manufacture fresh task state', () => {
  const now = Date.parse('2026-10-19T12:00:00Z');
  const model = normalizeAgentWorld({ now, cockpit: {
    last_verified_at: new Date(now + 2 * 60 * 1000).toISOString(),
    assignments: [{ id: 'FUTURE', owner: 'ANTI-01', state: 'ACCEPTED' }],
  } });
  assert.equal(model.observationState, 'STALE');
  assert.equal(model.tasks[0].state, 'UNKNOWN');
  assert.equal(model.tasks[0].acceptanceState, 'UNKNOWN');
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
