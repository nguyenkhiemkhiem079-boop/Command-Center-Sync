import unittest
from tests import test_orchestration as fixtures
from worktree_manager import inspect,create
from registry import Denied
class WorktreeTests(unittest.TestCase):
    setUp=fixtures.OrchestrationTests.setUp
    git=fixtures.OrchestrationTests.git
    spec=fixtures.OrchestrationTests.spec
    start=fixtures.OrchestrationTests.start
    candidate=fixtures.OrchestrationTests.candidate
    def test_create_refuses_overwrite_and_escape(self):
        workspace=self.root/'approved';workspace.mkdir()
        result=create('CODEX',self.repo,self.base,workspace/'new','pilot-new',workspace)
        self.assertEqual(result['base_sha'],self.base)
        with self.assertRaises(Denied):create('CODEX',self.repo,self.base,workspace/'new','another',workspace)
        with self.assertRaises(Denied):create('CODEX',self.repo,self.base,self.root/'escape','escape',workspace)
        with self.assertRaises(Denied):create('ANTI-01',self.repo,self.base,workspace/'worker','bad',workspace)
    def test_two_workers_same_worktree_rejected_atomically(self):
        specs=[self.spec('A'),self.spec('B',repo=str(self.repos['A']))]
        with self.assertRaisesRegex(Denied,'CANT_EDIT_WORKTREE_OWNER'):self.store.queue_wave('CODEX','M','W',specs)
        self.assertEqual(self.store.snapshot()['assignments'],[])
    def test_subdirectory_and_branch_switch_rejected(self):
        sub=self.repos['A']/'nested';sub.mkdir()
        with self.assertRaises(Denied):inspect(sub,self.base)
        epoch=self.start([self.spec('A')])['A'];self.store.acknowledge('ANTI-01','A',epoch,self.contract)
        sha,paths=self.candidate('A');self.git(self.repos['A'],'switch','-c','wrong-owner-branch')
        with self.assertRaisesRegex(Denied,'WORKTREE_OWNERSHIP_REVALIDATION_REQUIRED'):self.store.checkpoint('ANTI-01','A',epoch,sha,paths,{})
if __name__=='__main__':unittest.main()
