"""Bound recovery envelopes and deterministic mission summaries; never QA approval."""
import json
from pathlib import Path
from orchestration import digest,git_identity,stamp
from recovery_manager import RecoveryManager
from trust_vault import file_digest
from registry import Denied

def checkpoint_package(control,actor,assignment,artifact_directory,test_logs):
    if actor!='CODEX':raise Denied('ROLE_DENIED',403)
    task=control.get_assignment(actor,assignment)
    with control.connection() as db:
        row=db.execute('SELECT * FROM cc_checkpoints WHERE id=? AND assignment=?',(task['checkpoint_id'],assignment)).fetchone()
    if row is None:raise Denied('SOURCE_CHECKPOINT_REQUIRED')
    body=json.loads(row['body'])
    if digest({'assignment':assignment,'body':body})!=row['id'] or row['epoch']!=task['epoch']:raise Denied('STALE_OR_TAMPERED_CHECKPOINT')
    repo,tree=git_identity(task['repo'],body['commit_sha'])
    if tree!=body['tree']:raise Denied('CHECKPOINT_TREE_MISMATCH')
    target=Path(artifact_directory).resolve()
    if target.exists():raise ValueError('NEW_PACKAGE_DIRECTORY_REQUIRED')
    logs=[]
    for value in test_logs:
        path=Path(value).resolve(strict=True)
        if not path.is_file() or Path(value).is_symlink():raise ValueError('REGULAR_TEST_LOG_REQUIRED')
        logs.append({'path':str(path),'sha256':file_digest(path)})
    if not logs:raise ValueError('TEST_LOGS_REQUIRED_AS_CLAIMED_EVIDENCE')
    target.mkdir(parents=True)
    recovery=RecoveryManager();bundle=recovery.checkpoint_bundle(repo,body['commit_sha'],target/'source.bundle')
    envelope={'mission':task['mission'],'assignment':assignment,'owner':task['owner'],'epoch':task['epoch'],
        'contract_hash':task['contract_hash'],'revision':task['revision'],'base_sha':task['base_sha'],
        'candidate_sha':body['commit_sha'],'changed_paths':body['changed_paths'],'checkpoint_id':row['id'],
        'bundle':bundle,'logs':logs,'timestamp':stamp(),'verification':'LOCAL_CONSISTENCY_ONLY','production_trusted':False}
    result={'envelope':envelope,'digest':digest(envelope)}
    (target/'manifest.json').write_text(json.dumps(result,sort_keys=True,indent=2),encoding='utf-8')
    return result

def verify_checkpoint_package(control,actor,package):
    if actor!='CODEX':raise Denied('ROLE_DENIED',403)
    e=package['envelope']
    if digest(e)!=package['digest'] or e.get('production_trusted') is not False:raise Denied('PACKAGE_TAMPERED')
    t=control.get_assignment(actor,e['assignment'])
    for key,expected in {'mission':t['mission'],'owner':t['owner'],'epoch':t['epoch'],'contract_hash':t['contract_hash'],'revision':t['revision'],'base_sha':t['base_sha'],'checkpoint_id':t['checkpoint_id']}.items():
        if e.get(key)!=expected:raise Denied('PACKAGE_BINDING_MISMATCH_'+key)
    with control.connection() as db:
        row=db.execute('SELECT body FROM cc_checkpoints WHERE id=? AND assignment=?',(t['checkpoint_id'],t['id'])).fetchone()
    if row is None:raise Denied('SOURCE_CHECKPOINT_REQUIRED')
    body=json.loads(row['body'])
    if digest({'assignment':t['id'],'body':body})!=t['checkpoint_id'] or e['candidate_sha']!=body['commit_sha'] or e['changed_paths']!=body['changed_paths'] or e['bundle']['repo']!=str(Path(t['repo']).resolve()):
        raise Denied('PACKAGE_SOURCE_BINDING_MISMATCH')
    RecoveryManager().verify_bundle(e['bundle'],digest(e['bundle']))
    if e['bundle']['commit_sha']!=e['candidate_sha']:raise Denied('PACKAGE_CANDIDATE_MISMATCH')
    for log in e['logs']:
        if file_digest(log['path'])!=log['sha256']:raise Denied('LOG_TAMPERED')
    return {'status':'LOCAL_VERIFIED','production_trusted':False,'checkpoint_id':e['checkpoint_id']}

def mission_result(control,actor,mission):
    if actor!='CODEX':raise Denied('ROLE_DENIED',403)
    s=control.snapshot(actor);m=next((r for r in s['missions'] if r['id']==mission),None)
    if m is None:raise Denied('MISSION_NOT_FOUND',404)
    tasks=[t for t in s['assignments'] if t['mission']==mission];ids={t['id'] for t in tasks}
    return {'mission':mission,'revision':m['revision'],'tasks':[{'id':t['id'],'owner':t['owner'],'epoch':t['epoch'],'status':t['status'],'checkpoint_id':t['checkpoint_id'],'review_iteration':t['review_iteration']} for t in tasks],
        'checkpoints':[{'id':c['id'],'assignment':c['assignment'],'epoch':c['epoch']} for c in s['checkpoints'] if c['assignment'] in ids],
        'feedback_iterations':[{'assignment':f['assignment'],'iteration':f['iteration'],'issues':json.loads(f['issues']),'evidence':f['evidence']} for f in s['feedback'] if f['assignment'] in ids],
        'pending_requests':[{'id':r['id'],'kind':r['kind'],'status':r['status'],'deadline':r.get('deadline')} for r in s['human_requests'] if r['mission']==mission and r['status']=='PENDING'],
        'blocked_assignments':[t['id'] for t in tasks if t['status'] in ('FROZEN','FAILED')],
        'provider_completion_is_acceptance':False,'production_approval':'NOT_INFERRED','trusted_ci':'NOT_VERIFIED_BY_SUMMARY','source':'CONTROLLER_REGISTRY_AGGREGATE','last_verified_at':stamp()}
