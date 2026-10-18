import unittest
import dataclasses
from datetime import datetime,timedelta,timezone
from tests import test_orchestration as fixtures
from governance import GovernanceStore,Principal,ROLES
from registry import Denied,hash_token

class GovernanceTests(unittest.TestCase):
    setUp=fixtures.OrchestrationTests.setUp
    git=fixtures.OrchestrationTests.git
    spec=fixtures.OrchestrationTests.spec
    start=fixtures.OrchestrationTests.start
    def gov(self,fixture=True):
        return GovernanceStore(self.dbpath,{'CODEX':hash_token('fixture-codex'),'ANTI-01':hash_token('fixture-worker'),'OWNER':hash_token('fixture-owner'),'READ_ONLY_OBSERVER':hash_token('fixture-observer')},environment='TEST_FIXTURE' if fixture else 'PRODUCTION')
    def expiry(self):return (datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()
    def test_bearer_role_spoof_and_cross_store_principal_denied(self):
        g=self.gov();worker=g.authenticate('Bearer fixture-worker');self.assertEqual(worker.role,'ANTI_WORKER')
        with self.assertRaises(Denied):g.authorize(dataclasses.replace(worker,role='OWNER'),'release')
        with self.assertRaises(Denied):self.gov().authorize(worker,'status.read')
        with self.assertRaises(Denied):g.authenticate('Bearer unknown')
        with self.assertRaises(Denied):g.authorize(worker,'merge')
    def test_all_six_roles_and_unknown_actions_fail_closed(self):
        g=self.gov()
        for role in ROLES:
            p=g.fixture_principal('fixture-'+role,role);self.assertEqual(g.authorize(p,'status.read')['role'],role)
            with self.assertRaises(Denied):g.authorize(p,'grant.admin')
        prod=self.gov(False)
        with self.assertRaises(Denied):prod.fixture_principal('bad','OWNER')
    def test_production_owner_cannot_approve_via_local_bearer(self):
        g=self.gov(False);lead=g.authenticate('Bearer fixture-codex');owner=g.authenticate('Bearer fixture-owner')
        request=g.request_approval(lead,'M','merge',['module'],'a'*40,self.expiry())
        with self.assertRaisesRegex(Denied,'PROTECTED_OWNER_ATTESTATION_UNAVAILABLE'):g.approve(owner,request['request_id'])
        with self.assertRaises(Denied):g.consume_approval(lead,request['request_id'],'merge',['module'],'a'*40)
    def test_once_only_fixture_approval_and_scope_binding(self):
        g=self.gov();lead=g.authenticate('Bearer fixture-codex');owner=g.authenticate('Bearer fixture-owner')
        r=g.request_approval(lead,'M','merge',['module'],'a'*40,self.expiry());g.approve(owner,r['request_id'])
        with self.assertRaises(Denied):g.consume_approval(lead,r['request_id'],'merge',['other'],'a'*40)
        result=g.consume_approval(lead,r['request_id'],'merge',['module'],'a'*40)
        self.assertFalse(result['production_trusted'])
        with self.assertRaises(Denied):g.consume_approval(lead,r['request_id'],'merge',['module'],'a'*40)
        self.assertTrue(g.approval_history(lead,r['request_id']))
    def test_expired_request_and_worker_selfapproval_denied(self):
        epoch=self.start([self.spec('A')])['A'];g=self.gov();worker=g.authenticate('Bearer fixture-worker')
        r=g.request_approval(worker,'M','merge',['architectural/envelope'],'a'*40,self.expiry(),'A')
        with self.assertRaises(Denied):g.approve(worker,r['request_id'])
        with self.assertRaises(ValueError):g.request_approval(worker,'M','merge',['module'],'a'*40,'2000-01-01T00:00:00Z','A')
        with g.transaction() as db:db.execute("UPDATE cc_human_requests SET deadline='2000-01-01T00:00:00+00:00' WHERE id=?",(r['request_id'],))
        with self.assertRaises(Denied):g.approve(g.authenticate('Bearer fixture-owner'),r['request_id'])
    def test_knowledge_history_tampering_and_worker_write_denied(self):
        g=self.gov();lead=g.authenticate('Bearer fixture-codex');worker=g.authenticate('Bearer fixture-worker')
        prov={'source_ref':'fixture.md','source_sha256':'a'*64,'kind':'TEST_FIXTURE'}
        for i in (1,2):g.publish_knowledge(lead,'ADR1',{'decision':i},prov)
        self.assertEqual(len(g.knowledge_history(lead,'ADR1')),2)
        with self.assertRaises(Denied):g.publish_knowledge(worker,'ADR2',{'x':1},prov)
        with g.transaction() as db:db.execute("UPDATE cc_knowledge_versions SET content='{}' WHERE key='ADR1' AND version=1")
        with self.assertRaises(Denied):g.knowledge_history(lead,'ADR1')
    def test_migration_does_not_reset_existing_request(self):
        old=self.store.human_request('CODEX','M','INPUT_REQUIRED','Keep this request')
        self.gov();self.gov()
        row=next(x for x in self.store.snapshot()['human_requests'] if x['id']==old)
        self.assertEqual(row['body'],'Keep this request');self.assertEqual(row['status'],'PENDING')
    def test_approval_epoch_replay_is_rejected(self):
        epoch=self.start([self.spec('A')])['A'];g=self.gov();lead=g.authenticate('Bearer fixture-codex');owner=g.authenticate('Bearer fixture-owner')
        r=g.request_approval(lead,'M','merge',['architectural/envelope'],'a'*40,self.expiry(),'A');g.approve(owner,r['request_id'])
        with g.transaction() as db:db.execute("UPDATE cc_assignments SET epoch=epoch+1 WHERE id='A'")
        with self.assertRaisesRegex(Denied,'STALE_APPROVAL_OWNERSHIP_CONTRACT'):g.consume_approval(lead,r['request_id'],'merge',['architectural/envelope'],'a'*40)
if __name__=='__main__':unittest.main()
