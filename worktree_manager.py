"""Controller-owned Git worktree inspection; no overwrite, network push or merge."""
from pathlib import Path
import os,re,subprocess
from registry import Denied

def git(repo,*args):
    env=dict(os.environ)
    for key in ('GIT_DIR','GIT_WORK_TREE','GIT_COMMON_DIR','GIT_INDEX_FILE'):env.pop(key,None)
    p=subprocess.run(['git','-c','core.hooksPath=/dev/null','-C',str(repo),*args],env=env,capture_output=True,text=True,timeout=30)
    if p.returncode:raise ValueError('WORKTREE_GIT_CHECK_FAILED')
    return p.stdout.strip()

def inspect(path,base_sha,candidate_sha=None):
    path=Path(path).resolve(strict=True)
    if not re.fullmatch('[0-9a-fA-F]{40}',base_sha):raise ValueError('IMMUTABLE_BASE_REQUIRED')
    if Path(git(path,'rev-parse','--show-toplevel')).resolve()!=path:raise Denied('WORKTREE_ROOT_REQUIRED')
    for ancestor in (path,*path.parents):
        if ancestor.is_symlink() or getattr(ancestor.stat(),'st_file_attributes',0)&0x400:raise Denied('WORKTREE_REPARSE_PATH')
    branch=git(path,'symbolic-ref','-q','HEAD')
    if not branch.startswith('refs/heads/'):raise Denied('OWNED_BRANCH_REQUIRED')
    git(path,'cat-file','-e',base_sha+'^{commit}');git(path,'merge-base','--is-ancestor',base_sha,'HEAD')
    if candidate_sha is not None:
        if not re.fullmatch('[0-9a-fA-F]{40}',candidate_sha):raise ValueError('IMMUTABLE_CANDIDATE_REQUIRED')
        git(path,'merge-base','--is-ancestor',candidate_sha,'HEAD')
    records=git(path,'worktree','list','--porcelain').splitlines()
    if not any(line.startswith('worktree ') and Path(line[9:]).resolve()==path for line in records):raise Denied('REGISTERED_WORKTREE_REQUIRED')
    common=Path(git(path,'rev-parse','--git-common-dir'))
    if not common.is_absolute():common=path/common
    return {'path':str(path),'branch':branch,'base_sha':base_sha,'head_sha':git(path,'rev-parse','HEAD'),'common_dir':str(common.resolve()),'source':'ACTUAL_GIT_WORKTREE','isolation':'LOGICAL_ONLY'}

def create(actor,repo,base_sha,target,branch,approved_workspace_root):
    if actor!='CODEX':raise Denied('ROLE_DENIED',403)
    repo=Path(repo).resolve(strict=True);root=Path(approved_workspace_root).resolve(strict=True);target=Path(target).resolve()
    if target==root or root not in target.parents or target.exists():raise Denied('NEW_WORKTREE_UNDER_APPROVED_ROOT_REQUIRED')
    if not re.fullmatch('[0-9a-fA-F]{40}',base_sha):raise ValueError('IMMUTABLE_BASE_REQUIRED')
    git(repo,'check-ref-format','--branch',branch);git(repo,'cat-file','-e',base_sha+'^{commit}')
    git(repo,'worktree','add','-b',branch,str(target),base_sha)
    return inspect(target,base_sha)
