import json
import sqlite3
import subprocess
import sys
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from registry import Registry,Denied
from backup_registry import backup
from qa_runner import assess

class TestRecovery(unittest.TestCase):
 def setUp(self):
  self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)
  self.db=Registry(self.root/'registry.db')
  self.sha='a'*40
 def task(self,tid,scope,owner='ANTI-01',resources=None,depends=None):
  self.db.create_task('CODEX',tid,tid,scope,'bounded contract',self.sha,requires_preview=False,exclusive_resources=resources or [],depends_on=depends or [])
  return self.db.assign('CODEX',tid,owner)['fencing']
 def test_emergency_stop_freezes_and_blocks_all_new_work(self):
  fence=self.task('A','arch')
  out=self.db.emergency_stop('CODEX','Stop unsafe changes')
  self.assertEqual(out['mode'],'EMERGENCY_STOP')
  self.assertEqual(self.db.get_task('CODEX','A')['state'],'FROZEN')
  with self.assertRaises(Denied):self.db.create_task('CODEX','B','B','mep','task',self.sha)
  with self.assertRaises(Denied):self.db.checkpoint('ANTI-01','A',fence,'should not work')
  self.assertTrue(self.db.control_status('CODEX')['frozen_locks'])
  self.assertFalse(out['processes_killed'])
 def test_stop_role_separation(self):
  with self.assertRaises(Denied):self.db.emergency_stop('ANTI-01','Unsafe behavior')
 def test_crash_restart_freezes_fails_closed(self):
  fence=self.task('A','arch')
  out=self.db.reconcile_startup()
  self.assertEqual(out['mode'],'RECOVERY_REQUIRED')
  self.assertEqual(out['frozen_active_locks'],1)
  with self.assertRaises(Denied):self.db.create_task('CODEX','B','B','mep','contract',self.sha)
  with self.assertRaises(Denied):self.db.checkpoint('ANTI-01','A',fence,'still running')
 def test_recovery_explicit_and_new_fence(self):
  old=self.task('A','arch')
  self.db.reconcile_startup()
  with self.assertRaises(Denied):self.db.resume_control('CODEX',True,False,'I_APPROVE_RECOVERY')
  self.db.resume_control('CODEX',True,True,'I_APPROVE_RECOVERY')
  with self.assertRaises(Denied):self.db.resume_frozen_task('CODEX','A','ANTI-02',True,True)
  out=self.db.resume_frozen_task('CODEX','A','ANTI-01',True,True)
  self.assertNotEqual(old,out['new_fencing'])
  with self.assertRaises(Denied):self.db.checkpoint('ANTI-01','A',old,'stale fence')
  self.assertEqual(self.db.checkpoint('ANTI-01','A',out['new_fencing'],'new fence')['checkpoint'],'SAVED')
 def test_quota_exhaustion_freezes_only_owner(self):
  fa=self.task('A','arch')
  fb=self.task('B','mep','ANTI-02')
  self.db.heartbeat('ANTI-01','QUOTA_EXHAUSTED')
  self.assertEqual(self.db.get_task('CODEX','A')['state'],'FROZEN')
  self.assertEqual(self.db.get_task('CODEX','B')['state'],'RUNNING')
  self.assertEqual(self.db.checkpoint('ANTI-02','B',fb,'keep working')['checkpoint'],'SAVED')
  with self.assertRaises(Denied):self.db.checkpoint('ANTI-01','A',fa,'should fail')
 def test_stale_heartbeat_is_not_auto_release(self):
  self.task('A','arch')
  self.db.heartbeat('ANTI-01','WORKING')
  with self.db.transaction() as db:
   old=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
   db.execute('UPDATE agents SET last_seen=? WHERE id=?',(old,'ANTI-01'))
  result=self.db.stale_sweep('CODEX',120)
  self.assertEqual(result['frozen_tasks'],['A'])
  self.assertEqual(result['released_locks'],0)
  self.assertEqual(self.db.get_task('CODEX','A')['state'],'FROZEN')
 def test_resource_conflict_different_directories(self):
  self.task('A','rebar/beam','ANTI-01',['core-rebar-api'])
  self.db.create_task('CODEX','B','B','rebar/column','contract',self.sha,exclusive_resources=['core-rebar-api'])
  with self.assertRaisesRegex(Denied,'CANT_EDIT_SHARED_RESOURCE'):self.db.assign('CODEX','B','ANTI-02')
 def test_resource_nonconflict_parallel(self):
  self.task('A','rebar/beam','ANTI-01',['beam-api'])
  f=self.task('B','rebar/column','ANTI-02',['column-api'])
  self.assertGreater(f,0)
 def test_dependency_must_be_integrated(self):
  self.task('A','arch','ANTI-01')
  self.db.create_task('CODEX','B','B','mep','contract',self.sha,depends_on=['A'])
  with self.assertRaisesRegex(Denied,'DEPENDENCY_NOT_INTEGRATED'):self.db.assign('CODEX','B','ANTI-02')
 def test_qa_evidence_role_read_only(self):
  self.task('A','arch')
  with self.assertRaises(Denied):self.db.qa_evidence('ANTI-01','A')
 def test_backup_hash_and_integrity(self):
  self.task('A','arch')
  result=backup(self.root/'registry.db',self.root/'backups')
  self.assertEqual(result['sqlite_integrity_check'],'ok')
  self.assertTrue((self.root/'backups'/result['snapshot']).exists())
  self.assertFalse(result['includes_oauth_tokens'])
 def test_qa_runner_real_git_and_commit_gate(self):
  repo=self.root/'repo';repo.mkdir()
  def git(*args):
   return subprocess.run(['git',*args],cwd=repo,capture_output=True,text=True,check=True).stdout.strip()
  git('init','-q');git('config','user.email','qa@example.test');git('config','user.name','KTOOL Test')
  (repo/'README.md').write_text('base\n')
  git('add','.');git('commit','-qm','base');base=git('rev-parse','HEAD')
  (repo/'arch').mkdir();(repo/'arch'/'new.cs').write_text('class A {}\n')
  git('add','.');git('commit','-qm','implementation');head=git('rev-parse','HEAD')
  self.db.create_task('CODEX','GIT','GIT','arch','contract',base,requires_preview=False)
  f=self.db.assign('CODEX','GIT','ANTI-01')['fencing']
  self.db.submit_self_qa('ANTI-01','GIT',f,head,['arch/new.cs'],{'scope':True,'diff':True,'regression':True,'safety':True},'PASS','PASS','NOT_APPLICABLE','logs/selfqa.json')
  self.db.submit_result('ANTI-01','GIT',f,head,'Implemented module successfully','PASS','PASS','logs/submission.json')
  with self.assertRaisesRegex(Denied,'INDEPENDENT_LOCAL_QA_EVIDENCE_REQUIRED'):
   self.db.review_task('CODEX','GIT','PASS_CODE_REVIEW','Proposed pass without QA evidence','qa/review.json',True,True)
  profile=self.root/'profile.json';profile.write_text(json.dumps({'build':[sys.executable,'-c','print("build ok")'],'tests':[sys.executable,'-c','print("tests ok")']}))
  good=assess(self.root/'registry.db','GIT',repo,profile)
  self.assertEqual(good['result'],'PASS')
  self.db.review_task('CODEX','GIT','PASS_CODE_REVIEW','Verified diff build and tests from QA runner','qa/review.json',True,True)
  self.db.close_task('CODEX','GIT',head,True)
  self.assertEqual(self.db.get_task('CODEX','GIT')['state'],'CLOSED')

if __name__=='__main__':unittest.main()
