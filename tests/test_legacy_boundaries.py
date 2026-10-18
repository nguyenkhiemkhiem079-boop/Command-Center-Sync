"""Actual new-controller then legacy lock acquisition and shared freeze guards."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from orchestration import ControlStore
from registry import Registry,Denied

class LegacyBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.repo=self.root/'repo';self.repo.mkdir()
        for args in [('init','-q'),('config','user.name','Boundary QA'),('config','user.email','qa@example.test')]:self.git(*args)
        (self.repo/'README').write_text('base');self.git('add','.');self.git('commit','-qm','base');self.base=self.git('rev-parse','HEAD')
        self.path=self.root/'registry.db';self.legacy=Registry(self.path);self.control=ControlStore(self.path)
        contract=self.control.propose_contract('CODEX','fixture',{'acceptance_criteria':['fixture boundary']},affects_baseline=False)
        self.control.approve_contract('CODEX',contract);revision=self.control.publish_revision('CODEX',{'contracts':[contract]})
        self.control.create_mission('CODEX','MISSION',revision)
        self.control.queue_wave('CODEX','MISSION','WAVE',[{'id':'NEW','team':'TEAM1','owner':'ANTI-01','repo':str(self.repo),
          'base_sha':self.base,'contract_hash':contract,'allowed_paths':['module/owned'],'resource_locks':['shared-api'],
          'acceptance_criteria':['fixture boundary']}])
        self.assertEqual(len(self.control.dispatch('CODEX')['assigned']),1)
    def git(self,*args):
        return subprocess.run(['git',*args],cwd=self.repo,capture_output=True,text=True,check=True).stdout.strip()
    def legacy_task(self,scope,resources=None):
        self.legacy.create_task('CODEX','OLD','legacy',scope,'bounded task',self.base,exclusive_resources=resources or [])
    def test_new_lock_blocks_legacy_same_parent_child_scope(self):
        for scope in ('module','module/owned','module/owned/file'):
            with self.subTest(scope=scope):
                self.legacy.create_task('CODEX',scope.replace('/','_'),'legacy',scope,'bounded',self.base)
                with self.assertRaisesRegex(Denied,'CANT_EDIT'):
                    self.legacy.assign('CODEX',scope.replace('/','_'),'ANTI-02')
        self.assertEqual(len(self.control.snapshot()['assignments']),1)
    def test_new_resource_blocks_legacy_disjoint_scope(self):
        self.legacy_task('other',['shared-api'])
        with self.assertRaisesRegex(Denied,'CANT_EDIT_SHARED_RESOURCE'):self.legacy.assign('CODEX','OLD','ANTI-02')
    def test_new_emergency_mode_blocks_legacy_writes(self):
        self.legacy_task('other');self.control.set_mode('CODEX','EMERGENCY_STOP')
        with self.assertRaises(Denied):self.legacy.assign('CODEX','OLD','ANTI-02')
        with self.assertRaises(Denied):self.legacy.create_task('CODEX','X','X','x','bounded',self.base)
    def test_new_recovery_mode_blocks_legacy_writes(self):
        self.legacy_task('other');self.control.set_mode('CODEX','RECOVERY_REQUIRED')
        with self.assertRaises(Denied):self.legacy.assign('CODEX','OLD','ANTI-02')
    def test_legacy_emergency_freezes_new_controller(self):
        self.legacy.emergency_stop('CODEX','Owner requested complete stop')
        snapshot=self.control.snapshot();self.assertEqual(snapshot['supervisor_mode'],'EMERGENCY_STOP')
        self.assertEqual(snapshot['assignments'][0]['status'],'FROZEN')
        with self.control.connection() as db:self.assertEqual(db.execute('SELECT state FROM cc_locks').fetchone()[0],'FROZEN')
    def test_legacy_boolean_recovery_release_fail_closed_and_roles_first(self):
        for action,args in ((self.legacy.resume_control,(True,True,'I_APPROVE_RECOVERY')),
                            (self.legacy.resume_frozen_task,('NEW','ANTI-01',True,True)),
                            (self.legacy.close_task,('NEW','a'*40,True))):
            with self.subTest(action=action.__name__):
                with self.assertRaisesRegex(Denied,'ROLE'):action('ANTI-01',*args)
                with self.assertRaisesRegex(Denied,'VERIFIED_'):action('CODEX',*args)
        with self.control.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM cc_locks').fetchone()[0],1)

if __name__=='__main__':unittest.main()
