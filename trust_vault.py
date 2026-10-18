"""Evidence validation. Local hashes establish consistency, never a protected principal."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import os
import subprocess

HEX40=re.compile(r'^[0-9a-f]{40}$')
HEX64=re.compile(r'^[0-9a-f]{64}$')
REQUIRED={'mission','task','iteration','identity','epoch','repo','base_sha','candidate_sha','tree_sha',
          'paths','profile_digest','suite_digest','commands','artifacts','timestamp','provenance','trust_policy_digest',
          'contract_hash','workflow_revision','verifier_identity','approval_status'}

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_git_source(evidence, policy):
    """Check immutable Git facts independently; never infer command execution."""
    from registry import clean_scope, collide
    repo=Path(policy.get('repo_path') or evidence['repo']).resolve(strict=True)
    environment=dict(os.environ)
    for key in ('GIT_DIR','GIT_WORK_TREE','GIT_COMMON_DIR','GIT_INDEX_FILE'):
        environment.pop(key,None)
    def git(*args):
        result=subprocess.run(['git','-C',str(repo),*args],capture_output=True,
                              timeout=15,check=False,env=environment)
        if result.returncode:
            raise ValueError('SOURCE_GIT_COMMAND_FAILED')
        return result.stdout
    if Path(git('rev-parse','--show-toplevel').decode().strip()).resolve()!=repo:
        raise ValueError('SOURCE_REPOSITORY_ROOT_REQUIRED')
    base,candidate=evidence['base_sha'],evidence['candidate_sha']
    for commit in (base,candidate):
        if git('rev-parse',commit+'^{commit}').decode().strip()!=commit:
            raise ValueError('SOURCE_COMMIT_MISMATCH')
    git('merge-base','--is-ancestor',base,candidate)
    if git('rev-parse',candidate+'^{tree}').decode().strip()!=evidence['tree_sha']:
        raise ValueError('SOURCE_TREE_MISMATCH')
    raw=git('diff','--no-ext-diff','--no-textconv','--name-only','--no-renames','-z',base,candidate,'--')
    paths=[item.decode('utf-8','strict') for item in raw.split(b'\0') if item]
    if not paths or sorted(paths)!=sorted(evidence['paths']):
        raise ValueError('SOURCE_PATHS_MISMATCH')
    if any('\\' in path for path in paths):
        raise ValueError('SOURCE_NONCANONICAL_PATH')
    normalized=[clean_scope(path) for path in paths]
    allowed=policy.get('allowed_paths')
    if allowed is None and policy.get('scope'):
        allowed=[policy['scope']]
    if allowed is not None:
        if not isinstance(allowed,list) or not allowed:
            raise ValueError('SOURCE_ALLOWLIST_REQUIRED')
        allowed=[clean_scope(path) for path in allowed]
        if any(not any(path==scope or path.startswith(scope+'/') for scope in allowed) for path in normalized):
            raise ValueError('SOURCE_OUT_OF_SCOPE')
    protected=[clean_scope(path) for path in policy.get('protected_paths',[])]
    if any(collide(path,scope) for path in normalized for scope in protected):
        raise ValueError('SOURCE_PROTECTED_PATH')
    if policy.get('scope'):
        from ci_scope_gate import verify
        checked=verify(repo,base,candidate,policy['scope'],allowed,protected)
        if not checked['pass']:
            raise ValueError('SOURCE_SCOPE_GATE_FAILED')
    return {'repository_root_verified':True,'commits_verified':True,
            'baseline_ancestor':True,'tree_verified':True,'changed_paths_verified':True}

def verify_evidence(evidence,policy,ci_fetch=None,now=None):
    errors=[]
    def require(condition,message):
        if not condition: errors.append(message)
    try:
        require(isinstance(evidence,dict) and REQUIRED<=evidence.keys(),'SCHEMA_MISSING')
        if errors: return {'status':'REJECTED','errors':errors}
        require(evidence['trust_policy_digest']==digest(policy),'TRUST_POLICY_TAMPERED')
        for key in ('mission','task','identity','repo','provenance'):
            require(isinstance(evidence[key],str) and bool(evidence[key]),'INVALID_'+key)
        for key in ('iteration','epoch'):
            require(type(evidence[key]) is int and evidence[key]>0,'INVALID_'+key)
        for key in ('base_sha','candidate_sha','tree_sha'):
            require(bool(HEX40.fullmatch(evidence[key])),'INVALID_'+key)
        for key in ('profile_digest','suite_digest','contract_hash','workflow_revision'):
            require(bool(HEX64.fullmatch(evidence[key])),'INVALID_'+key)
        # Controller policy pins every task binding; missing expected binding fails closed.
        expected=policy.get('expected',{})
        bindings=('mission','task','iteration','identity','epoch','repo','base_sha','candidate_sha','tree_sha','paths','profile_digest','suite_digest','contract_hash','workflow_revision','verifier_identity','approval_status')
        for key in bindings:
            require(key in expected and evidence[key]==expected[key],'BINDING_MISMATCH_'+key)
        require(isinstance(evidence['paths'],list) and bool(evidence['paths']) and
                all(isinstance(p,str) and p and not p.startswith(('/','\\')) and '\\' not in p and ':' not in p and all(x not in ('','.','..') for x in p.split('/')) for p in evidence['paths']),'INVALID_PATHS')
        require(isinstance(evidence['commands'],list) and bool(evidence['commands']),'COMMANDS_REQUIRED')
        for command in evidence['commands']:
            require(isinstance(command,dict) and isinstance(command.get('argv'),list) and bool(command['argv']) and
                    all(isinstance(a,str) and a for a in command['argv']) and type(command.get('exit')) is int and command['exit']==0,'COMMAND_NOT_PASS')
        require(digest(evidence['commands'])==policy.get('commands_digest'),'COMMAND_CONFIG_MISMATCH')
        for name,key in [('profile_path','profile_digest'),('suite_path','suite_digest')]:
            path=policy.get(name)
            require(bool(path) and Path(path).is_file() and file_digest(path)==evidence[key],'CONFIG_TAMPERED_'+name)
        artifacts=evidence['artifacts']
        require(isinstance(artifacts,list) and bool(artifacts),'ARTIFACTS_REQUIRED')
        seen=set()
        for artifact in artifacts:
            require(isinstance(artifact,dict) and set(artifact)>={'name','path','sha256'},'ARTIFACT_SCHEMA')
            if not isinstance(artifact,dict) or not {'name','path','sha256'}<=artifact.keys(): continue
            require(artifact['name'] not in seen,'DUPLICATE_ARTIFACT'); seen.add(artifact['name'])
            require(Path(artifact['path']).is_file() and file_digest(artifact['path'])==artifact['sha256'],'ARTIFACT_TAMPERED_'+artifact['name'])
        instant=datetime.fromisoformat(evidence['timestamp'].replace('Z','+00:00'))
        require(instant.tzinfo is not None,'TIMEZONE_REQUIRED')
        age=((now or datetime.now(timezone.utc))-instant).total_seconds()
        require(0<=age<=policy.get('max_age_seconds',3600),'STALE_OR_FUTURE_EVIDENCE')
        if errors: return {'status':'REJECTED','errors':errors,'evidence_digest':digest(evidence)}
        source=verify_git_source(evidence,policy)
        if evidence['provenance']=='LOCAL_SAME_USER':
            if evidence['approval_status']!='NOT_APPROVED':
                return {'status':'REJECTED','errors':['LOCAL_EVIDENCE_CANNOT_APPROVE'],'production_trusted':False}
            return {'status':'LOCAL_VERIFIED','errors':[],'production_trusted':False,
                    'source_verification':source,
                    'command_evidence':'CONSISTENCY_ONLY_NOT_EXECUTION_PROOF',
                    'evidence_digest':digest(evidence)}
        if evidence['provenance']!='PROTECTED_CI' or ci_fetch is None:
            return {'status':'BLOCKED','errors':['PROTECTED_VERIFIER_UNAVAILABLE'],'production_trusted':False}
        ci_policy=policy.get('ci',{})
        if not all(ci_policy.get(k) for k in ('repo','workflow','workflow_sha','issuer','required_checks')) or not evidence.get('run_id'):
            return {'status':'BLOCKED','errors':['TRUSTED_CI_POLICY_MISSING'],'production_trusted':False}
        fetched=ci_fetch(ci_policy['repo'],evidence['run_id'])
        # Adapter must obtain these independently from the hosted service; worker booleans are never inputs.
        for key,expected_value in {'repo':ci_policy['repo'],'workflow':ci_policy['workflow'],
            'workflow_sha':ci_policy['workflow_sha'],'issuer':ci_policy['issuer'],'run_id':evidence['run_id'],'head_sha':evidence['candidate_sha'],
            'conclusion':'success','status':'completed'}.items():
            require(fetched.get(key)==expected_value,'CI_MISMATCH_'+key)
        require(fetched.get('evidence_digest')==digest(evidence),'CI_EVIDENCE_NOT_BOUND')
        require(fetched.get('policy_digest')==digest(policy),'CI_POLICY_NOT_BOUND')
        require(fetched.get('artifacts')=={a['name']:a['sha256'] for a in artifacts},'CI_ARTIFACTS_NOT_BOUND')
        checks=fetched.get('checks',{})
        require(all(checks.get(c)=='success' for c in ci_policy['required_checks']),'CI_REQUIRED_CHECK_FAILED')
        if errors: return {'status':'REJECTED','errors':errors,'production_trusted':False}
        # This distribution contains no independently anchored protected CI adapter.
        # Callback attributes and fetched JSON are mutable same-user inputs, not
        # proof of a protected principal. Keep metadata validation above useful
        # for future integration, but no caller-controlled flag can enable trust.
        return {'status':'BLOCKED','errors':['PROTECTED_TRUST_BOUNDARY_NOT_CONFIGURED'],
                'production_trusted':False,'evidence_digest':digest(evidence)}
    except Exception as error:
        return {'status':'REJECTED','errors':['VALIDATION_ERROR:'+type(error).__name__],'production_trusted':False}
