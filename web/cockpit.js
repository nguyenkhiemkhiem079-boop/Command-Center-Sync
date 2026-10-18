'use strict';
async function loadCockpit(){try{state.cockpit=(await req('cockpit')).result;state.cockpitError=null;}catch(e){state.cockpit=null;state.cockpitError=e.message;}}
function fleetGraph(fleet){
 const nodes=(fleet?.nodes||[]).slice(0,100),positions=new Map(),counts={};
 if(!nodes.length)return empty('NOT_RECORDED — no recorded hierarchy or execution.');
 const columns={MISSION:0,WAVE:1,TEAM:2,ASSIGNMENT:3,SUBAGENT:4};
 nodes.forEach(n=>{const col=columns[n.kind]??3,row=counts[col]||0;counts[col]=row+1;positions.set(n.id,{x:20+col*230,y:28+row*94});});
 const height=Math.max(160,...Object.values(counts).map(v=>v*94+30));
 const edges=(fleet.edges||[]).filter(e=>positions.has(e.from)&&positions.has(e.to)).map(e=>{const a=positions.get(e.from),b=positions.get(e.to);return `<line x1="${a.x+160}" y1="${a.y+26}" x2="${b.x}" y2="${b.y+26}" stroke="${e.kind==='DEPENDENCY'?'#bd7a24':'#9aaabe'}" stroke-dasharray="${e.kind==='DEPENDENCY'?'5 4':'0'}"><title>${escapeHtml(e.kind)}</title></line>`}).join('');
 const boxes=nodes.map(n=>{const p=positions.get(n.id);return `<g><rect x="${p.x}" y="${p.y}" width="170" height="68" rx="9" fill="#f2f6fc" stroke="#9aaabe"/><text x="${p.x+10}" y="${p.y+19}" font-size="10" fill="#53647e">${escapeHtml(n.kind)}</text><text x="${p.x+10}" y="${p.y+38}" font-size="12" fill="#162846">${escapeHtml(n.id.slice(0,22))}</text><text x="${p.x+10}" y="${p.y+56}" font-size="10" fill="#53647e">${escapeHtml(n.state)}</text><title>${escapeHtml(n.id+' · '+n.owner)}</title></g>`}).join('');
 return `<div class="table-scroll"><svg role="img" aria-label="Controller Fleet dependency graph" viewBox="0 0 1150 ${height}" class="fleet-graph">${edges}${boxes}</svg></div><p class="muted">Max100 nodes. Dashed edges: dependencies. Controller graph does not verify provider execution.</p>`;
}
function renderCockpit(){
 if(state.cockpitError)return `<div class="panel"><div class="panel-body" role="alert">Cockpit API unavailable: ${escapeHtml(state.cockpitError)}. No substituted execution data.</div></div>`;
 const r=state.cockpit;if(!r)return empty('NOT_RECORDED');
 const identities=(r.identity_layers||[]).map(x=>({id:x.id,mcp:x.mcp?.contact||'UNKNOWN',runtime:x.runtime?.session||'UNKNOWN',teamwork:x.runtime?.teamwork||'UNKNOWN',provider:x.provider?.account||'UNKNOWN',quota:x.provider?.quota||'UNKNOWN',source:x.source,last_verified_at:x.last_verified_at}));
 return `<div class="notice"><span>Source: ${escapeHtml(r.source)} · Verified: ${escapeHtml(r.last_verified_at)} · LOGICAL_ONLY. Protected owner approval: NOT_CONFIGURED.</span></div>`+
 studioPanel('Identity & Account Inspector','MCP identity, runtime session and provider account are separate layers.',identities,[['id','IDENTITY'],['mcp','MCP'],['runtime','SESSION'],['teamwork','TEAMWORK'],['provider','PROVIDER'],['quota','QUOTA']])+
 `<div class="panel"><div class="panel-head"><div><div class="panel-title">Fleet DAG & Ownership</div><div class="panel-desc">${escapeHtml(r.fleet?.source)} · ${escapeHtml(r.fleet?.last_verified_at)}</div></div></div><div class="panel-body">${fleetGraph(r.fleet)}</div></div>`+
 studioPanel('Approval Inbox','Read-only until protected owner principal exists. Buttons cannot confer authority.',r.approvals,[['id','REQUEST'],['kind','TYPE'],['state','STATE'],['owner_principal','OWNER'],['decision_enabled','DECISION ENABLED']])+
 `<div class="panel"><div class="panel-head"><div><div class="panel-title">Pinned Git Diff Inspector</div><div class="panel-desc">Controller-pinned immutable checkpoints; best-effort content redaction.</div></div></div><div class="panel-body">${(r.assignments||[]).filter(x=>x.checkpoint_id).map(x=>`<button class="btn ghost" data-act="pinned-diff" data-assignment="${escapeHtml(x.id)}">${escapeHtml(x.id)} · ${escapeHtml(short(x.base_sha))}</button>`).join('')||empty('NOT_RECORDED — no pinned checkpoint.')}<pre id="pinnedDiff" class="evidence-detail">${state.pinnedDiff?escapeHtml(JSON.stringify(state.pinnedDiff,null,2)):'Select a recorded checkpoint. Git comparison does not replace independent QA.'}</pre></div></div>`+
 studioPanel('Authorized Event Timeline','Private event bodies, tool output and reasoning are excluded.',r.timeline,[['id','SEQUENCE'],['at','TIME'],['actor','ACTOR'],['action','EVENT'],['target','TARGET']]);
}
