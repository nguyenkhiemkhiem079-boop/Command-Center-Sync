import unittest
from tests import test_orchestration as fixtures
from mission_recovery import checkpoint_package,verify_checkpoint_package,mission_result
from registry import Denied
class MissionRecoveryTests(unittest.TestCase):
    setUp=fixtures.OrchestrationTests.setUp
    git=fixtures.OrchestrationTests.git
    spec=fixtures.OrchestrationTests.spec
    start=fixtures.OrchestrationTests.start
    candidate=fixtures.OrchestrationTests.candidate
    def test_source_bundle_log_contract_epoch_bound(self):
        epoch=self.start([self.spec('A')])['A'];self.store.acknowledge('ANTI-01','A',epoch,self.contract)
        sha,paths=self.candidate('A');self.store.checkpoint('ANTI-01','A',epoch,sha,paths,{})
        log=self.root/'test.log';log.write_text('TEST_FIXTURE_LOG_NOT_EXECUTION_PROOF')
        result=checkpoint_package(self.store,'CODEX','A',self.root/'package',[log])
        self.assertEqual(verify_checkpoint_package(self.store,'CODEX',result)['status'],'LOCAL_VERIFIED')
        log.write_text('tampered')
        with self.assertRaises(Denied):verify_checkpoint_package(self.store,'CODEX',result)
    def test_wrong_owner_and_missing_source_denied_summary_never_approves(self):
        self.start([self.spec('A')])
        with self.assertRaises(Denied):checkpoint_package(self.store,'ANTI-01','A',self.root/'bad',[])
        with self.assertRaises(Denied):checkpoint_package(self.store,'CODEX','A',self.root/'bad',[])
        summary=mission_result(self.store,'CODEX','M');self.assertEqual(summary['production_approval'],'NOT_INFERRED')
        self.assertFalse(summary['provider_completion_is_acceptance'])
if __name__=='__main__':unittest.main()
