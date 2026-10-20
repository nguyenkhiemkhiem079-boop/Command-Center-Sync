const UNKNOWN = 'UNKNOWN';
// Cockpit is polled every few seconds. Older snapshots must not keep presenting
// ephemeral task/session states as current after the controller stops responding.
export const OBSERVATION_TTL_MS = 5 * 60 * 1000;
const FUTURE_CLOCK_SKEW_MS = 60 * 1000;
const safeText = (value, fallback = UNKNOWN) => {
  if (typeof value !== 'string') return fallback;
  const text = value.trim();
  return text && text.length <= 240 && !/[\u0000-\u001f]/.test(text) ? text : fallback;
};
const rows = (value) => Array.isArray(value) ? value.filter((row) => row && typeof row === 'object' && !Array.isArray(row)) : [];
const rawState = (value) => safeText(value).toUpperCase();

export function taskState(value) {
  const state = rawState(value);
  if (state === 'FROZEN' || state === 'BLOCKED') return 'BLOCKED';
  if (['SUBMITTED', 'SELF_QA_READY', 'QA_PENDING'].includes(state)) return 'AWAITING_QA';
  if (['SYNC_REQUEST', 'WAITING_FOR_CODEX_REVIEW'].includes(state)) return 'AWAITING_CODEX_REVIEW';
  if (['CHANGES_REQUESTED', 'REWORK_REQUIRED'].includes(state)) return 'FEEDBACK_REQUESTED';
  if (['CODE_REVIEWED', 'PASS_CODE_REVIEW'].includes(state)) return 'REVIEW_PASSED';
  if (['PREPARE', 'PREPARED', 'VALIDATE', 'VALIDATED', 'INTEGRATION_PENDING'].includes(state)) return 'INTEGRATION_PENDING';
  if (['INTEGRATION_QA', 'INTEGRATION_QA_IN_PROGRESS'].includes(state)) return 'INTEGRATION_QA';
  if (['APPROVAL_PENDING', 'CHILDREN_ACCEPTED_APPROVAL_PENDING'].includes(state)) return 'APPROVAL_PENDING';
  if (['INTEGRATED', 'COMMITTED', 'COMPLETE'].includes(state)) return 'INTEGRATED';
  if (state === 'ACCEPTED') return 'ACCEPTED';
  if (['RUNNING', 'IN_PROGRESS', 'DEVELOPMENT', 'SELF_QA'].includes(state)) return 'IN_PROGRESS';
  if (['ACKNOWLEDGED', 'ACK', 'TASK_ACKNOWLEDGED'].includes(state)) return 'ACKNOWLEDGED';
  if (['QUEUED', 'ASSIGNED', 'TASK_ASSIGNED'].includes(state)) return 'ASSIGNED';
  return UNKNOWN;
}

function lifecycle(value) {
  const source = rawState(value);
  const state = taskState(value);
  return {
    state,
    reviewState: state === 'REVIEW_PASSED' ? 'PASSED' : UNKNOWN,
    integrationState: state === 'REVIEW_PASSED' ? 'INTEGRATION_PENDING'
      : state === 'INTEGRATION_PENDING' ? 'PENDING'
        : state === 'INTEGRATION_QA' ? 'IN_PROGRESS'
          : state === 'APPROVAL_PENDING' ? 'QA_PASSED' : state === 'INTEGRATED' ? 'COMPLETE' : UNKNOWN,
    approvalState: state === 'APPROVAL_PENDING' ? 'PENDING' : UNKNOWN,
    acceptanceState: ['ACCEPTED', 'INTEGRATED'].includes(state) ? 'ACCEPTED' : 'NOT_ACCEPTED',
    sourceState: source,
  };
}

function observationAge(timestamp, now) {
  if (typeof timestamp !== 'string' || !timestamp.trim()) return { state: 'UNKNOWN', ageMs: null };
  const parsed = Date.parse(timestamp);
  if (!Number.isFinite(parsed)) return { state: 'UNKNOWN', ageMs: null };
  const ageMs = now - parsed;
  if (ageMs < -FUTURE_CLOCK_SKEW_MS || ageMs > OBSERVATION_TTL_MS) return { state: 'STALE', ageMs };
  return { state: 'FRESH', ageMs: Math.max(0, ageMs) };
}

function visibleLifecycle(value, stale) {
  const result = lifecycle(value);
  if (!stale) return result;
  // Preserve a recorded freeze as a safety hold; other stale states cannot be
  // treated as current evidence or progress.
  if (result.state === 'BLOCKED' && result.sourceState === 'FROZEN') return result;
  return { state: UNKNOWN, reviewState: UNKNOWN, integrationState: UNKNOWN, approvalState: UNKNOWN,
    acceptanceState: 'UNKNOWN', sourceState: result.sourceState };
}

export function normalizeAgentWorld({ cockpit, snapshot, studio, cockpitError = null, observedAt = null, now = Date.now() } = {}) {
  const cockpitAvailable = Boolean(cockpit && typeof cockpit === 'object' && !Array.isArray(cockpit));
  const projectionAt = safeText(cockpit?.last_verified_at ?? observedAt);
  const observation = observationAge(projectionAt, now);
  const stale = observation.state === 'STALE';
  const legacyTasks = rows(snapshot?.tasks);
  const studioAssignments = rows(studio?.assignments);
  const assignmentMap = new Map();
  for (const item of [...studioAssignments, ...rows(cockpit?.assignments)]) {
    const id = safeText(item.id);
    if (id === UNKNOWN) continue;
    assignmentMap.set(id, { ...(assignmentMap.get(id) || {}), ...item });
  }
  const controllerAssignments = [...assignmentMap.values()];
  const assignmentById = new Map(controllerAssignments.map((item) => [safeText(item.id), item]));
  const tasks = legacyTasks.map((item) => {
    const id = safeText(item.id);
    const assignment = assignmentById.get(id);
    const source = assignment?.state ?? item.state;
    const stateAge = observationAge(assignment?.last_verified_at ?? item.last_verified_at ?? projectionAt, now);
    const stateStale = stale || stateAge.state === 'STALE';
    const status = visibleLifecycle(source, stateStale);
    return {
      id,
      title: safeText(item.title, id),
      owner: safeText(item.owner),
      ...status,
      wave: safeText(item.wave_id ?? item.wave ?? assignment?.wave),
      mission: safeText(assignment?.mission ?? item.mission_id),
      scope: safeText(assignment?.scope ?? item.scope),
      baseSha: safeText(assignment?.base_sha ?? item.base_sha),
      checkpoint: Boolean(assignment?.checkpoint_id || item.checkpoint || item.checkpoint_at),
      evidence: assignment?.source || item.source || 'REGISTRY_RECORD',
      freshness: stateStale ? 'STALE' : (observation.state === 'FRESH' || stateAge.state === 'FRESH' ? 'FRESH' : 'UNKNOWN'),
      lastObservedAt: safeText(assignment?.last_verified_at ?? item.last_verified_at ?? projectionAt),
    };
  });
  for (const item of controllerAssignments) {
    const id = safeText(item.id);
    if (tasks.some((task) => task.id === id)) continue;
    const source = item.state;
    const stateAge = observationAge(item.last_verified_at ?? projectionAt, now);
    const stateStale = stale || stateAge.state === 'STALE';
    tasks.push({
      id, title: safeText(item.title, id), owner: safeText(item.owner), ...visibleLifecycle(source, stateStale),
      wave: safeText(item.wave), mission: safeText(item.mission), scope: safeText(item.scope ?? item.allowed), baseSha: safeText(item.base_sha),
      checkpoint: Boolean(item.checkpoint_id), evidence: safeText(item.source, 'CONTROLLER_RECORD'),
      freshness: stateStale ? 'STALE' : (observation.state === 'FRESH' || stateAge.state === 'FRESH' ? 'FRESH' : 'UNKNOWN'),
      lastObservedAt: safeText(item.last_verified_at ?? projectionAt),
    });
  }

  const identityRecords = rows(cockpit?.identity_layers);
  const roles = ['CODEX', 'ANTI-01', 'ANTI-02'];
  const agents = roles.map((id) => {
    const record = identityRecords.find((entry) => safeText(entry.id) === id);
    const assigned = tasks.filter((task) => task.owner === id);
    const runtime = record?.runtime && typeof record.runtime === 'object' ? record.runtime : {};
    const teamwork = safeText(runtime.teamwork);
    const verification = safeText(runtime.verification ?? runtime.evidence_class);
    const verifiedTeamwork = !stale && teamwork === 'TEAMWORK_ACTIVE' && verification === 'VERIFIED';
    return {
      id,
      role: id === 'CODEX' ? 'SUPERVISOR' : 'DEVELOPMENT TEAM',
      mcp: stale ? UNKNOWN : safeText(record?.mcp?.contact),
      runtime: stale ? UNKNOWN : (verifiedTeamwork ? 'TEAMWORK_ACTIVE' : safeText(runtime.session)),
      teamwork: verifiedTeamwork ? 'TEAMWORK_ACTIVE' : UNKNOWN,
      evidenceClass: verifiedTeamwork ? 'VERIFIED' : (!stale && verification === 'AGENT_REPORTED' ? 'AGENT_REPORTED' : 'UNKNOWN'),
      source: safeText(record?.source ?? record?.runtime?.source, record ? 'NO_RUNTIME_ATTESTATION' : 'ROLE_CONFIGURED_RUNTIME_UNKNOWN'),
      lastObservedAt: safeText(record?.runtime?.last_verified_at ?? record?.last_verified_at ?? projectionAt),
      tasks: assigned,
      ownership: assigned.map((task) => ({ task: task.id, scope: task.scope, state: task.state })),
    };
  });
  const subagents = rows(cockpit?.fleet?.nodes).filter((node) => node.kind === 'SUBAGENT').map((node) => ({
    id: safeText(node.id), parent: safeText(node.owner), assignment: safeText(node.parent), role: 'SUBAGENT', mcp: UNKNOWN,
    runtime: UNKNOWN, teamwork: UNKNOWN, evidenceClass: 'UNKNOWN',
    source: safeText(node.source, 'CONTROLLER_METADATA_PROJECTION'),
    lastObservedAt: safeText(node.last_verified_at ?? projectionAt),
    tasks: tasks.filter((task) => task.owner === safeText(node.id)),
    ownership: [{ task: safeText(node.parent), scope: 'INHERITED_FROM_PARENT', state: stale ? UNKNOWN : safeText(node.state) }],
  })).filter((agent) => agent.id !== UNKNOWN && !roles.includes(agent.id));
  agents.push(...subagents);

  const events = rows(cockpit?.timeline).map((event, index) => {
    const target = safeText(event.target);
    const relatedTask = tasks.find((item) => item.id === target);
    return {
      id: safeText(event.id, `event-${index}`), at: safeText(event.at), actor: safeText(event.actor), type: safeText(event.action), target,
      mission: safeText(event.mission ?? relatedTask?.mission), wave: safeText(event.wave ?? relatedTask?.wave),
      summary: safeText(event.summary, 'Controller event recorded; payload omitted'),
      source: safeText(event.source, cockpit?.source || 'CONTROLLER_METADATA_PROJECTION'),
    };
  });
  const locks = [
    ...rows(snapshot?.locks).map((lock) => ({
      task: safeText(lock.task_id), owner: safeText(lock.owner), scope: safeText(lock.scope),
      state: stale && lock.state !== 'FROZEN' ? UNKNOWN : safeText(lock.state), epoch: Number.isInteger(lock.fencing) ? lock.fencing : null,
      source: 'LEGACY_REGISTRY_RECORD', freshness: stale ? 'STALE' : observation.state,
    })),
    ...rows(snapshot?.controller_summary?.worksharing_locks).map((lock) => ({
      task: safeText(lock.assignment), owner: safeText(lock.owner), scope: safeText(lock.scope),
      state: stale && lock.state !== 'FROZEN' ? UNKNOWN : safeText(lock.state), epoch: Number.isInteger(lock.epoch) ? lock.epoch : null,
      source: safeText(lock.source, 'CONTROLLER_SQLITE'), freshness: stale ? 'STALE' : observation.state,
    })),
  ];

  return {
    available: cockpitAvailable,
    source: safeText(cockpit?.source, cockpitAvailable ? 'CONTROLLER_METADATA_PROJECTION' : 'LEGACY_REGISTRY_FALLBACK'),
    observedAt: projectionAt,
    observationState: observation.state,
    error: cockpitAvailable ? null : safeText(cockpitError, 'Cockpit observation unavailable'),
    mission: rows(studio?.missions)[0] ? safeText(studio.missions[0].id) : UNKNOWN,
    missions: [...new Set([
      ...rows(studio?.missions).map((item) => safeText(item.id)),
      ...tasks.map((item) => item.mission).filter((value) => value !== UNKNOWN),
    ])].filter((value) => value !== UNKNOWN),
    waves: [...new Set(tasks.map((item) => item.wave).filter((value) => value !== UNKNOWN))],
    agents, tasks, events, approvals: rows(cockpit?.approvals), locks, controllerAssignments, subagents,
    provenance: cockpitAvailable ? 'CONTROLLER_METADATA; DOES NOT PROVE PROVIDER SESSION OR CODE EXECUTION' : 'LEGACY_REGISTRY_ONLY; RUNTIME UNKNOWN',
  };
}
