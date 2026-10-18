import unittest
from tests import test_orchestration as fixtures
from cockpit import snapshot,assignment_diff,redact_patch
from registry import Denied
class CockpitTests(unittest.TestCase):
    setUp=fixtures.OrchestrationTests.setUp
    git=fixtures.OrchestrationTests.git
    spec=fixtures.OrchestrationTests.spec
    start=fixtures.OrchestrationTests.start
    candidate=fixtures.OrchestrationTests.candidate
    def test_unknown_identity_and_private_timeline(self):
        self.store.event
        data=snapshot(self.store)
        self.assertIn('UNKNOWN',str(data));self.assertEqual(data['owner_approval_action'],'DISABLED_EXTERNAL_PRINCIPAL_REQUIRED')
        with self.assertRaises(Denied):snapshot(self.store,'ANTI-01')
    def test_real_pinned_diff_and_wrong_candidate_path_rejected(self):
        epoch=self.start([self.spec('A')])['A'];self.store.acknowledge('ANTI-01','A',epoch,self.contract)
        sha,paths=self.candidate('A');self.store.checkpoint('ANTI-01','A',epoch,sha,paths,{})
        diff=assignment_diff(self.store,'CODEX','A');self.assertEqual(diff['candidate_sha'],sha);self.assertTrue(diff['scope_pass']);self.assertIn('real source',diff['patch'])
        for kwargs in ({'candidate_sha':'a'*40},{'path':'../../private/roles.json'}):
            with self.assertRaises(Denied):assignment_diff(self.store,'CODEX','A',**kwargs)
        with self.assertRaises(Denied):assignment_diff(self.store,'ANTI-01','A')
    def test_redaction_and_fake_checkpoint_rejected(self):
        self.assertNotIn('secretVALUE',redact_patch('+password=secretVALUE'))
        epoch=self.start([self.spec('A')])['A']
        with self.assertRaises(Denied):assignment_diff(self.store,'CODEX','A')
if __name__=='__main__':unittest.main()
