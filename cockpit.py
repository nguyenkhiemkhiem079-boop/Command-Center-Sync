"""Read-only cockpit projections and bounded controller-pinned Git inspection.

Shared-user local records remain LOGICAL_ONLY. No approval mutation or arbitrary
file reader is exposed here. Diff content is best-effort secret redacted; callers
must not treat this as a replacement for repository secret scanning.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from registry import Denied, clean_scope
from orchestration import digest, git_identity


def now():return datetime.now(timezone.utc).isoformat()
def require(actor):
    if actor!='CODEX':raise Denied('ROLE_DENIED',403)
def label(value):
    value=str(value or 'UNKNOWN')
    return value[:100] if re.fullmatch(r'[A-Za-z0-9_.: /-]{1,100}',value) else 'REDACTED_UNTRUSTED_LABEL'
def parse(value,fallback=None):
    try:return json.loads(value) if isinstance(value,str) else value
    except (ValueError,TypeError):return fallback


def snapshot(control_or_snapshot,actor='CODEX'):
    require(actor)
    raw=control_or_snapshot.snapshot(actor) if hasattr(control_or_snapshot,'snapshot') else control_or_snapshot
    if not isinstance(raw,dict):raise ValueError('controller snapshot required')
    verified=now();origin='CONTROLLER_METADATA_PROJECTION'
    def meta(row=None):return {'source':origin,'last_verified_at':verified,'execution_verified_at':None}
    nodes=[];edges=[];assignments=[]
    def node(row,kind,parent=None):
        item={'id':label(row.get('id')),'kind':kind,'state':label(row.get('status',row.get('state'))),'owner':label(row.get('owner')),**meta()}
        nodes.append(item)
        if parent:edges.append({'from':label(parent),'to':item['id'],'kind':'OWNERSHIP',**meta()})
    for r in raw.get('missions',[]):node(r,'MISSION')
    for r in raw.get('waves',[]):node(r,'WAVE',r.get('mission'))
    for r in raw.get('teams',[]):node(r,'TEAM',r.get('mission'))
    for r in raw.get('assignments',[]):
        node(r,'ASSIGNMENT',r.get('team'))
        if r.get('wave'):edges.append({'from':label(r['wave']),'to':label(r['id']),'kind':'WAVE_MEMBERSHIP',**meta()})
        for dependency in parse(r.get('dependencies'),[]) or []:edges.append({'from':label(dependency),'to':label(r.get('id')),'kind':'DEPENDENCY',**meta()})
        assignments.append({'id':label(r.get('id')),'owner':label(r.get('owner')),'state':label(r.get('status')),'base_sha':r.get('base_sha') if re.fullmatch('[0-9a-fA-F]{40}',str(r.get('base_sha'))) else None,'checkpoint_id':r.get('checkpoint_id') if re.fullmatch('[0-9a-fA-F]{64}',str(r.get('checkpoint_id'))) else None,**meta()})
    for r in raw.get('subagents',[]):node(r,'SUBAGENT',r.get('parent'))
    identities=[]
    for role in ('CODEX','ANTI-01','ANTI-02'):
        identities.append({'id':role,'mcp':{'role':role,'contact':'UNKNOWN','source':'ROLE_CONFIGURATION_ONLY','last_verified_at':verified},'runtime':{'session':'UNKNOWN','capabilities':[],'teamwork':'UNKNOWN','source':'NO_RUNTIME_ATTESTATION','last_verified_at':None},'provider':{'account':'UNKNOWN','quota':'UNKNOWN','source':'NO_PROVIDER_ATTESTATION','last_verified_at':None},**meta()})
    timeline=[{'id':r.get('id'),'at':r.get('at'),'actor':label(r.get('actor')),'action':label(r.get('kind')),'target':label(r.get('target')),'summary':'Controller event recorded; private payload omitted',**meta()} for r in raw.get('events',[])[-100:]]
    approvals=[{'id':label(r.get('id')),'mission':label(r.get('mission')),'assignment':label(r.get('assignment')),'kind':label(r.get('kind')),'state':label(r.get('status')),'decision_enabled':False,'owner_principal':'NOT_VERIFIED','summary':'Request content retained in controller; no privilege granted',**meta()} for r in raw.get('human_requests',[]) if r.get('kind') in ('approval','review','MERGE_APPROVAL','RELEASE_APPROVAL','PERMISSION_REQUIRED','CONTRACT_CHANGE','INPUT_REQUIRED','DIRECTION_REQUIRED')]
    performance=[{key:r.get(key,'UNKNOWN') for key in ('agent','accepted_tasks','correction_iterations','blocked_tasks','cost_per_accepted_task','provider_quota')}|meta() for r in raw.get('performance',[])]
    return {'source':origin,'last_verified_at':verified,'isolation_level':'LOGICAL_ONLY','supervisor_mode':label(raw.get('supervisor_mode')),'identity_layers':identities,'fleet':{'nodes':nodes,'edges':edges,**meta()},'timeline':timeline,'approvals':approvals,'assignments':assignments,'performance':performance,'owner_approval_action':'DISABLED_EXTERNAL_PRINCIPAL_REQUIRED'}


_SECRET=re.compile(r'(?i)(password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|authorization|bearer\s+|private[_ -]?key|chain[_ -]?of[_ -]?thought|private[_ -]?reasoning)')
_CREDENTIAL=re.compile(r'(?:AIza[0-9A-Za-z_-]{20,}|(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{12,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|[A-Za-z0-9+/=_-]{48,})')
def redact_patch(text):
    return '\n'.join((line[:1]+'[REDACTED_SENSITIVE_CONTENT]' if _SECRET.search(line) or _CREDENTIAL.search(line) else line) for line in text.splitlines())


def assignment_diff(control,actor,assignment,candidate_sha=None,path=None,max_bytes=32768):
    require(actor)
    if type(max_bytes) is not int or not 512<=max_bytes<=65536:raise ValueError('diff byte limit 512..65536')
    task=control.get_assignment(actor,assignment)
    if not task.get('checkpoint_id'):raise Denied('PINNED_CHECKPOINT_REQUIRED',409)
    with control.connection() as db:
        row=db.execute('SELECT * FROM cc_checkpoints WHERE id=? AND assignment=?',(task['checkpoint_id'],assignment)).fetchone()
    if row is None:raise Denied('PINNED_CHECKPOINT_REQUIRED',409)
    body=parse(row['body'])
    if not isinstance(body,dict) or digest({'assignment':assignment,'body':body})!=row['id']:raise Denied('CHECKPOINT_TAMPERED',409)
    pinned=body.get('commit_sha')
    if candidate_sha is not None and candidate_sha!=pinned:raise Denied('CANDIDATE_NOT_PINNED',403)
    if body.get('epoch')!=task['epoch'] or body.get('contract_hash')!=task['contract_hash'] or body.get('base_sha')!=task['base_sha']:raise Denied('CHECKPOINT_BINDING_MISMATCH',409)
    repo,tree=git_identity(task['repo'],pinned)
    git_identity(repo,task['base_sha'])
    if tree!=body.get('tree'):raise Denied('CHECKPOINT_TREE_MISMATCH',409)
    # Refuse symlink/junction repo ancestry. Shared-user local controller integrity
    # still needs protected external enforcement for a production trust boundary.
    for ancestor in [Path(repo),*Path(repo).parents]:
        stat=ancestor.lstat()
        if ancestor.is_symlink() or getattr(stat,'st_file_attributes',0)&0x400:raise Denied('UNSAFE_REPOSITORY_PATH',403)
    def git(*args,cap=1048576):
        environment={**os.environ,'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':os.devnull,'GIT_PAGER':'cat'}
        for key in ('GIT_DIR','GIT_WORK_TREE','GIT_COMMON_DIR','GIT_INDEX_FILE','GIT_EXTERNAL_DIFF'):environment.pop(key,None)
        proc=subprocess.Popen(['git','--literal-pathspecs','-C',repo,*args],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=environment)
        try:
            output=proc.stdout.read(cap+1)
            if len(output)>cap:proc.kill();proc.wait(timeout=5);return output[:cap],True
            proc.wait(timeout=15)
            if proc.returncode:raise Denied('GIT_INSPECTION_FAILED',409)
            return output,False
        finally:
            if proc.poll() is None:proc.kill();proc.wait(timeout=5)
            proc.stdout.close()
    names,overflow=git('diff','--no-ext-diff','--no-textconv','--no-renames','--name-only','-z',task['base_sha'],pinned)
    if overflow:raise Denied('DIFF_PATH_LIMIT_EXCEEDED',409)
    paths=[s.decode('utf-8',errors='strict') for s in names.split(b'\0') if s]
    allowed=parse(task.get('allowed'),[]) or [];forbidden=(parse(task.get('forbidden'),[]) or [])+(parse(task.get('readonly'),[]) or [])
    def owns(p):
        p=clean_scope(p)
        return any(p==a or p.startswith(a+'/') for a in allowed) and not any(p==f or p.startswith(f+'/') or f.startswith(p+'/') for f in forbidden)
    if any(not owns(p) for p in paths):raise Denied('CANT_EDIT_OUT_OF_SCOPE_DIFF',403)
    if sorted(paths)!=sorted(body.get('changed_paths',[])):raise Denied('CHECKPOINT_DIFF_MISMATCH',409)
    if path is not None:
        if path not in paths or not owns(path):raise Denied('PATH_NOT_IN_OWNED_DIFF',403)
    # Reject changed symlink/submodule entries at either tree, never dereference them.
    for sha in (task['base_sha'],pinned):
        tree_entries,overflow=git('ls-tree','-r','-z',sha,'--',*(paths or ['__no_changed_paths__']))
        if overflow:raise Denied('TREE_ENTRY_LIMIT_EXCEEDED',409)
        if any(entry.startswith((b'120000 ',b'160000 ')) for entry in tree_entries.split(b'\0')):raise Denied('UNSAFE_DIFF_ENTRY',403)
    patch,overflow=git('diff','--no-ext-diff','--no-textconv','--no-renames','--no-color','--unified=3',task['base_sha'],pinned,'--',*([path] if path else paths),cap=max_bytes)
    text=redact_patch(patch.decode('utf-8',errors='replace'))
    return {'assignment':assignment,'base_sha':task['base_sha'],'candidate_sha':pinned,'changed_paths':paths,'selected_path':path,'scope_pass':True,'patch':text,'truncated':overflow,'max_bytes':max_bytes,'redaction':'BEST_EFFORT_SENSITIVE_LINES_REMOVED','independent_qa':'NOT_INFERRED_FROM_DIFF','source':'CONTROLLER_PINNED_GIT_COMMITS','last_verified_at':now()}
