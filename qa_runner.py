"""Independent local Git + build/test verifier for K-TOOL Command Center.
Run from a trusted supervisor Windows account with filesystem ACL isolation.
NOT a Revit runtime test and NOT a secure boundary when the worker shares OS privileges.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from registry import Registry, clean_scope


def execute(argv, cwd: Path, timeout: int = 180, output_limit=10000):
    if not isinstance(argv, list) or not argv or not all(isinstance(x,str) and x for x in argv):
        return {'exit':None,'error':'INVALID_COMMAND','stdout':'','stderr':''}
    try:
        p=subprocess.run(argv,cwd=str(cwd),capture_output=True,text=True,errors='replace',timeout=timeout,check=False)
        return {'exit':p.returncode,'stdout':p.stdout[-output_limit:] if output_limit else p.stdout,'stderr':p.stderr[-10000:]}
    except subprocess.TimeoutExpired:
        return {'exit':None,'error':'TIMEOUT','stdout':'','stderr':''}
    except OSError as ex:
        return {'exit':None,'error':type(ex).__name__,'stdout':'','stderr':''}


def assess(db_path:Path, tid:str, repo:Path, profile:Path):
    store=Registry(db_path)
    t=store.get_task('CODEX',tid)
    if t['state']!='SUBMITTED':raise ValueError('task must be SUBMITTED')
    res=json.loads(t['result_json'] or '{}')
    selfqa=json.loads(t['self_qa_json'] or '{}')
    if not res or not selfqa:raise ValueError('source + self QA missing')
    profile_bytes=profile.read_bytes()
    config=json.loads(profile_bytes.decode('utf-8'))
    if set(config) != {'build','tests'}:
        raise ValueError('QA profile needs build/tests argv arrays only')
    repo=repo.resolve(strict=True)
    git_root=execute(['git','rev-parse','--show-toplevel'],repo)
    root=Path(git_root['stdout'].strip()).resolve() if git_root['exit']==0 else None
    if root!=repo:raise ValueError('repo must be Git root')
    current=execute(['git','rev-parse','HEAD'],repo)
    sha=current['stdout'].strip().lower()
    expected=res['commit_sha'].lower()
    base=execute(['git','cat-file','-e',t['base_sha']+'^{commit}'],repo)
    ancestor=execute(['git','merge-base','--is-ancestor',t['base_sha'],expected],repo)
    diff=execute(['git','diff','--name-only','--no-renames','-z',t['base_sha'],expected],repo,output_limit=None) if base['exit']==0 else {'exit':None,'stdout':''}
    clean=execute(['git','status','--porcelain','--untracked-files=all'],repo)
    changed=[x for x in diff.get('stdout','').split('\0') if x]
    normalized=[]
    try: normalized=[clean_scope(x) for x in changed]
    except ValueError: normalized=[]
    path_check=bool(changed) and len(normalized)==len(changed) and all(
        x==t['scope'] or x.startswith(t['scope']+'/') for x in normalized)
    claimed=sorted(selfqa.get('changed_paths',[]))
    path_check=path_check and sorted(normalized)==claimed
    tree_clean=clean['exit']==0 and clean['stdout'].strip()==''
    identity_ok=sha==expected and base['exit']==0 and ancestor['exit']==0 and diff['exit']==0 and current['exit']==0
    # Fail closed: NEVER execute build/test on a mismatching or out-of-scope commit.
    if tree_clean and identity_ok and path_check:
        build=execute(config['build'],repo,300)
        tests=execute(config['tests'],repo,300) if build['exit']==0 else {'exit':None,'error':'BUILD_FAILED_FIRST'}
    else:
        build={'exit':None,'error':'GIT_PREFLIGHT_FAILED'}
        tests={'exit':None,'error':'GIT_PREFLIGHT_FAILED'}
    final_head=execute(['git','rev-parse','HEAD'],repo)
    final_clean=execute(['git','status','--porcelain','--untracked-files=all'],repo)
    identity_ok=identity_ok and final_head['exit']==0 and final_head['stdout'].strip().lower()==expected
    tree_clean=tree_clean and final_clean['exit']==0 and final_clean['stdout'].strip()==''
    payload={'task_id':tid,'commit_sha':sha,'expected_sha':expected,'base_sha':t['base_sha'],
             'git_root':str(repo),'diff':changed,'git_verified':identity_ok,'path_check':path_check,
             'tree_clean':tree_clean,'postflight_head':final_head,'postflight_status':final_clean,
             'baseline_ancestor':ancestor['exit']==0,'profile_sha256':hashlib.sha256(profile_bytes).hexdigest(),
             'build':build,'tests':tests, 'revit_host':'NOT_EXECUTED', 'agent_sessions':'NOT_VERIFIED'}
    stored=store.register_local_qa(tid,t['qa_round'],expected,identity_ok and path_check,tree_clean,
                                   normalized,build['exit'],tests['exit'],payload)
    return stored


def main():
    ap=argparse.ArgumentParser(description='Trusted independent QA: run from supervisor Windows profile only.')
    ap.add_argument('--db',default=str(Path(__file__).with_name('private')/'registry.db'))
    ap.add_argument('--task',required=True)
    ap.add_argument('--repo',required=True)
    ap.add_argument('--profile',required=True)
    args=ap.parse_args()
    result=assess(Path(args.db),args.task,Path(args.repo),Path(args.profile))
    print(json.dumps(result,indent=2))
    return 0 if result['result']=='PASS' else 2

if __name__=='__main__':sys.exit(main())
