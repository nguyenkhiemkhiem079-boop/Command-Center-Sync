import unittest
from unittest.mock import patch
from tests import test_orchestration as fixtures
from orchestration import ControlStore
from registry import Denied
class DeliveryTests(unittest.TestCase):
    setUp=fixtures.OrchestrationTests.setUp
    git=fixtures.OrchestrationTests.git
    spec=fixtures.OrchestrationTests.spec
    start=fixtures.OrchestrationTests.start
    def test_atomic_assignment_outbox_rollback(self):
        self.store.queue_wave('CODEX','M','W',[self.spec('A')])
        with patch.object(self.store,'_enqueue_delivery',side_effect=RuntimeError('fixture interruption')):
            with self.assertRaises(RuntimeError):self.store.dispatch('CODEX')
        snap=self.store.snapshot();self.assertEqual(snap['assignments'][0]['status'],'QUEUED');self.assertEqual(snap['deliveries'],[])
        with self.store.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM cc_locks').fetchone()[0],0)
    def test_same_delivery_retry_ack_and_restart(self):
        epochs=self.start();outbox=self.store.delivery_outbox('ANTI-01');self.assertEqual(len(outbox),1)
        delivery=outbox[0]['id'];new=ControlStore(self.dbpath)
        first=new.delivery_attempt('CODEX',delivery);second=new.delivery_attempt('CODEX',delivery)
        self.assertEqual(first['payload_hash'],second['payload_hash']);self.assertEqual(second['attempts'],2)
        result=new.acknowledge('ANTI-01','A',epochs['A'],self.contract,delivery)
        self.assertEqual(result['status'],'ACKED');self.assertTrue(new.acknowledge('ANTI-01','A',epochs['A'],self.contract,delivery)['idempotent'])
        with self.assertRaises(Denied):new.delivery_attempt('CODEX',delivery)
    def test_wrong_owner_and_delivery_rejected(self):
        epochs=self.start();delivery=self.store.delivery_outbox('ANTI-01')[0]['id']
        with self.assertRaises(Denied):self.store.delivery_outbox('ANTI-02','A')
        with self.assertRaises(Denied):self.store.delivery_attempt('ANTI-01',delivery)
        with self.assertRaises(Denied):self.store.acknowledge('ANTI-02','A',epochs['A'],self.contract,delivery)
        with self.assertRaises(Denied):self.store.acknowledge('ANTI-01','A',epochs['A'],self.contract,'wrong')
    def test_timeout_freezes_preserves_lock_and_never_replays(self):
        epochs=self.start([self.spec('A')]);delivery=self.store.delivery_outbox('ANTI-01')[0]['id']
        with self.store.transaction() as db:db.execute("UPDATE cc_deliveries SET ack_deadline='2000-01-01T00:00:00+00:00'")
        summary=self.store.supervisor_tick('CODEX');self.assertEqual(summary['frozen'],['A']);self.assertFalse(summary['approval_granted'])
        with self.store.connection() as db:self.assertEqual(db.execute('SELECT state FROM cc_locks').fetchone()[0],'FROZEN')
        self.assertEqual(self.store.get_assignment('CODEX','A')['epoch'],epochs['A'])
        self.assertEqual(self.store.dispatch('CODEX')['assigned'],[])
        with self.assertRaises(Denied):self.store.acknowledge('ANTI-01','A',epochs['A'],self.contract,delivery)
    def test_production_boolean_availability_is_not_attestation(self):
        # Use canonical serialization instead of SQL quoting for policy.
        import json
        with self.store.transaction() as db:db.execute('UPDATE cc_missions SET policy=?',(json.dumps({'sandbox':False,'max_workers':2}),))
        self.store.queue_wave('CODEX','M','W',[self.spec('A')])
        result=self.store.dispatch('CODEX',availability={'ANTI-01':True})
        self.assertEqual(result['assigned'],[]);self.assertEqual(result['pending'][0]['reason'],'VERIFIED_RUNTIME_ATTESTATION_REQUIRED')
    def test_supervisor_worker_denied_and_summary_persists(self):
        self.start([self.spec('A')])
        with self.assertRaises(Denied):self.store.supervisor_tick('ANTI-01')
        result=self.store.supervisor_tick('CODEX');self.assertFalse(result['approval_granted'])
        self.assertTrue(ControlStore(self.dbpath).snapshot()['supervisor_summaries'])
if __name__=='__main__':unittest.main()
