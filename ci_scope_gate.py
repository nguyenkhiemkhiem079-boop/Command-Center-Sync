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
    result = subprocess.run(['git', *args], cwd=repo, capture_output=True, check=False)
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
        fields=git(repo,'diff','--name-status','--no-renames','-z',base,commit,'--').split(b'\0')
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

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True); parser.add_argument('--base',required=True)
    parser.add_argument('--commit',required=True); parser.add_argument('--policy',required=True)
    args=parser.parse_args()
    try:
        policy=json.loads(Path(args.policy).read_text(encoding='utf-8'))
        if not isinstance(policy,dict) or not policy.get('scope') or not policy.get('allowed_paths'):
            raise ValueError('trusted scope and allowed_paths policy required')
        result=verify(args.repo,args.base,args.commit,policy['scope'],policy['allowed_paths'],policy.get('protected_paths'))
    except (OSError,ValueError,TypeError) as ex:
        result={'pass':False,'errors':[str(ex)],'quarantine':True}
    print(json.dumps(result,indent=2))
    return 0 if result['pass'] else 2

if __name__=='__main__': raise SystemExit(main())
