"""Actual Git transactions; owner authority below is explicitly a TEST FIXTURE."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import json
import sqlite3
from contextlib import closing
from transaction_sync import TransactionSync
from trust_vault import digest

class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.repo=Path(self.temp.name)/'repo';self.repo.mkdir()
        self.git('init','-q');self.git('config','user.name','Fixture');self.git('config','user.email','fixture@example.test')
        (self.repo/'base').write_text('base');self.git('add','.');self.git('commit','-qm','base');self.base=self.git('rev-parse','HEAD')
        self.central='refs/ktool-disposable/central';self.git('update-ref',self.central,self.base)
        self.candidates=[]
        for scope in ('a','b'):
            self.git('checkout','-qb','worker-'+scope,self.base)
            (self.repo/scope).mkdir();(self.repo/scope/'value.py').write_text('VALUE='+('2' if scope=='a' else '3')+'\n')
            self.git('add','.');self.git('commit','-qm',scope)
            self.candidates.append({'sha':self.git('rev-parse','HEAD'),'scope':scope,'base_sha':self.base})
        self.git('checkout','--detach',self.base)
        self.commands=[[sys.executable,'-B','-c','from a.value import VALUE as A; from b.value import VALUE as B; assert A+B==5']]
    def git(self,*args):
        return subprocess.run(['git',*args],cwd=self.repo,capture_output=True,text=True,check=True).stdout.strip()
    def make(self,central=None):
        txn=TransactionSync(self.repo,central or self.central,self.base,self.candidates,'checkpoint-1',{'qa_commands_digest':digest(self.commands)})
        def cleanup():
            if txn.workspace:
                subprocess.run(['git','worktree','remove','--force',str(txn.workspace)],cwd=self.repo,capture_output=True)
                shutil.rmtree(txn.workspace.parent,ignore_errors=True)
        self.addCleanup(cleanup)
        return txn
    def ready(self,txn):
        self.assertEqual(txn.prepare()['state'],'PREPARE');self.assertEqual(txn.validate()['state'],'VALIDATE')
        self.assertEqual(txn.integration_qa(self.commands)['state'],'INTEGRATION_QA');txn.request_approval()
    def approve(self,token,binding):
        self.assertEqual(token,'OWNER_TEST_FIXTURE')
        return {'decision':'APPROVE','principal_role':'OWNER','binding_digest':digest(binding),'fixture':True}
    def test_combined_qa_and_atomic_disposable_commit(self):
        txn=self.make();self.ready(txn)
        result=txn.commit('OWNER_TEST_FIXTURE',self.approve)
        self.assertEqual(result['state'],'COMMIT');self.assertFalse(result['production_trusted'])
        self.assertEqual(self.git('rev-parse',self.central),txn.integration_sha)
        for scope,candidate in zip(('a','b'),self.candidates):self.assertEqual(self.git('rev-parse','worker-'+scope),candidate['sha'])
    def test_owner_required_worker_cannot_approve(self):
        txn=self.make();self.ready(txn);self.assertEqual(txn.commit()['status'],'BLOCKED')
        result=txn.commit('worker',lambda *_:{'decision':'APPROVE','principal_role':'ANTI-01'})
        self.assertEqual(result['state'],'ABORT');self.assertEqual(self.git('rev-parse',self.central),self.base)
    def test_production_central_write_blocked(self):
        ref='refs/heads/production-central';self.git('update-ref',ref,self.base)
        txn=self.make(ref);self.ready(txn)
        self.assertEqual(txn.commit('OWNER_TEST_FIXTURE',self.approve)['status'],'BLOCKED')
        self.assertEqual(self.git('rev-parse',ref),self.base)
    def test_central_advance_after_qa_atomic_abort(self):
        txn=self.make();self.ready(txn);advanced=self.candidates[0]['sha'];self.git('update-ref',self.central,advanced,self.base)
        result=txn.commit('OWNER_TEST_FIXTURE',self.approve)
        self.assertEqual(result['state'],'ABORT');self.assertEqual(self.git('rev-parse',self.central),advanced)
        self.assertEqual(result['checkpoint'],'checkpoint-1')
    def test_failed_qa_aborts_central_unchanged(self):
        bad=[[sys.executable,'-c','raise RuntimeError("regression")']]
        txn=self.make();txn.scope_policy['qa_commands_digest']=digest(bad);txn.prepare();txn.validate()
        self.assertEqual(txn.integration_qa(bad)['state'],'ABORT');self.assertEqual(self.git('rev-parse',self.central),self.base)
    def test_actual_git_cherry_pick_conflict(self):
        # Two different disjoint modules can still conflict in commit metadata/tree
        # if a controller attempts an unrelated preexisting candidate sequence.
        txn=self.make();txn.prepare();txn.validate()
        original=txn.git
        def with_conflict(*args,**kw):
            if args and args[0]=='cherry-pick' and kw.get('cwd'):
                work=Path(kw['cwd']);(work/'a').mkdir(exist_ok=True);(work/'a/value.py').write_text('VALUE=99\n')
                original('add','a/value.py',cwd=work);original('commit','-qm','conflicting local integration change',cwd=work)
            return original(*args,**kw)
        txn.git=with_conflict
        r=txn.integration_qa(self.commands)
        self.assertEqual(r['state'],'ABORT');self.assertIn('GIT_FAILED cherry-pick',r['reason'])
        self.assertEqual(self.git('rev-parse',self.central),self.base)
    def test_scope_violation_aborts_before_qa(self):
        self.candidates[0]['scope']='other';txn=self.make();txn.prepare()
        self.assertEqual(txn.validate()['state'],'ABORT');self.assertEqual(self.git('rev-parse',self.central),self.base)

    def test_reconstruct_approval_pending_then_atomic_cas_commit(self):
        txn=self.make();self.ready(txn)
        recovered=TransactionSync.recover(txn.journal_db,txn.transaction_id)
        self.assertIsNot(txn,recovered)
        self.assertEqual(recovered.state,'APPROVAL_PENDING')
        self.assertEqual(recovered.integration_sha,txn.integration_sha)
        self.assertEqual(recovered.approval_binding,txn.approval_binding)
        self.assertEqual(recovered.commit('OWNER_TEST_FIXTURE',self.approve)['state'],'COMMIT')
        durable=TransactionSync.load(txn.journal_db,txn.transaction_id)
        self.assertEqual(durable.state,'COMMIT')
        self.assertEqual(self.git('rev-parse',self.central),durable.integration_sha)
        self.assertTrue(txn.journal_db.is_relative_to((self.repo/'.git').resolve()))

    def test_reconstruct_approval_pending_rejects_central_cas_change(self):
        txn=self.make();self.ready(txn)
        advanced=self.candidates[0]['sha'];self.git('update-ref',self.central,advanced,self.base)
        recovered=TransactionSync.load(txn.journal_db,txn.transaction_id)
        self.assertEqual(recovered.commit('OWNER_TEST_FIXTURE',self.approve)['state'],'ABORT')
        self.assertEqual(self.git('rev-parse',self.central),advanced)
        self.assertEqual(TransactionSync.load(txn.journal_db,txn.transaction_id).state,'ABORT')

    def test_real_process_exit_before_cherry_pick_recovers_abort_without_replay(self):
        txn=self.make();txn.prepare();txn.validate()
        source=Path(__file__).resolve().parents[1]
        code='''import json,os,sys
sys.path.insert(0,sys.argv[1])
from transaction_sync import TransactionSync
txn=TransactionSync.load(sys.argv[2],sys.argv[3])
original=txn.git
def stop_before_pick(*args,**kwargs):
    if args[0]=='cherry-pick': os._exit(17)
    return original(*args,**kwargs)
txn.git=stop_before_pick
txn.integration_qa(json.loads(sys.argv[4]))
'''
        process=subprocess.run([sys.executable,'-B','-c',code,str(source),str(txn.journal_db),
                                txn.transaction_id,json.dumps(self.commands)],capture_output=True,timeout=30)
        self.assertEqual(process.returncode,17,process.stderr.decode(errors='replace'))
        with closing(sqlite3.connect(txn.journal_db)) as db:
            self.assertEqual(db.execute('SELECT state FROM cc_sync_transactions WHERE id=?',(txn.transaction_id,)).fetchone()[0],
                             'INTEGRATION_QA_IN_PROGRESS')
        recovered=TransactionSync.recover(txn.journal_db,txn.transaction_id)
        txn.workspace=recovered.workspace
        self.assertEqual(recovered.state,'ABORT')
        self.assertTrue(recovered.history[-1]['return_to_owner'])
        self.assertEqual(recovered.history[-1]['checkpoint'],'checkpoint-1')
        self.assertEqual(self.git('rev-parse',self.central),self.base)
        with self.assertRaisesRegex(ValueError,'INVALID_TRANSITION'):
            recovered.integration_qa(self.commands)
        self.assertEqual(TransactionSync.load(txn.journal_db,txn.transaction_id).state,'ABORT')
        self.assertEqual(self.git('rev-parse',self.central),self.base)

    def test_journal_immutable_digest_and_history_tampering_rejected(self):
        txn=self.make();txn.prepare()
        with closing(sqlite3.connect(txn.journal_db)) as db:
            with db:
                db.execute("UPDATE cc_sync_transactions SET immutable_digest='tampered' WHERE id=?",(txn.transaction_id,))
        with self.assertRaisesRegex(ValueError,'JOURNAL_TAMPERED'):
            TransactionSync.load(txn.journal_db,txn.transaction_id)
        other=self.make();other.prepare()
        with closing(sqlite3.connect(other.journal_db)) as db:
            with db:
                db.execute("UPDATE cc_sync_history SET payload_digest='tampered' WHERE transaction_id=? AND version=1",(other.transaction_id,))
        with self.assertRaisesRegex(ValueError,'JOURNAL_TAMPERED'):
            TransactionSync.load(other.journal_db,other.transaction_id)

    def test_stale_reconstructed_writer_cannot_repeat_commit(self):
        txn=self.make();self.ready(txn)
        first=TransactionSync.load(txn.journal_db,txn.transaction_id)
        stale=TransactionSync.load(txn.journal_db,txn.transaction_id)
        self.assertEqual(first.commit('OWNER_TEST_FIXTURE',self.approve)['state'],'COMMIT')
        with self.assertRaisesRegex(ValueError,'JOURNAL_VERSION_CONFLICT'):
            stale.commit('OWNER_TEST_FIXTURE',self.approve)
        self.assertEqual(TransactionSync.load(txn.journal_db,txn.transaction_id).state,'COMMIT')

    def test_explicit_journal_and_interrupted_ref_write_never_redone(self):
        journal=self.repo.parent/'explicit.sqlite3'
        txn=TransactionSync(self.repo,self.central,self.base,self.candidates,'saved',journal_db=journal)
        self.assertEqual(txn.journal_db,journal.resolve())
        txn.record('COMMIT_IN_PROGRESS',checkpoint='saved')
        recovered=TransactionSync.load(journal,txn.transaction_id)
        self.assertEqual(recovered.state,'ABORT')
        self.assertEqual(self.git('rev-parse',self.central),self.base)

    def test_journal_keeps_qa_output_digests_without_raw_text(self):
        script=self.repo.parent/'qa.py';script.write_text('print("PRIVATE_OUTPUT_SENTINEL")')
        commands=[[sys.executable,'-B',str(script)]]
        txn=self.make();txn.scope_policy['qa_commands_digest']=digest(commands)
        txn.prepare();txn.validate()
        self.assertEqual(txn.integration_qa(commands)['state'],'INTEGRATION_QA')
        with closing(sqlite3.connect(txn.journal_db)) as db:
            payload=db.execute('SELECT payload FROM cc_sync_transactions WHERE id=?',(txn.transaction_id,)).fetchone()[0]
        self.assertNotIn('PRIVATE_OUTPUT_SENTINEL',payload)
        self.assertIn('stdout_sha256',payload)

if __name__=='__main__':unittest.main()
