"""Fail-closed Git source boundary gate. Policy must come from a trusted supervisor/base."""
import argparse
import json
import os
import stat
from pathlib import Path
import re
import subprocess
from registry import clean_scope

SHA = re.compile(r'^[0-9a-fA-F]{40}$')

def git(repo, *args):
    environment=dict(os.environ)
    for key in ('GIT_DIR','GIT_WORK_TREE','GIT_COMMON_DIR','GIT_INDEX_FILE','GIT_EXTERNAL_DIFF'):
        environment.pop(key,None)
    result = subprocess.run(['git', *args], cwd=repo, capture_output=True, check=False,env=environment,timeout=30)
    if result.returncode:
        raise ValueError('git command failed: ' + ' '.join(args[:2]))
    return result.stdout

def walk_error(error):
    raise error

def within(path, scope):
    return path == scope or path.startswith(scope + '/')

def verify(repo, base, commit, scope, allowed_paths=None, protected_paths=None):
    errors=[]; changed=[]; entries=[]
    try:
        if not SHA.fullmatch(base) or not SHA.fullmatch(commit):
            raise ValueError('immutable 40-hex commit IDs required')
        scope=clean_scope(scope)
        allowed=[clean_scope(p) for p in (allowed_paths if allowed_paths is not None else [scope])]
        protected=[clean_scope(p) for p in (protected_paths or [])]
        if not allowed or any(not within(p,scope) for p in allowed):
            raise ValueError('allowed paths must be inside task scope')
        for sha in (base,commit): git(repo,'cat-file','-e',sha+'^{commit}')
        git(repo,'merge-base','--is-ancestor',base,commit)
        fields=git(repo,'diff','--no-ext-diff','--no-textconv','--name-status','--no-renames','-z',base,commit,'--').split(b'\0')
        if fields[-1] != b'': raise ValueError('truncated diff')
        fields.pop()
        if len(fields)%2: raise ValueError('invalid diff records')
        for i in range(0,len(fields),2):
            status=fields[i].decode('ascii'); raw=fields[i+1].decode('utf-8','strict')
            if status not in ('A','M','D','T'): raise ValueError('unsupported diff status')
            # Git paths use forward slashes. Reject aliases instead of normalizing them.
            if '\\' in raw: raise ValueError('noncanonical Git path')
            path=clean_scope(raw)
            changed.append(path); entries.append({'status':status,'path':raw})
            if not within(path,scope) or not any(within(path,p) for p in allowed):
                errors.append('OUT_OF_SCOPE: '+raw)
            if any(within(path,p) or within(p,path) for p in protected):
                errors.append('PROTECTED_PATH: '+raw)
        if not changed: errors.append('EMPTY_DIFF')
        # Git trees do not represent NTFS junctions. Check the live worktree too,
        # pruning all links/reparse points before os.walk can traverse them.
        for directory, dirs, files in os.walk(repo, followlinks=False, onerror=walk_error):
            if Path(directory) == Path(repo) and '.git' in dirs: dirs.remove('.git')
            for name in dirs[:] + files:
                item=Path(directory)/name
                attrs=item.lstat()
                if stat.S_ISLNK(attrs.st_mode) or getattr(attrs,'st_file_attributes',0) & getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400):
                    errors.append('PHYSICAL_REPARSE_POINT: '+str(item.relative_to(repo)))
                    if name in dirs: dirs.remove(name)

        # Inspect both trees, including deleted links and symlink ancestors.
        for sha in (base,commit):
            for record in git(repo,'ls-tree','-r','-z',sha).split(b'\0'):
                if not record: continue
                metadata,raw=record.split(b'\t',1)
                path=clean_scope(raw.decode('utf-8','strict'))
                if metadata.split()[0] in (b'120000', b'160000') and (within(path,scope) or any(within(p,path) for p in changed)):
                    errors.append('SYMLINK_ENTRY: '+path)
    except (ValueError, OSError, UnicodeError) as ex:
        errors.append(str(ex))
    return {'pass':not errors,'errors':errors,'changed_paths':changed,'entries':entries,
            'base_sha':base,'commit_sha':commit,'quarantine':bool(errors)}


def verify_policy(repo,base,commit,policy,assignment=None,repository=None):
    """Policy loaded from immutable trusted base; a pending policy never permits CI."""
    if not isinstance(policy,dict): raise ValueError('POLICY_OBJECT_REQUIRED')
    if policy.get('schema_version')!=1: raise ValueError('UNSUPPORTED_POLICY_SCHEMA')
    if set(policy)-{'schema_version','repository','approval_state','assignments','protected_paths'}: raise ValueError('UNKNOWN_POLICY_FIELDS')
    if not isinstance(policy.get('repository'),str) or not policy['repository']: raise ValueError('REPOSITORY_REQUIRED')
    if repository is not None and policy['repository']!=repository: raise ValueError('POLICY_REPOSITORY_MISMATCH')
    if policy.get('approval_state')!='OWNER_APPROVED': raise ValueError('OWNER_APPROVED_BASE_POLICY_REQUIRED')
    assignments=policy.get('assignments')
    if not isinstance(assignments,dict) or not assignment or assignment not in assignments: raise ValueError('APPROVED_ASSIGNMENT_REQUIRED')
    item=assignments[assignment]
    if not isinstance(item,dict) or set(item)!={'scope','allowed_paths','resource_locks','required_resource_locks'}: raise ValueError('ASSIGNMENT_POLICY_SCHEMA')
    protected=policy.get('protected_paths')
    if not isinstance(protected,list) or not protected: raise ValueError('PROTECTED_PATHS_REQUIRED')
    for values in (item['allowed_paths'],protected,item['resource_locks'],item['required_resource_locks']):
        if not isinstance(values,list) or any(not isinstance(v,str) or not v for v in values): raise ValueError('EXPLICIT_POLICY_LIST_REQUIRED')
    if not set(item['required_resource_locks'])<=set(item['resource_locks']): raise ValueError('SHARED_RESOURCE_LOCK_REQUIRED')
    # Name-status without rename folding validates both source and destination.
    result=verify(repo,base,commit,item['scope'],item['allowed_paths'],protected)
    result.update({'assignment':assignment,'repository':policy['repository'],'policy_source':'TRUSTED_BASE_REQUIRED','production_approval_inferred':False})
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True); parser.add_argument('--base',required=True)
    parser.add_argument('--commit',required=True); parser.add_argument('--policy',required=True)
    parser.add_argument('--assignment');parser.add_argument('--repository')
    args=parser.parse_args()
    try:
        policy=json.loads(Path(args.policy).read_text(encoding='utf-8'))
        result=verify_policy(args.repo,args.base,args.commit,policy,args.assignment,args.repository)
    except (OSError,ValueError,TypeError) as ex:
        result={'pass':False,'errors':[str(ex)],'quarantine':True}
    print(json.dumps(result,indent=2))
    return 0 if result['pass'] else 2

if __name__=='__main__': raise SystemExit(main())
