"""Deterministic local worker fixtures: real Git/code/tests/RPC, NEVER Antigravity proof.

All work happens in a disposable directory. No installed tokens or Registry are used.
Run with --out to preserve non-secret logs, commits, diffs and a Git bundle.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
import hashlib
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from threading import Thread
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from registry import Registry, hash_token
from server import handler_factory
from qa_runner import assess


def command(argv, cwd):
    p=subprocess.run(argv,cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
    if p.returncode:
        raise RuntimeError(json.dumps({'argv':argv,'exit':p.returncode,'out':p.stdout,'err':p.stderr}))
    return (p.stdout+p.stderr).strip()


def worker(jobpath):
    job=json.loads(Path(jobpath).read_text())
    repo=Path(job['repo']); started=time.time()
    token=Path(job['credential_file']).read_text()
    def rpc(op,**args):
        req=Request(job['rpc'],data=json.dumps({'op':op,'args':args}).encode(),
                    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urlopen(req,timeout=10) as response:
            result=json.load(response)
            if not result.get('ok'): raise RuntimeError('RPC failed')
            return result['result']
    task=rpc('get_task',tid=job['tid'])
    if task['owner']!=job['owner']: raise RuntimeError('Owner mismatch')
    if job.get('acknowledge'): rpc('acknowledge_feedback',tid=job['tid'],fencing=job['fencing'])
    for relative,content in job['files'].items():
        if not relative.startswith(job['scope']+'/'): raise RuntimeError('Fixture out of scope')
        path=repo/relative; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(content)
    build=[sys.executable,'-B','-m','compileall','-q',job['scope']]
    tests=[sys.executable,'-B','-m','unittest','discover','-s',job['scope'],'-p','test_*.py','-v']
    built=command(build,repo); tested=command(tests,repo)
    command(['git','diff','--check'],repo)
    command(['git','add','--',job['scope']],repo)
    command(['git','commit','-qm','Fixture implementation '+job['tid']+' '+job['round']],repo)
    sha=command(['git','rev-parse','HEAD'],repo)
    paths=command(['git','diff','--name-only',job['base'],sha],repo).splitlines()
    if not paths or not all(p.startswith(job['scope']+'/') for p in paths): raise RuntimeError('Changed path mismatch')
    if command(['git','status','--porcelain'],repo): raise RuntimeError('Dirty fixture')
    log={'provenance':'TEST_HARNESS_NOT_ANTIGRAVITY','owner':job['owner'],'task':job['tid'],
         'commit':sha,'started':started,'ended':time.time(),'build':{'command':build,'exit':0,'stdout':built},
         'tests':{'command':tests,'exit':0,'stdout':tested},'paths':paths}
    Path(job['evidence']).write_text(json.dumps(log,indent=2))
    rpc('checkpoint',tid=job['tid'],fencing=job['fencing'],message='TEST_HARNESS checkpoint '+sha)
    rpc('submit_self_qa',tid=job['tid'],fencing=job['fencing'],commit_sha=sha,changed_paths=paths,
        checks=dict(scope=True,diff=True,regression=True,safety=True),build_status='PASS',test_status='PASS',
        preview_status='NOT_APPLICABLE',evidence_ref=job['evidence'])
    rpc('submit_result',tid=job['tid'],fencing=job['fencing'],commit_sha=sha,
        summary='TEST_HARNESS fixture; no Antigravity execution',build_status='PASS',test_status='PASS',evidence_ref=job['evidence'])


def run(out):
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ktool-v07-e2e-') as temp:
        folder=Path(temp); dbpath=folder/'registry.db'; store=Registry(dbpath)
        tokens={role:secrets.token_urlsafe(40) for role in ('CODEX','ANTI-01','ANTI-02')}
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_factory(store,{r:hash_token(t) for r,t in tokens.items()}))
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            central=folder/'central'; central.mkdir()
            command(['git','init','-q','-b','central'],central)
            command(['git','config','user.name','KTOOL Test Harness'],central)
            command(['git','config','user.email','fixture@localhost'],central)
            (central/'.gitignore').write_text('__pycache__/\n*.pyc\n')
            command(['git','add','.'],central); command(['git','commit','-qm','Disposable baseline'],central)
            base=command(['git','rev-parse','HEAD'],central)
            scopes={'A':'architectural/envelope','B':'documentation/schedules'}
            owners={'A':'ANTI-01','B':'ANTI-02'}; fences={}; repos={}; jobs={}
            for tid in ('A','B'):
                repo=folder/tid;repos[tid]=repo
                command(['git','worktree','add','-q','-b','fixture-'+tid,str(repo)],central)
                store.create_task('CODEX',tid,'TEST_HARNESS '+tid,scopes[tid],
                    'TEST_HARNESS only. A: area rejects negative width/height; B: schedule totals stable keys.',base,
                    wave_id='V07_HARNESS',requires_preview=False)
                fences[tid]=store.assign('CODEX',tid,owners[tid])['fencing']
                cred=folder/(owners[tid]+'.credential');cred.write_text(tokens[owners[tid]])
                jobs[tid]={'repo':str(repo),'tid':tid,'scope':scopes[tid],'owner':owners[tid],'fencing':fences[tid],
                    'credential_file':str(cred),'rpc':f'http://127.0.0.1:{server.server_port}/rpc','base':base,'round':'1',
                    'evidence':str(out/(tid+'-selfqa-round1.json'))}
            jobs['A']['files']={scopes['A']+'/area.py':'def area(width, height):\n    return width * height\n',
                scopes['A']+'/test_area.py':'import unittest\nfrom area import area\nclass AreaTest(unittest.TestCase):\n    def test_positive(self): self.assertEqual(area(2,3),6)\n'}
            jobs['B']['files']={scopes['B']+'/schedule.py':'def totals(rows):\n    result = {}\n    for key, value in rows:\n        result[key] = result.get(key, 0) + value\n    return dict(sorted(result.items()))\n',
                scopes['B']+'/test_schedule.py':'import unittest\nfrom schedule import totals\nclass ScheduleTest(unittest.TestCase):\n    def test_totals(self): self.assertEqual(totals([(\"b\",2),(\"a\",1),(\"b\",3)]),{\"a\":1,\"b\":5})\n'}
            def launch(job):
                jobpath=folder/(job['tid']+'-job.json');jobpath.write_text(json.dumps(job))
                return command([sys.executable,str(Path(__file__).resolve()),'--worker',str(jobpath)],ROOT)
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(launch,[jobs['A'],jobs['B']]))
            # Trusted oracle is outside all worker worktrees; fixtures cannot revise it by scope.
            oracle=folder/'supervisor_oracle.py'
            oracle.write_text('import importlib.util,sys\np=sys.argv[1]\ns=importlib.util.spec_from_file_location("target",p)\nm=importlib.util.module_from_spec(s);s.loader.exec_module(m)\nif hasattr(m,"area"):\n    assert m.area(2,3)==6\n    for width,height in [(-1,2),(2,-1)]:\n        try: m.area(width,height)\n        except ValueError: pass\n        else: raise AssertionError("AREA-NEG: negative dimension must raise ValueError")\nelse:\n    r=m.totals([("b",2),("a",1),("b",3)])\n    assert list(r)==["a","b"] and r=={"a":1,"b":5}\n')
            profiles={}
            for tid,module in [('A','area.py'),('B','schedule.py')]:
                profile=folder/(tid+'-qa-profile.json');profiles[tid]=profile
                profile.write_text(json.dumps({'build':[sys.executable,'-B','-m','compileall','-q',scopes[tid]],
                    'tests':[sys.executable,'-B',str(oracle),str(repos[tid]/scopes[tid]/module)],'allowed_paths':[scopes[tid]]}))
            initialA=assess(dbpath,'A',repos['A'],profiles['A']); passedB=assess(dbpath,'B',repos['B'],profiles['B'])
            def save_qa(result, filename):
                with store.connect() as conn:
                    row=dict(conn.execute('SELECT * FROM qa_evidence WHERE id=?',(result['evidence_id'],)).fetchone())
                (out/filename).write_text(json.dumps(row,indent=2))
            save_qa(initialA,'A-independent-round1.json')
            save_qa(passedB,'B-independent-final.json')
            assert initialA['result']=='FAIL' and passedB['result']=='PASS'
            issue={'id':'AREA-NEG','file':scopes['A']+'/area.py','severity':'high',
                   'expected':'negative width raises ValueError','actual':'negative product returned','evidence':'trusted oracle exit 1'}
            store.review_task('CODEX','A','CHANGES_REQUESTED','Negative dimension validation violates contract',
                              'A-independent-round1.json',issues=[issue])
            jobs['A']['acknowledge']=True;jobs['A']['round']='2';jobs['A']['evidence']=str(out/'A-selfqa-round2.json')
            jobs['A']['files'][scopes['A']+'/area.py']='def area(width, height):\n    if width < 0 or height < 0:\n        raise ValueError("negative dimension")\n    return width * height\n'
            jobs['A']['files'][scopes['A']+'/test_area.py']+='    def test_negative(self):\n        with self.assertRaises(ValueError): area(-1,2)\n'
            jobs['A']['files'][scopes['A']+'/test_area.py']+='    def test_negative_height(self):\n        with self.assertRaises(ValueError): area(2,-1)\n'
            launch(jobs['A'])
            passedA=assess(dbpath,'A',repos['A'],profiles['A']);assert passedA['result']=='PASS'
            save_qa(passedA,'A-independent-final.json')
            for tid in ('A','B'):
                store.review_task('CODEX',tid,'PASS_CODE_REVIEW','TEST_HARNESS scope diff and independent oracle verified; not an AI source review',
                                  tid+'-independent-final.json',True,True)
            integration=folder/'integration'
            command(['git','worktree','add','-q','-b','fixture-integration',str(integration),base],central)
            heads={tid:command(['git','rev-parse','HEAD'],repos[tid]) for tid in ('A','B')}
            for tid in ('A','B'):
                sequence=command(['git','rev-list','--reverse',base+'..'+heads[tid]],central).splitlines()
                command(['git','cherry-pick',*sequence],integration)
            outputs={}
            for tid,module in [('A','area.py'),('B','schedule.py')]:
                outputs[tid]=command([sys.executable,'-B',str(oracle),str(integration/scopes[tid]/module)],integration)
                outputs[tid+'-regression']=command([sys.executable,'-B','-m','unittest','discover','-s',scopes[tid],'-v'],integration)
            (out/'integration-test.log').write_text(json.dumps(outputs,indent=2))
            integration_sha=command(['git','rev-parse','HEAD'],integration)
            assert not command(['git','status','--porcelain'],integration)
            command(['git','fsck','--full'],central)
            command(['git','bundle','create',str(out/'fixture-history.bundle'),'--all'],central)
            command(['git','diff',base,integration_sha,'--output='+str(out/'fixture-implementation.patch')],central)
            with store.connect() as conn:
                qa=[dict(row) for row in conn.execute('SELECT task_id,qa_round,commit_sha,result,evidence_json FROM qa_evidence')]
            (out/'independent-qa.json').write_text(json.dumps(qa,indent=2))
            history=store.feedback_history('CODEX','A')
            (out/'feedback-history.json').write_text(json.dumps(history,indent=2))
            first=json.loads((out/'A-selfqa-round1.json').read_text());second=json.loads((out/'B-selfqa-round1.json').read_text())
            overlap=max(first['started'],second['started']) < min(first['ended'],second['ended'])
            result={'status':'PASS','provenance':'TEST_HARNESS_NOT_ANTIGRAVITY','base_sha':base,'commits':heads,
                    'integration_sha':integration_sha,'initial_A':'FAIL','corrected_A':'PASS','B':'PASS',
                    'feedback_resubmission_cycles':1,'fixture_processes_overlapped':overlap,
                    'real_teamwork_concurrency':'NOT_EXECUTED','revit_runtime':'NOT_EXECUTED'}
            (out/'result.json').write_text(json.dumps(result,indent=2))
            return result
        finally:
            server.shutdown();server.server_close();thread.join()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker');parser.add_argument('--out',type=Path)
    options=parser.parse_args()
    if options.worker: worker(options.worker)
    elif options.out: print(json.dumps(run(options.out.resolve()),indent=2))
    else: parser.error('--out required')
