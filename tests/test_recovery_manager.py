"""Actual controller-owned child handles, real Git bundles and SQLite restore drills."""
import copy
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from recovery_manager import OwnedProcessRegistry,RecoveryManager
from trust_vault import digest

@contextmanager
def database(path):
    db=sqlite3.connect(path)
    try:
        with db: yield db
    finally: db.close()

class RecoveryManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.manager=RecoveryManager()
    def launch(self,registry,assignment):
        record=registry.launch(assignment,[sys.executable,'-c','import time;time.sleep(120)'])
        def cleanup():
            process=registry._records[record['record_id']]['process']
            if process.poll() is None: process.terminate();process.wait(timeout=10)
        self.addCleanup(cleanup);return record
    def test_actual_owned_handle_termination(self):
        registry=OwnedProcessRegistry();record=self.launch(registry,'A')
        self.assertFalse(registry.verify_stop({'stopped':True,'pid':record['pid']},'A'))
        proof=registry.terminate(record['record_id'],'A')
        self.assertTrue(registry.verify_stop(proof,'A'));self.assertFalse(registry.verify_stop(proof,'B'))
        self.assertIsNotNone(registry._records[record['record_id']]['process'].poll())
    def test_unrelated_reused_or_altered_record_cannot_authorize(self):
        registry=OwnedProcessRegistry();a=self.launch(registry,'A');b=self.launch(registry,'B')
        with self.assertRaises(ValueError):registry.terminate(b['record_id'],'A')
        proof=registry.terminate(a['record_id'],'A');changed=copy.deepcopy(proof);changed['pid']=b['pid']
        self.assertFalse(registry.verify_stop(changed,'A'))
        self.assertFalse(OwnedProcessRegistry().verify_stop(proof,'A'))
        newer=self.launch(registry,'A');self.assertFalse(registry.verify_stop(proof,'A'))
        self.assertIsNone(registry._records[b['record_id']]['process'].poll())
    def git(self,repo,*args):
        return subprocess.run(['git','-C',str(repo),*args],capture_output=True,text=True,check=True).stdout.strip()
    def bundle(self):
        repo=self.root/'repo';repo.mkdir();self.git(repo,'init','-q');self.git(repo,'config','user.name','Recovery QA');self.git(repo,'config','user.email','qa@example.test')
        (repo/'source.txt').write_text('checkpoint data');self.git(repo,'add','.');self.git(repo,'commit','-qm','checkpoint')
        sha=self.git(repo,'rev-parse','HEAD');snapshot=self.manager.checkpoint_bundle(repo,sha,self.root/'checkpoint.bundle')
        return snapshot
    def test_bundle_actual_clone_and_hash_verification(self):
        snapshot=self.bundle();r=self.manager.verify_bundle(snapshot,digest(snapshot))
        self.assertEqual(r['commit_sha'],snapshot['commit_sha'])
    def test_bundle_tamper_or_snapshot_substitution_rejected(self):
        snapshot=self.bundle();expected=digest(snapshot);changed=copy.deepcopy(snapshot);changed['commit_sha']='a'*40
        with self.assertRaises(ValueError):self.manager.verify_bundle(changed,expected)
        with Path(snapshot['bundle']).open('ab') as stream:stream.write(b'tampered')
        with self.assertRaises(ValueError):self.manager.verify_bundle(snapshot,expected)
    def sqlite(self):
        source=self.root/'live.db'
        with database(source) as db:
            db.execute('PRAGMA journal_mode=WAL');db.execute('CREATE TABLE tasks(id TEXT PRIMARY KEY,state TEXT,checkpoint TEXT)')
            db.execute('INSERT INTO tasks VALUES(?,?,?)',('A','FROZEN','sha-checkpoint'));db.commit()
        return source
    def test_sqlite_full_restore_new_target_retains_task_data(self):
        source=self.sqlite();snapshot=self.manager.backup_sqlite(source,self.root/'backup.db')
        with database(source) as db:db.execute("INSERT INTO tasks VALUES('B','ACTIVE','new')")
        target=self.root/'restored.db';r=self.manager.restore_sqlite(snapshot,digest(snapshot),target)
        self.assertEqual(r['kind'],'SQLITE_RESTORE_DRILL_VERIFIED')
        with database(target) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('SELECT * FROM tasks').fetchall(),[('A','FROZEN','sha-checkpoint')])
        with database(source) as db:self.assertEqual(db.execute('SELECT count(*) FROM tasks').fetchone()[0],2)
        with self.assertRaises(ValueError):self.manager.restore_sqlite(snapshot,digest(snapshot),source)
        with self.assertRaises(ValueError):self.manager.restore_sqlite(snapshot,digest(snapshot),target)
    def test_sqlite_tamper_rejected(self):
        source=self.sqlite();snapshot=self.manager.backup_sqlite(source,self.root/'backup.db');expected=digest(snapshot)
        with database(snapshot['backup']) as db:db.execute("DELETE FROM tasks")
        with self.assertRaises(ValueError):self.manager.restore_sqlite(snapshot,expected,self.root/'not-created.db')
        self.assertFalse((self.root/'not-created.db').exists())

if __name__=='__main__':unittest.main()
