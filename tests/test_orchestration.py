"""Controller regression tests with real temporary Git; fixture acceptance is sandbox only."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from orchestration import ControlStore, digest
from registry import Denied, Registry
from recovery_manager import OwnedProcessRegistry


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.repo=self.root/'central';self.repo.mkdir()
        self.git(self.repo,'init','-q','-b','central');self.git(self.repo,'config','user.name','Controller Test')
        self.git(self.repo,'config','user.email','controller@test.local')
        (self.repo/'README.md').write_text('base\n');self.git(self.repo,'add','.');self.git(self.repo,'commit','-qm','base')
        self.base=self.git(self.repo,'rev-parse','HEAD')
        self.repos={}
        for key in ('A','B'):
            self.repos[key]=self.root/key
            self.git(self.repo,'worktree','add','-q','-b','worker-'+key,str(self.repos[key]),self.base)
        self.dbpath=self.root/'registry.db';self.store=ControlStore(self.dbpath)
        content={'acceptance_criteria':['actual tests required'],'rules':['sandbox only']}
        self.contract=self.store.propose_contract('CODEX','CONTRACT',content,False)
        self.store.approve_contract('CODEX',self.contract)
        self.rev=self.store.publish_revision('CODEX',{'contracts':[self.contract],'version':1})
        self.store.create_mission('CODEX','M',self.rev,{'sandbox':True,'max_workers':2,'dispatch_without_lead':False})

    def git(self,repo,*args):
        return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.PIPE,text=True).strip()

    def spec(self,key,**extra):
        spec={'id':key,'team':'TEAM-'+key,'owner':'ANTI-01' if key=='A' else 'ANTI-02',
              'contract_hash':self.contract,'repo':str(self.repos[key]),'base_sha':self.base,
              'allowed_paths':['architectural/envelope' if key=='A' else 'documentation/schedules'],
              'acceptance_criteria':['unit tests'],'tools':['read_source','write_source','run_tests','checkpoint']}
        spec.update(extra);return spec

    def start(self,specs=None):
        self.store.queue_wave('CODEX','M','W',specs or [self.spec('A'),self.spec('B')])
        return {x['id']:x['epoch'] for x in self.store.dispatch('CONTROLLER')['assigned']}

    def candidate(self,key,path=None):
        scope=path or ('architectural/envelope' if key=='A' else 'documentation/schedules')
        file=self.repos[key]/scope/'module.txt';file.parent.mkdir(parents=True,exist_ok=True);file.write_text(key+' real source\n')
        self.git(self.repos[key],'add','.');self.git(self.repos[key],'commit','-qm','candidate '+key)
        return self.git(self.repos[key],'rev-parse','HEAD'),[scope+'/module.txt']

    def submit(self,key,epoch):
        owner='ANTI-01' if key=='A' else 'ANTI-02'
        self.store.acknowledge(owner,key,epoch,self.contract)
        sha,paths=self.candidate(key)
        self.store.checkpoint(owner,key,epoch,sha,paths,{'source':'TEST_FIXTURE','status':'CLAIMED'})
        self.store.submit_claim(owner,key,epoch)
        return sha

    def local_accept(self,key):
        # Only exercises controller state; not a protected verifier or production QA proof.
        return self.store.accept('CODEX',key,{'source':'STATE_MACHINE_FIXTURE'},
                                 lambda evidence,binding:{'status':'LOCAL_VERIFIED','source':'TEST_FIXTURE'})

    def test_atomic_wave_idempotent_retry_and_restart(self):
        specs=[self.spec('A'),self.spec('B')]
        first=self.store.queue_wave('CODEX','M','W',specs)
        retry=ControlStore(self.dbpath).queue_wave('CODEX','M','W',specs)
        self.assertFalse(first['idempotent']);self.assertTrue(retry['idempotent'])
        snap=self.store.snapshot();self.assertEqual(len(snap['assignments']),2)
        self.assertEqual(snap['waves'][0]['state'],'WAITING')

    def test_circular_dependencies_rollback_parent_and_children(self):
        with self.assertRaisesRegex(Denied,'CIRCULAR_DEPENDENCY'):
            self.store.queue_wave('CODEX','M','W',[self.spec('A',dependencies=['B']),self.spec('B',dependencies=['A'])])
        self.assertEqual(self.store.snapshot()['waves'],[]);self.assertEqual(self.store.snapshot()['assignments'],[])

    def test_two_dispatches_are_concurrent_but_not_running_until_ack(self):
        epochs=self.start();self.assertEqual(set(epochs),{'A','B'})
        for t in self.store.snapshot()['assignments']: self.assertEqual(t['status'],'TASK_ASSIGNED')
        self.assertEqual(self.store.dispatch('CONTROLLER')['assigned'],[])
        self.store.acknowledge('ANTI-01','A',epochs['A'],self.contract)
        with self.assertRaises(Denied):self.store.acknowledge('ANTI-02','A',epochs['A'],self.contract)
        with self.assertRaises(Denied):self.store.acknowledge('ANTI-01','A',epochs['A'],'stale')

    def test_parent_child_lock_conflict_and_shared_resource(self):
        self.store.queue_wave('CODEX','M','W',[self.spec('A',allowed_paths=['architectural']),self.spec('B',allowed_paths=['architectural/envelope'])])
        r=self.store.dispatch('CONTROLLER');self.assertEqual(len(r['assigned']),1)
        self.assertEqual(r['pending'][0]['reason'],'CANT_EDIT')

    def test_shared_core_and_capability_wait(self):
        self.store.queue_wave('CODEX','M','W',[self.spec('A',resource_locks=['core']),self.spec('B',resource_locks=['core'])])
        result=self.store.dispatch('CONTROLLER');self.assertEqual(result['pending'][0]['reason'],'CANT_EDIT_SHARED_RESOURCE')

    def test_nonexistent_and_empty_checkpoint_rejected(self):
        epoch=self.start([self.spec('A')])['A'];self.store.acknowledge('ANTI-01','A',epoch,self.contract)
        with self.assertRaises(ValueError):self.store.checkpoint('ANTI-01','A',epoch,'0'*40,[],{})
        with self.assertRaisesRegex(Denied,'CHECKPOINT_DIFF_MISMATCH'):self.store.checkpoint('ANTI-01','A',epoch,self.base,[],{})
        sha,paths=self.candidate('A')
        with self.assertRaises(Denied):self.store.checkpoint('ANTI-01','A',epoch,sha,[],{})
        with self.assertRaises(Denied):self.store.checkpoint('ANTI-02','A',epoch,sha,paths,{})

    def test_multiple_paths_forbidden_and_actual_diff_enforcement(self):
        spec=self.spec('A',allowed_paths=['architectural/envelope','documentation/schedules'],readonly_paths=['locked'],forbidden_paths=['secrets'])
        epoch=self.start([spec])['A'];self.store.acknowledge('ANTI-01','A',epoch,self.contract)
        sha,paths=self.candidate('A','secrets')
        with self.assertRaisesRegex(Denied,'CANT_EDIT'):self.store.checkpoint('ANTI-01','A',epoch,sha,paths,{})

    def test_provider_completion_and_early_child_never_complete_wave(self):
        epochs=self.start();self.submit('A',epochs['A'])
        self.store.provider_completed('ANTI-02','B',epochs['B'])
        self.assertEqual(self.store.snapshot()['waves'][0]['state'],'WAITING')
        self.local_accept('A');self.assertEqual(self.store.snapshot()['waves'][0]['state'],'WAITING')
        self.submit('B',epochs['B']);self.local_accept('B')
        self.assertEqual(self.store.snapshot()['waves'][0]['state'],'COMPLETE')
        events=[e for e in self.store.snapshot()['events'] if e['kind']=='WAVE_BARRIER_TERMINAL']
        self.assertEqual(len(events),1)

    def test_worker_cannot_self_approve_and_production_callback_cannot_forge_trust(self):
        epoch=self.start([self.spec('A')])['A'];self.submit('A',epoch)
        with self.assertRaises(Denied):self.store.accept('ANTI-01','A',True,lambda e,b:{'status':'ACCEPTED'})
        with self.assertRaises(Denied):self.store.accept('CODEX','A',True)
        with self.store.transaction() as db:db.execute("UPDATE cc_missions SET policy=? WHERE id='M'",('{"sandbox":false,"max_workers":2}',))
        with self.assertRaisesRegex(Denied,'PROTECTED_EXTERNAL_VERIFIER_NOT_CONFIGURED'):
            self.store.accept('CODEX','A',True,lambda e,b:{'status':'ACCEPTED','production_trusted':True})

    def test_wrong_owner_steering_and_durable_ack(self):
        epochs=self.start()
        with self.assertRaises(Denied):self.store.steer('ANTI-02','M','A','ANTI-01',self.rev,'wrong owner')
        with self.assertRaises(Denied):self.store.steer('ANTI-01','M','A','ANTI-02',self.rev,'wrong target')
        h=self.store.steer('CODEX','M','A','ANTI-01',self.rev,'Review boundary condition')
        self.store.acknowledge_steering('ANTI-01',h,'ANTI-01')
        self.assertEqual(ControlStore(self.dbpath).snapshot()['steering'][0]['status'],'ACKNOWLEDGED')
        self.assertEqual(self.store.get_assignment('CODEX','A')['contract_hash'],self.contract)

    def test_subagent_cannot_expand_parent_tools_or_scope(self):
        epoch=self.start([self.spec('A',tools=['read_source','checkpoint'])])['A']
        with self.assertRaises(Denied):self.store.add_subagent('ANTI-01','A',epoch,'child',['other'],['read_source'],['read_source','checkpoint'])
        with self.assertRaises(Denied):self.store.add_subagent('ANTI-01','A',epoch,'child',['architectural/envelope'],['write_source'],['read_source','write_source','checkpoint'])
        with self.assertRaises(Denied):self.store.add_subagent('ANTI-01','A',epoch,'ANTI-02',['architectural/envelope'],['read_source'],['read_source','checkpoint'])
        self.store.add_subagent('ANTI-01','A',epoch,'A-explorer',['architectural/envelope'],['read_source'],['read_source','checkpoint'])

    def test_nested_wave_narrowing_and_suspended_parent(self):
        epoch=self.start([self.spec('A')])['A'];self.store.acknowledge('ANTI-01','A',epoch,self.contract)
        child=self.spec('A',id='CHILD',team='TEAM-A',allowed_paths=['architectural/envelope/child'])
        with self.assertRaises(Denied):self.store.queue_wave('CODEX','M','BAD',[dict(child,allowed_paths=['outside'])],parent='A')
        self.store.queue_wave('CODEX','M','NESTED',[child],parent='A')
        assigned=self.store.dispatch('CONTROLLER')['assigned'];self.assertEqual(assigned[0]['id'],'CHILD')
        with self.assertRaises(Denied):self.store.provider_completed('ANTI-01','A',epoch)

    def test_lead_unavailable_keeps_authorized_checkpoints_without_approval(self):
        epoch=self.start([self.spec('A')])['A'];self.store.acknowledge('ANTI-01','A',epoch,self.contract)
        self.store.set_mode('CODEX','LEAD_UNAVAILABLE')
        with self.assertRaises(Denied):self.store.propose_contract('CODEX','NEW',{'acceptance_criteria':['x']},False)
        sha,paths=self.candidate('A');self.store.checkpoint('ANTI-01','A',epoch,sha,paths,{})
        self.store.submit_claim('ANTI-01','A',epoch)
        self.assertEqual(self.store.get_assignment('CODEX','A')['status'],'WAITING_FOR_CODEX_REVIEW')
        with self.assertRaises(Denied):self.local_accept('A')
        summary=self.store.recover_lead('CODEX');self.assertFalse(summary['approval_granted'])
        self.assertEqual(self.store.get_assignment('CODEX','A')['status'],'SYNC_REQUEST')

    def test_crash_freeze_verified_stop_resume_and_stale_epoch(self):
        epoch=self.start([self.spec('A')])['A'];self.store.reconcile_startup()
        with self.assertRaises(Denied):self.store.resume('CODEX','A',{'stopped':True})
        process_registry=OwnedProcessRegistry();record=process_registry.launch('A',[sys.executable,'-c','import time; time.sleep(30)'])
        proof=process_registry.terminate(record['record_id'],'A')
        new=self.store.resume('CODEX','A',proof,process_registry.verify_stop)
        self.assertNotEqual(epoch,new)
        with self.assertRaises(Denied):self.store.acknowledge('ANTI-01','A',epoch,self.contract)
        self.store.acknowledge('ANTI-01','A',new,self.contract)

    def test_emergency_stop_is_absorbing_and_legacy_emergency_blocks_dispatch(self):
        self.store.set_mode('CODEX','EMERGENCY_STOP')
        for mode in ('NORMAL','LEAD_UNAVAILABLE','RECOVERY_REQUIRED'):
            with self.assertRaises(Denied):self.store.set_mode('CODEX',mode)
        with self.assertRaises(Denied):self.store.dispatch('CONTROLLER')
        legacy=Registry(self.root/'legacy.db');other=ControlStore(self.root/'legacy.db')
        legacy.emergency_stop('CODEX','Actual legacy emergency test')
        with self.assertRaises(Denied):other.dispatch('CONTROLLER')

    def test_contract_hash_immutable_and_baseline_requires_owner(self):
        with self.assertRaises(Denied):self.store.propose_contract('ANTI-01','BAD',{'acceptance_criteria':['x']})
        baseline=self.store.propose_contract('CODEX','ENGINEERING',{'acceptance_criteria':['Revit API baseline']},True)
        with self.assertRaises(Denied):self.store.approve_contract('CODEX',baseline)
        with self.assertRaises(Denied):self.store.approve_contract('OWNER',baseline,{'checkbox':True})
        with self.store.transaction() as db:db.execute('UPDATE cc_contracts SET content=? WHERE hash=?',('{"acceptance_criteria":["tampered"]}',self.contract))
        with self.assertRaisesRegex(Denied,'TAMPERED_CONTRACT'):self.store.get_contract('ANTI-01',self.contract)

    def test_human_request_does_not_grant_privileges(self):
        self.start([self.spec('A')])
        request=self.store.human_request('ANTI-01','M','approval','Request owner review','A')
        with self.assertRaises(Denied):self.store.resolve_human_request('ANTI-01',request,'approve')
        with self.assertRaises(Denied):self.store.resolve_human_request('OWNER',request,'approve',True)
        self.assertEqual(self.store.snapshot()['human_requests'][0]['status'],'PENDING')

    def test_three_unchanged_defects_freeze_without_releasing_lock(self):
        epoch=self.start([self.spec('A')])['A']
        self.store.acknowledge('ANTI-01','A',epoch,self.contract)
        sha,paths=self.candidate('A')
        issue={'id':'D1','severity':'high','path':paths[0],'expected':'correct','actual':'wrong'}
        for iteration in range(3):
            self.store.checkpoint('ANTI-01','A',epoch,sha,paths,{})
            self.store.submit_claim('ANTI-01','A',epoch)
            self.store.feedback('CODEX','A',[issue],'real failing evidence reference')
            if iteration<2:self.store.acknowledge_feedback('ANTI-01','A',epoch)
        self.assertEqual(self.store.get_assignment('CODEX','A')['status'],'FROZEN')
        with self.store.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM cc_locks').fetchone()[0],1)

    def test_additive_migration_preserves_legacy_data(self):
        path=self.root/'existing.db';legacy=Registry(path)
        legacy.create_task('CODEX','LEGACY','Keep','arch','existing contract',self.base)
        ControlStore(path);ControlStore(path)
        self.assertEqual(legacy.get_task('CODEX','LEGACY')['title'],'Keep')


    def test_old_checkpoint_cannot_be_submitted_after_verified_resume(self):
        epoch=self.start([self.spec('A')])['A']
        self.store.acknowledge('ANTI-01','A',epoch,self.contract)
        sha,paths=self.candidate('A');self.store.checkpoint('ANTI-01','A',epoch,sha,paths,{})
        self.store.reconcile_startup()
        processes=OwnedProcessRegistry();record=processes.launch('A',[sys.executable,'-c','import time; time.sleep(30)'])
        proof=processes.terminate(record['record_id'],'A')
        new=self.store.resume('CODEX','A',proof,processes.verify_stop)
        self.store.acknowledge('ANTI-01','A',new,self.contract)
        with self.assertRaisesRegex(Denied,'CURRENT_EPOCH_CHECKPOINT_REQUIRED'):
            self.store.submit_claim('ANTI-01','A',new)

    def test_checkpoint_requires_worker_acknowledgment(self):
        epoch=self.start([self.spec('A')])['A'];sha,paths=self.candidate('A')
        with self.assertRaises(Denied):self.store.checkpoint('ANTI-01','A',epoch,sha,paths,{})

if __name__=='__main__':unittest.main()
