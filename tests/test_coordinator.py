import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import sqlite3
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from registry import Registry, hash_token, collide
from server import handler_factory

class TestDualDev(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.db=Registry(Path(self.tmp.name)/'registry.db')
        self.tokens={'CODEX':'codex-token','ANTI-01':'anti1-token','ANTI-02':'anti2-token'}
        self.httpd=ThreadingHTTPServer(('127.0.0.1',0),handler_factory(self.db,{k:hash_token(v) for k,v in self.tokens.items()}))
        self.addCleanup(self.httpd.server_close)
        self.thread=Thread(target=self.httpd.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.httpd.shutdown)
        self.url=f'http://127.0.0.1:{self.httpd.server_port}/rpc'
        self.sha='a'*40
    def call(self, role, op, **args):
        data=json.dumps({'op':op,'args':args}).encode()
        headers={'Content-Type':'application/json'}
        if role:headers['Authorization']='Bearer '+self.tokens[role]
        try:
            with urlopen(Request(self.url,data=data,headers=headers),timeout=4) as response:
                return response.status,json.load(response)
        except HTTPError as error:return error.code,json.load(error)
    def create(self,tid,scope,wave='WAVE1'):
        return self.call('CODEX','create_task',tid=tid,title=f'Task {tid}',scope=scope,
                         contract='Implement bounded code with regression tests',base_sha=self.sha,wave_id=wave)
    def ass(self,tid,who):return self.call('CODEX','assign_task',tid=tid,owner=who)
    def selfqa(self,who,tid,fence,commit='b'*40,build='PASS',test='PASS',paths=None):
        return self.call(who,'submit_self_qa',tid=tid,fencing=fence,commit_sha=commit,
            changed_paths=paths or [self.db.get_task('CODEX',tid)['scope']+'/file.cs'],
            checks={'scope':True,'diff':True,'regression':True,'safety':True},
            build_status=build,test_status=test,preview_status='NOT_EXECUTED',
            evidence_ref='logs/worker-self-qa.json')
    def submit(self,who,tid,fence,commit='b'*40):
        return self.call(who,'submit_result',tid=tid,fencing=fence,commit_sha=commit,
            summary='Bounded implementation with worker self QA evidence',
            build_status='PASS',test_status='PASS',evidence_ref='logs/worker-result.json')
    def evidence(self,tid):
        t=self.db.get_task('CODEX',tid)
        sha=json.loads(t['result_json'])['commit_sha']
        paths=json.loads(t['self_qa_json'])['changed_paths']
        return self.db.register_local_qa(tid,t['qa_round'],sha,True,True,paths,0,0,
          {'git_verified':True,'path_check':True,'TEST_ONLY':True})
    def codexpass(self,tid):
        self.evidence(tid)
        return self.call('CODEX','review_task',tid=tid,decision='PASS_CODE_REVIEW',
            report='Independently verified diff, build, tests, preview from logs',
            evidence_ref='qa/codex-build-review.md',build_verified=True,tests_verified=True,
            preview_verified=True,preview_evidence_ref='qa/codex-preview.png')
    def codexrework(self,tid,report='Expected geometry differs from observed placement'):
        return self.call('CODEX','review_task',tid=tid,decision='CHANGES_REQUESTED',
            report=report,evidence_ref='qa/codex-feedback.md',
            issues=[{'id':'GEO-001','file':'arch/file.cs','expected':'Correct geometry','actual':'Incorrect geometry'}])
    def test_roles(self):
        self.assertEqual(self.call(None,'status')[0],401)
        self.assertEqual(self.call('ANTI-01','create_task',tid='T',title='x',scope='A',contract='x',base_sha=self.sha)[0],403)
        self.assertEqual(self.call('ANTI-02','create_task',tid='T',title='x',scope='A',contract='x',base_sha=self.sha)[0],403)
        self.assertEqual(self.call('ANTI-02','report')[0],403)
    def test_dual_parallel_development(self):
        self.create('ARCH1','Architectural/Room')
        self.create('MEP1','MEP/Openings')
        aa=self.ass('ARCH1','ANTI-01');bb=self.ass('MEP1','ANTI-02')
        self.assertEqual(aa[0],bb[0]);self.assertEqual(aa[0],200)
        self.assertEqual(self.call('ANTI-01','get_task',tid='ARCH1')[0],200)
        self.assertEqual(self.call('ANTI-02','get_task',tid='MEP1')[0],200)
        self.assertEqual(self.call('ANTI-01','get_task',tid='MEP1')[0],403)
        self.assertEqual(self.call('ANTI-02','get_task',tid='ARCH1')[0],403)
    def test_simultaneous_assign_no_double_lock(self):
        self.create('A','architectural/door')
        self.create('B','architectural')
        with ThreadPoolExecutor(max_workers=2) as pool:
            r=list(pool.map(lambda pair:self.ass(*pair)[0],[('A','ANTI-01'),('B','ANTI-02')]))
        self.assertEqual(sorted(r),[200,409])
    def test_conflict_on_parent_child(self):
        self.create('A','architectural/door');self.create('B','architectural')
        self.ass('A','ANTI-01')
        code,result=self.ass('B','ANTI-02')
        self.assertEqual(code,409);self.assertIn('CANT_EDIT',result['error'])
        self.assertFalse(collide('a/b','a/bc'))
    def test_agent_busy(self):
        self.create('A','arch');self.create('B','mep')
        self.ass('A','ANTI-01')
        self.assertEqual(self.ass('B','ANTI-01')[0],409)
        self.assertEqual(self.ass('B','ANTI-02')[0],200)
    def test_workers_submit_and_codex_reviews(self):
        for owner,tid,scope in [('ANTI-01','A','arch'),('ANTI-02','B','mep')]:
            self.create(tid,scope)
            tok=self.ass(tid,owner)[1]['result']['fencing']
            self.assertEqual(self.call(owner,'checkpoint',tid=tid,fencing=tok,message='2 files changed; test pending')[0],200)
            self.assertEqual(self.submit(owner,tid,tok)[0],403)
            self.assertEqual(self.selfqa(owner,tid,tok)[0],200)
            self.assertEqual(self.submit(owner,tid,tok)[0],200)
            self.assertEqual(self.call(owner,'checkpoint',tid=tid,fencing=tok,message='should fail')[0],403)
            self.assertEqual(self.call(owner,'review_task',tid=tid,decision='PASS_CODE_REVIEW',report='fake',evidence_ref='fake')[0],403)
            self.assertEqual(self.codexpass(tid)[0],200)
        report=self.call('CODEX','report',wave_id='WAVE1')[1]['result']
        self.assertEqual(report['counts']['CODE_REVIEWED'],2)
        self.assertIn('Revit host: NOT_EXECUTED',report['markdown'])
        self.assertIn('Self-QA: RECORDED',report['markdown'])
    def test_pass_requires_independent_qa_gate(self):
        self.create('X','x');tok=self.ass('X','ANTI-01')[1]['result']['fencing']
        self.selfqa('ANTI-01','X',tok);self.submit('ANTI-01','X',tok)
        code,result=self.call('CODEX','review_task',tid='X',decision='PASS_CODE_REVIEW',
            report='No separate QA executed yet',evidence_ref='reports/review.md')
        self.assertEqual(code,409);self.assertIn('QA_GATE',result['error'])
        code,result=self.call('CODEX','review_task',tid='X',decision='PASS_CODE_REVIEW',
            report='Did build and tests, preview missing',evidence_ref='reports/review.md',
            build_verified=True,tests_verified=True)
        self.assertEqual(code,409);self.assertIn('INDEPENDENT_LOCAL_QA_EVIDENCE_REQUIRED',result['error'])
        self.evidence('X')
        code,result=self.call('CODEX','review_task',tid='X',decision='PASS_CODE_REVIEW',
            report='Did build and tests, preview missing',evidence_ref='reports/review.md',
            build_verified=True,tests_verified=True)
        self.assertEqual(code,409);self.assertIn('PREVIEW_GATE',result['error'])
    def test_review_correction_rework(self):
        self.create('A','arch');tok=self.ass('A','ANTI-01')[1]['result']['fencing']
        self.selfqa('ANTI-01','A',tok,commit='a'*40);self.submit('ANTI-01','A',tok,commit='a'*40)
        self.assertEqual(self.call('CODEX','review_task',tid='A',decision='CHANGES_REQUESTED',
            report='Fix invalid element id handling',evidence_ref='logs/review-1.md')[0],409)
        code,r=self.codexrework('A')
        self.assertEqual(code,200);self.assertEqual(r['result']['state'],'REWORK_REQUIRED')
        self.assertEqual(self.call('ANTI-01','checkpoint',tid='A',fencing=tok,message='should wait')[0],403)
        self.assertEqual(self.call('ANTI-02','acknowledge_feedback',tid='A',fencing=tok)[0],403)
        self.assertEqual(self.call('ANTI-01','acknowledge_feedback',tid='A',fencing=tok)[0],200)
        self.assertEqual(self.db.get_task('CODEX','A')['qa_round'],2)
        self.assertEqual(self.call('ANTI-01','checkpoint',tid='A',fencing=tok,message='fix in progress')[0],200)
        self.assertEqual(self.selfqa('ANTI-01','A',tok,commit='b'*40)[0],200)
        self.assertEqual(self.submit('ANTI-01','A',tok,commit='b'*40)[0],200)
        self.assertEqual(self.codexpass('A')[0],200)
        history=self.call('ANTI-01','feedback_history',tid='A')
        self.assertEqual(history[0],200)
        self.assertEqual([x['cycle'] for x in history[1]['result']['history']],[1,2])
    def test_closed_release_requires_codex_and_confirmation(self):
        self.create('A','arch');tok=self.ass('A','ANTI-01')[1]['result']['fencing']
        self.selfqa('ANTI-01','A',tok);self.submit('ANTI-01','A',tok)
        self.assertEqual(self.call('CODEX','close_task',tid='A',integration_sha='c'*40,source_stopped=True)[0],409)
        self.assertEqual(self.codexpass('A')[0],200)
        self.assertEqual(self.call('CODEX','close_task',tid='A',integration_sha='c'*40,source_stopped=False)[0],409)
        self.assertEqual(self.call('ANTI-01','close_task',tid='A',integration_sha='c'*40,source_stopped=True)[0],403)
        self.assertEqual(self.call('CODEX','close_task',tid='A',integration_sha='c'*40,source_stopped=True)[0],200)
        self.create('B','arch');self.assertEqual(self.ass('B','ANTI-02')[0],200)
    def test_freeze_keeps_lock_and_blocks_worker(self):
        self.create('A','architectural/door');tok=self.ass('A','ANTI-01')[1]['result']['fencing']
        self.call('CODEX','freeze',tid='A',reason='pause for manual review')
        self.assertEqual(self.call('ANTI-01','checkpoint',tid='A',fencing=tok,message='stale')[0],403)
        self.create('B','architectural')
        self.assertEqual(self.ass('B','ANTI-02')[0],409)
    def test_two_worker_contact_not_teamwork_proof(self):
        for role in ('ANTI-01','ANTI-02'):
            self.assertEqual(self.call(role,'heartbeat',event='WORKING')[0],200)
        snap=self.db.dashboard_snapshot('CODEX')
        self.assertTrue(all(a['mcp_recent'] for a in snap['agents']))
        self.assertTrue(all(a['teamwork']=='NOT_VERIFIED' for a in snap['agents']))
    def test_nonworker_qa_prohibited(self):
        self.create('A','arch');self.ass('A','ANTI-01')
        self.assertEqual(self.call('ANTI-02','qa_report',tid='A',qa_status='PASS_CODE_REVIEW',report='bad')[0],400)
    def test_invalid_scope_and_sha(self):
        self.assertEqual(self.create('A','../escape')[0],400)
        self.assertEqual(self.call('CODEX','create_task',tid='B',title='B',scope='arch',contract='x',base_sha='master')[0],400)
    def test_frozen_outside_scope_claim_retains_lock(self):
        self.create('A','architectural/windows')
        tok=self.ass('A','ANTI-01')[1]['result']['fencing']
        c,r=self.selfqa('ANTI-01','A',tok,paths=['architectural/windows/A.cs','rebar/C.cs'])
        self.assertEqual(c,200)
        self.assertEqual(r['result']['state'],'FROZEN')
        self.assertEqual(self.db.get_task('CODEX','A')['state'],'FROZEN')
        self.create('B','architectural')
        self.assertEqual(self.ass('B','ANTI-02')[0],409)
    def test_failed_self_qa_cannot_sync(self):
        self.create('A','arch');tok=self.ass('A','ANTI-01')[1]['result']['fencing']
        res=self.selfqa('ANTI-01','A',tok,build='FAIL')
        self.assertEqual(res[1]['result']['state'],'RUNNING')
        self.assertEqual(self.submit('ANTI-01','A',tok)[0],403)
        self.assertEqual(self.selfqa('ANTI-01','A',tok)[0],200)
        self.assertEqual(self.submit('ANTI-01','A',tok,commit='c'*40)[0],409)
        self.assertEqual(self.submit('ANTI-01','A',tok)[0],200)
    def test_active_owner_exclusive_during_rework(self):
        self.create('A','architectural/windows');tok=self.ass('A','ANTI-01')[1]['result']['fencing']
        self.selfqa('ANTI-01','A',tok);self.submit('ANTI-01','A',tok)
        self.codexrework('A')
        self.create('B','architectural/windows')
        self.assertEqual(self.ass('B','ANTI-02')[0],409)
        self.call('ANTI-01','acknowledge_feedback',tid='A',fencing=tok)
        self.assertEqual(self.ass('B','ANTI-02')[0],409)
    def test_repeated_feedback_escalation_recommended(self):
        self.create('A','arch');fence=self.ass('A','ANTI-01')[1]['result']['fencing']
        for cycle in range(1,4):
            commit=hex(cycle)[2:]*40
            self.assertEqual(self.selfqa('ANTI-01','A',fence,commit=commit)[0],200)
            self.assertEqual(self.submit('ANTI-01','A',fence,commit=commit)[0],200)
            code,r=self.codexrework('A')
            self.assertEqual(code,200)
            self.assertEqual(r['result']['escalation_recommended'],cycle>=3)
            if cycle<3:
                self.assertEqual(self.call('ANTI-01','acknowledge_feedback',tid='A',fencing=fence)[0],200)
            else:
                self.assertTrue(r['result']['no_progress_freeze'])
                self.assertEqual(self.call('ANTI-01','acknowledge_feedback',tid='A',fencing=fence)[0],403)
        self.assertEqual(self.db.get_task('CODEX','A')['state'],'FROZEN')
        self.assertEqual(self.db.get_task('CODEX','A')['qa_round'],3)
        self.assertEqual(self.db.get_task('CODEX','A')['rework_count'],3)
        self.assertEqual(self.db.get_task('CODEX','A')['fencing'],fence)
    def test_review_not_applicable_requires_explicit_configuration(self):
        self.call('CODEX','create_task',tid='A',title='Doc task',scope='docs',contract='Pure refactor of text docs',base_sha=self.sha,requires_preview=False)
        f=self.ass('A','ANTI-01')[1]['result']['fencing']
        self.selfqa('ANTI-01','A',f);self.submit('ANTI-01','A',f)
        self.evidence('A')
        code,r=self.call('CODEX','review_task',tid='A',decision='PASS_CODE_REVIEW',report='Independent build and tests confirmed, no 3D preview is applicable',evidence_ref='qa/verified.txt',build_verified=True,tests_verified=True)
        self.assertEqual(code,200)
    def test_v03_schema_upgrade(self):
        old=Path(self.tmp.name)/'legacy.db'
        from contextlib import closing
        with closing(sqlite3.connect(old)) as db:
            with db:
                db.execute('CREATE TABLE tasks (id TEXT PRIMARY KEY,title TEXT,scope TEXT,contract TEXT,state TEXT,owner TEXT,base_sha TEXT,fencing INTEGER,checkpoint TEXT,checkpoint_at TEXT,qa_result TEXT,qa_actor TEXT,updated TEXT)')
                db.execute("INSERT INTO tasks VALUES('LEGACY','Old','old','Contract','QUEUED',NULL,?,0,NULL,NULL,NULL,NULL,'2026-10-17')",(self.sha,))
        upgraded=Registry(old)
        self.assertEqual(upgraded.get_task('CODEX','LEGACY')['wave_id'],'PILOT')
        self.assertEqual(upgraded.get_task('CODEX','LEGACY')['title'],'Old')

if __name__=='__main__':unittest.main()
