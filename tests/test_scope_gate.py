"""Scope gate tests use actual immutable Git trees, including index-only symlinks."""
import subprocess
import json
import os
import sys
from registry import Registry
from qa_runner import assess
import tempfile
from pathlib import Path
import unittest
from ci_scope_gate import verify

class ScopeGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.repo=Path(self.tmp.name)
        self.git('init','-q'); self.git('config','user.name','Scope QA'); self.git('config','user.email','scope@example.test')
        (self.repo/'module').mkdir()
        (self.repo/'module/a').write_text('base')
        (self.repo/'module/tests').mkdir(); (self.repo/'module/tests/test.txt').write_text('test')
        self.commit(); self.base=self.git('rev-parse','HEAD')
    def git(self,*args):
        return subprocess.run(['git',*args],cwd=self.repo,capture_output=True,text=True,check=True).stdout.strip()
    def commit(self):
        self.git('add','-A'); self.git('commit','-qm','fixture')
        return self.git('rev-parse','HEAD')
    def gate(self,head,**kw): return verify(self.repo,self.base,head,'module',**kw)
    def test_allowed_modification(self):
        (self.repo/'module/a').write_text('new'); self.assertTrue(self.gate(self.commit())['pass'])
    def test_out_of_scope(self):
        (self.repo/'outside').write_text('new'); result=self.gate(self.commit())
        self.assertFalse(result['pass']); self.assertTrue(result['quarantine'])
    def test_protected_fixture(self):
        (self.repo/'module/tests/test.txt').write_text('weakened')
        self.assertFalse(self.gate(self.commit(),protected_paths=['module/tests'])['pass'])
    def test_allowed_paths_narrow_scope(self):
        (self.repo/'module/a').write_text('new')
        self.assertFalse(self.gate(self.commit(),allowed_paths=['module/tests'])['pass'])
    def test_delete_records(self):
        (self.repo/'module/a').unlink(); r=self.gate(self.commit())
        self.assertTrue(r['pass']); self.assertEqual(r['entries'][0]['status'],'D')
    def test_rename_outside_records_both_paths(self):
        self.git('mv','module/a','outside'); r=self.gate(self.commit())
        self.assertFalse(r['pass']); self.assertIn('module/a',r['changed_paths']); self.assertIn('outside',r['changed_paths'])
    def test_index_symlink_without_windows_privilege(self):
        blob=self.git('hash-object','-w','module/a')
        self.git('update-index','--add','--cacheinfo','120000,'+blob+',module/link')
        self.git('commit','-qm','link'); self.assertFalse(self.gate(self.git('rev-parse','HEAD'))['pass'])
    def test_unrelated_base(self):
        self.git('checkout','--orphan','other'); self.git('commit','-qm','orphan')
        self.assertFalse(self.gate(self.git('rev-parse','HEAD'))['pass'])
    def test_future_or_stale_reversed_base(self):
        (self.repo/'module/a').write_text('new'); head=self.commit()
        self.assertFalse(verify(self.repo,head,self.base,'module')['pass'])
    def test_false_worker_claim_quarantines_actual_outside_diff(self):
        (self.repo/'module/a').write_text('implementation')
        (self.repo/'outside').write_text('unauthorized')
        head=self.commit()
        dbpath=self.repo.parent/(self.repo.name+'-qa.db')
        self.addCleanup(lambda: dbpath.unlink(missing_ok=True))
        store=Registry(dbpath)
        store.create_task('CODEX','A','Scope fixture','module','do only assigned files',self.base,requires_preview=False)
        fence=store.assign('CODEX','A','ANTI-01')['fencing']
        store.submit_self_qa('ANTI-01','A',fence,head,['module/a'],
            dict(scope=True,diff=True,regression=True,safety=True),'PASS','PASS','NOT_APPLICABLE','evidence/self.json')
        store.submit_result('ANTI-01','A',fence,head,'claimed in scope','PASS','PASS','evidence/result.json')
        profile=self.repo.parent/(self.repo.name+'-profile.json')
        self.addCleanup(lambda: profile.unlink(missing_ok=True))
        profile.write_text(json.dumps({'build':[sys.executable,'-c','raise Exception("must not run")'],
                                       'tests':[sys.executable,'-c','raise Exception("must not run")']}))
        result=assess(dbpath,'A',self.repo,profile)
        self.assertEqual(result['result'],'FAIL')
        self.assertEqual(result['quarantine'],'FROZEN')
        self.assertEqual(store.get_task('CODEX','A')['state'],'FROZEN')
        with store.connect() as connection:
            locks=connection.execute('SELECT * FROM locks WHERE task_id=?',('A',)).fetchall()
            evidence=connection.execute('SELECT evidence_json FROM qa_evidence WHERE task_id=?',('A',)).fetchone()
        self.assertEqual(len(locks),1); self.assertEqual(locks[0]['state'],'FROZEN')
        payload=json.loads(evidence['evidence_json'])
        self.assertEqual(payload['build']['error'],'GIT_PREFLIGHT_FAILED')
        self.assertIn('outside',payload['diff'])
        self.assertEqual(self.git('rev-parse','HEAD'),head)

    @unittest.skipUnless(os.name=='nt','NTFS junction test requires Windows')
    def test_physical_windows_junction_is_rejected(self):
        target=tempfile.TemporaryDirectory(); self.addCleanup(target.cleanup)
        link=self.repo/'module/junction'
        subprocess.run(['cmd','/c','mklink','/J',str(link),target.name],capture_output=True,check=True)
        self.addCleanup(lambda: os.rmdir(link) if link.exists() else None)
        (self.repo/'module/a').write_text('implementation')
        result=self.gate(self.commit())
        self.assertFalse(result['pass'])
        self.assertTrue(any('PHYSICAL_REPARSE_POINT' in message for message in result['errors']))

    def test_mutable_ref_rejected(self):
        self.assertFalse(verify(self.repo,'HEAD','HEAD','module')['pass'])
    def test_traversal_policy_rejected(self):
        (self.repo/'module/a').write_text('new')
        self.assertFalse(self.gate(self.commit(),allowed_paths=['module/../outside'])['pass'])

if __name__=='__main__': unittest.main()
