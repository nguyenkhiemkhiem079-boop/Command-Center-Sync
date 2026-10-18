"""Typed requests are durable requests, never production approvals."""
from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
from orchestration import ControlStore
from registry import Denied

class HumanRequestTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'registry.db';self.store=ControlStore(self.path)
        with self.store.transaction() as db:
            db.execute("INSERT INTO cc_missions VALUES('M','FIXTURE_REVISION','{}','PLANNING','TEST_ONLY')")

    def test_all_master_types_persist_and_never_grant_permissions(self):
        for kind in ('INPUT_REQUIRED','DIRECTION_REQUIRED','PERMISSION_REQUIRED','CONTRACT_CHANGE','MERGE_APPROVAL','RELEASE_APPROVAL'):
            deadline=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
            request=self.store.human_request('CODEX','M',kind,'Owner decision requested',deadline=deadline)
            with self.assertRaises(Denied):self.store.resolve_human_request('ANTI-01',request,'approve')
            with self.assertRaises(Denied):self.store.resolve_human_request('OWNER',request,'approve',True)
        rows=ControlStore(self.path).snapshot()['human_requests']
        self.assertEqual(len(rows),6);self.assertTrue(all(r['status']=='PENDING' and r['deadline'] for r in rows))

    def test_deadline_validation_and_canonical_idempotency(self):
        for bad in ('2026-10-18T19:55:00','invalid',True,'2000-01-01T00:00:00+00:00'):
            with self.assertRaises(ValueError):self.store.human_request('CODEX','M','INPUT_REQUIRED','Needed',deadline=bad)
        first=self.store.human_request('CODEX','M','INPUT_REQUIRED','Needed',deadline='2099-01-01T07:00:00+07:00')
        retry=self.store.human_request('CODEX','M','INPUT_REQUIRED','Needed',deadline='2099-01-01T00:00:00Z')
        self.assertEqual(first,retry)
        with self.assertRaises(ValueError):self.store.human_request('CODEX','M','AUTO_APPROVE','invalid')

    def test_expiry_rejects_decision_and_resolution_is_once_only(self):
        request=self.store.human_request('CODEX','M','MERGE_APPROVAL','Request only',deadline='2099-01-01T00:00:00Z')
        with self.store.transaction() as db:db.execute("UPDATE cc_human_requests SET deadline='2000-01-01T00:00:00+00:00' WHERE id=?",(request,))
        with self.assertRaisesRegex(Denied,'REQUEST_EXPIRED'):
            self.store.resolve_human_request('OWNER',request,'approve',{},lambda *a:True)
        # A fixture verifies durable decision history only, never owner production identity.
        other=self.store.human_request('CODEX','M','DIRECTION_REQUIRED','Clarify naming')
        self.store.resolve_human_request('OWNER',other,{'decision':'reject','source':'TEST_FIXTURE'},{},lambda *a:True)
        row=next(r for r in self.store.snapshot()['human_requests'] if r['id']==other)
        self.assertIsNotNone(row['decided_at']);self.assertEqual(row['status'],'RESOLVED')
        with self.assertRaisesRegex(Denied,'REQUEST_ALREADY_RESOLVED'):
            self.store.resolve_human_request('OWNER',other,'approve',{},lambda *a:True)
        events=self.store.snapshot()['events']
        self.assertIn('"privilege_granted":false',events[-1]['body'])

    def test_legacy_migration_preserves_request_and_id(self):
        legacy=Path(self.tmp.name)/'legacy.db'
        with closing(sqlite3.connect(legacy)) as db:
            db.execute("CREATE TABLE cc_human_requests(id TEXT PRIMARY KEY,mission TEXT NOT NULL,assignment TEXT,target TEXT NOT NULL,kind TEXT NOT NULL,body TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'PENDING',created TEXT NOT NULL,response TEXT)")
            db.execute("INSERT INTO cc_human_requests VALUES('OLD','M',NULL,'OWNER','input','Keep','PENDING','TEST_ONLY',NULL)")
            db.commit()
        ControlStore(legacy);store=ControlStore(legacy)
        row=store.snapshot()['human_requests'][0]
        self.assertEqual(row['id'],'OLD');self.assertEqual(row['body'],'Keep');self.assertIsNone(row['deadline'])
        with store.connection() as db:self.assertEqual(db.execute("SELECT value FROM cc_meta WHERE key='human_requests_schema_version'").fetchone()[0],'2')

if __name__=='__main__':unittest.main()
