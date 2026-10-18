"""Create a NEW isolated QA-only fixture; never import production credentials/Registry."""
import argparse,json,secrets,subprocess
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from registry import Registry,hash_token
from orchestration import ControlStore

def prepare(root):
    root=Path(root).resolve()
    if root.exists():raise FileExistsError('New empty staging root required')
    root.mkdir(parents=True)
    protect=Path(__file__).resolve().parents[1]/'scripts/protect-private-path.ps1'
    subprocess.run(['pwsh','-NoProfile','-File',str(protect),'-LiteralPath',str(root)],capture_output=True,check=True)
    tokens={role:secrets.token_urlsafe(40) for role in ('CODEX','ANTI-01','ANTI-02')}
    (root/'roles.json').write_text(json.dumps({r:hash_token(t) for r,t in tokens.items()}))
    (root/'operator.txt').write_text(tokens['CODEX'])
    repo=root/'fixture-repo';repo.mkdir()
    def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.PIPE,text=True).strip()
    git('init','-q');git('config','user.name','KTOOL QA Fixture');git('config','user.email','qa@fixture.invalid')
    (repo/'README.md').write_text('TEST_FIXTURE_NOT_ANTIGRAVITY\n');git('add','.');git('commit','-qm','fixture baseline');base=git('rev-parse','HEAD')
    Registry(root/'registry.db');c=ControlStore(root/'registry.db')
    contract=c.propose_contract('CODEX','QA_FIXTURE',{'acceptance_criteria':['isolated browser fixture only']},False);c.approve_contract('CODEX',contract)
    revision=c.publish_revision('CODEX',{'contracts':[contract],'source':'TEST_FIXTURE'})
    c.create_mission('CODEX','QA_FIXTURE_NOT_ANTIGRAVITY',revision,{'sandbox':True,'max_workers':2})
    tasks=[]
    for suffix,owner in [('A','ANTI-01'),('B','ANTI-02')]:
        work=root/('worktree-'+suffix);git('worktree','add','-q','-b','fixture-'+suffix,str(work),base)
        tasks.append({'id':'QA_'+suffix,'team':'QA_TEAM_'+suffix,'owner':owner,'contract_hash':contract,'repo':str(work),'base_sha':base,'allowed_paths':['module-'+suffix.lower()],'acceptance_criteria':['fixture only']})
    c.queue_wave('CODEX','QA_FIXTURE_NOT_ANTIGRAVITY','QA_WAVE',tasks)
    result=c.dispatch('CODEX',ack_timeout_seconds=3600)
    epoch=next(r['epoch'] for r in result['assigned'] if r['id']=='QA_A');c.acknowledge('ANTI-01','QA_A',epoch,contract)
    work=root/'worktree-A';folder=work/'module-a';folder.mkdir();(folder/'fixture.py').write_text('TEST_FIXTURE_VALUE = 1\n')
    subprocess.run(['git','-C',str(work),'add','.'],check=True,capture_output=True);subprocess.run(['git','-C',str(work),'commit','-qm','QA fixture source'],check=True,capture_output=True)
    candidate=subprocess.check_output(['git','-C',str(work),'rev-parse','HEAD'],text=True).strip()
    c.checkpoint('ANTI-01','QA_A',epoch,candidate,['module-a/fixture.py'],{'provenance':'TEST_FIXTURE','verification':'CLAIMED'})
    c.human_request('CODEX','QA_FIXTURE_NOT_ANTIGRAVITY','MERGE_APPROVAL','QA-only pending request; no merge permission')
    return {'root':str(root),'scope':'ISOLATED_QA_FIXTURE_NOT_ANTIGRAVITY','provider_execution':'NOT_EXECUTED','base_sha':base,'candidate_sha':candidate}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args();print(json.dumps(prepare(a.root),indent=2))
