const UNKNOWN = 'UNKNOWN';
const safeText = (value, fallback = UNKNOWN) => {
  if (typeof value !== 'string') return fallback;
  const text = value.trim();
  return text && text.length <= 240 && !/[\u0000-\u001f]/.test(text) ? text : fallback;
};
const rows = (value) => Array.isArray(value) ? value.filter((row) => row && typeof row === 'object' && !Array.isArray(row)) : [];
const taskState = (value) => {
  const state = safeText(value).toUpperCase();
  if (state === 'FROZEN' || state === 'BLOCKED') return 'BLOCKED';
  if (['SUBMITTED', 'SELF_QA_READY', 'QA_PENDING'].includes(state)) return 'AWAITING_QA';
  if (['CHANGES_REQUESTED', 'REWORK_REQUIRED'].includes(state)) return 'FEEDBACK_REQUESTED';
  if (['ACCEPTED', 'CODE_REVIEWED', 'PASS_CODE_REVIEW'].includes(state)) return 'ACCEPTED';
  if (['RUNNING', 'IN_PROGRESS'].includes(state)) return 'IN_PROGRESS';
  if (['ACKNOWLEDGED', 'ACK'].includes(state)) return 'ACKNOWLEDGED';
  if (state === 'QUEUED' || state === 'ASSIGNED') return 'ASSIGNED';
  return 'UNKNOWN';
};

export function normalizeAgentWorld({ cockpit, snapshot, studio, cockpitError = null, observedAt = new Date().toISOString() } = {}) {
  const cockpitAvailable = Boolean(cockpit && typeof cockpit === 'object' && !Array.isArray(cockpit));
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
    return {
      id,
      title: safeText(item.title, id),
      owner: safeText(item.owner),
      state: taskState(assignment?.state ?? item.state),
      rawState: safeText(assignment?.state ?? item.state),
      wave: safeText(item.wave_id ?? item.wave ?? assignment?.wave),
      mission: safeText(assignment?.mission ?? item.mission_id),
      scope: safeText(assignment?.scope ?? item.scope),
      baseSha: safeText(assignment?.base_sha ?? item.base_sha),
      checkpoint: Boolean(assignment?.checkpoint_id || item.checkpoint || item.checkpoint_at),
      evidence: assignment?.source || item.source || 'REGISTRY_RECORD',
      lastObservedAt: safeText(assignment?.last_verified_at ?? item.updated, observedAt),
    };
  });
  for (const item of controllerAssignments) {
    const id = safeText(item.id);
    if (tasks.some((task) => task.id === id)) continue;
    tasks.push({
      id, title: safeText(item.title, id), owner: safeText(item.owner), state: taskState(item.state),
      rawState: safeText(item.state), wave: safeText(item.wave), mission: safeText(item.mission),
      scope: safeText(item.scope ?? item.allowed), baseSha: safeText(item.base_sha),
      checkpoint: Boolean(item.checkpoint_id), evidence: safeText(item.source, 'CONTROLLER_RECORD'),
      lastObservedAt: safeText(item.last_verified_at, observedAt),
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
    const verifiedTeamwork = teamwork === 'TEAMWORK_ACTIVE' && verification === 'VERIFIED';
    return {
      id,
      role: id === 'CODEX' ? 'SUPERVISOR' : 'DEVELOPMENT TEAM',
      mcp: safeText(record?.mcp?.contact),
      runtime: verifiedTeamwork ? 'TEAMWORK_ACTIVE' : safeText(runtime.session),
      teamwork: verifiedTeamwork ? 'TEAMWORK_ACTIVE' : UNKNOWN,
      evidenceClass: verifiedTeamwork ? 'VERIFIED' : (verification === 'AGENT_REPORTED' ? 'AGENT_REPORTED' : 'UNKNOWN'),
      source: safeText(record?.source ?? record?.runtime?.source, record ? 'NO_RUNTIME_ATTESTATION' : 'ROLE_CONFIGURED_RUNTIME_UNKNOWN'),
      lastObservedAt: safeText(record?.runtime?.last_verified_at ?? record?.last_verified_at),
      tasks: assigned,
      ownership: assigned.map((task) => ({ task: task.id, scope: task.scope, state: task.state })),
    };
  });
  const subagents = rows(cockpit?.fleet?.nodes).filter((node) => node.kind === 'SUBAGENT').map((node) => ({
    id: safeText(node.id), parent: safeText(node.owner), assignment: safeText(node.parent), role: 'SUBAGENT', mcp: UNKNOWN,
    runtime: UNKNOWN, teamwork: UNKNOWN, evidenceClass: 'UNKNOWN',
    source: safeText(node.source, 'CONTROLLER_METADATA_PROJECTION'),
    lastObservedAt: safeText(node.last_verified_at),
    tasks: tasks.filter((task) => task.owner === safeText(node.id)),
    ownership: [{ task: safeText(node.parent), scope: 'INHERITED_FROM_PARENT', state: safeText(node.state) }],
  })).filter((agent) => agent.id !== UNKNOWN && !roles.includes(agent.id));
  agents.push(...subagents);

  const events = rows(cockpit?.timeline).map((event, index) => {
    const target = safeText(event.target);
    const relatedTask = tasks.find((item) => item.id === target);
    return {
    id: safeText(event.id, `event-${index}`),
    at: safeText(event.at),
    actor: safeText(event.actor),
    type: safeText(event.action),
    target,
    mission: safeText(event.mission ?? relatedTask?.mission),
    wave: safeText(event.wave ?? relatedTask?.wave),
    summary: safeText(event.summary, 'Controller event recorded; payload omitted'),
    source: safeText(event.source, cockpit?.source || 'CONTROLLER_METADATA_PROJECTION'),
  }; });
  const locks = [
    ...rows(snapshot?.locks).map((lock) => ({
    task: safeText(lock.task_id), owner: safeText(lock.owner), scope: safeText(lock.scope),
    state: safeText(lock.state), epoch: Number.isInteger(lock.fencing) ? lock.fencing : null,
    source: 'LEGACY_REGISTRY_RECORD',
    })),
    ...rows(snapshot?.controller_summary?.worksharing_locks).map((lock) => ({
      task: safeText(lock.assignment), owner: safeText(lock.owner), scope: safeText(lock.scope),
      state: safeText(lock.state), epoch: Number.isInteger(lock.epoch) ? lock.epoch : null,
      source: safeText(lock.source, 'CONTROLLER_SQLITE'),
    })),
  ];

  return {
    available: cockpitAvailable,
    source: safeText(cockpit?.source, cockpitAvailable ? 'CONTROLLER_METADATA_PROJECTION' : 'LEGACY_REGISTRY_FALLBACK'),
    observedAt: safeText(cockpit?.last_verified_at, observedAt),
    mode: safeText(cockpit?.supervisor_mode),
    error: cockpitAvailable ? null : safeText(cockpitError, 'Cockpit observation unavailable'),
    mission: rows(studio?.missions)[0] ? safeText(studio.missions[0].id) : UNKNOWN,
    missions: [...new Set([
      ...rows(studio?.missions).map((item) => safeText(item.id)),
      ...tasks.map((item) => item.mission).filter((value) => value !== UNKNOWN),
    ])].filter((value) => value !== UNKNOWN),
    waves: [...new Set(tasks.map((item) => item.wave).filter((value) => value !== UNKNOWN))],
    agents,
    tasks,
    events,
    approvals: rows(cockpit?.approvals),
    locks,
    controllerAssignments,
    subagents,
    provenance: cockpitAvailable ? 'CONTROLLER_METADATA; DOES NOT PROVE PROVIDER SESSION OR CODE EXECUTION' : 'LEGACY_REGISTRY_ONLY; RUNTIME UNKNOWN',
  };
}

export { taskState };
