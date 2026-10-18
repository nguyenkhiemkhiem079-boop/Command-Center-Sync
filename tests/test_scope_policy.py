import copy,json,os,subprocess,sys,unittest
from pathlib import Path
from tests import test_scope_gate as fixtures
from ci_scope_gate import verify_policy
class ScopePolicyTests(unittest.TestCase):
    setUp=fixtures.ScopeGateTests.setUp
    git=fixtures.ScopeGateTests.git
    commit=fixtures.ScopeGateTests.commit
    def policy(self):return {'schema_version':1,'repository':'fixture/repo','approval_state':'OWNER_APPROVED','protected_paths':['module/tests','shared-core'],'assignments':{'A':{'scope':'module','allowed_paths':['module'],'resource_locks':[],'required_resource_locks':[]}}}
    def candidate(self):
        (self.repo/'module/a').write_text('changed');return self.commit()
    def test_approved_fixture_scope_real_commit(self):self.assertTrue(verify_policy(self.repo,self.base,self.candidate(),self.policy(),'A','fixture/repo')['pass'])
    def test_pending_policy_missing_assignment_wrong_repo_denied(self):
        head=self.candidate();p=self.policy();p['approval_state']='PENDING_OWNER_APPROVAL'
        with self.assertRaises(ValueError):verify_policy(self.repo,self.base,head,p,'A')
        for assignment,repo in [('OTHER','fixture/repo'),('A','other/repo')]:
            with self.assertRaises(ValueError):verify_policy(self.repo,self.base,head,self.policy(),assignment,repo)
    def test_shared_resource_and_traversal_denied(self):
        head=self.candidate();p=self.policy();p['assignments']['A']['required_resource_locks']=['core']
        with self.assertRaises(ValueError):verify_policy(self.repo,self.base,head,p,'A')
        p=self.policy();p['assignments']['A']['allowed_paths']=['module/../outside']
        self.assertFalse(verify_policy(self.repo,self.base,head,p,'A')['pass'])
    def test_protected_profile_and_rename_escape(self):
        (self.repo/'module/tests/test.txt').write_text('weakened');self.git('mv','module/a','outside')
        r=verify_policy(self.repo,self.base,self.commit(),self.policy(),'A');self.assertFalse(r['pass']);self.assertIn('outside',r['changed_paths'])
    def test_policy_on_disk_pending_fails_closed(self):
        root=Path(__file__).resolve().parents[1]
        p=subprocess.run([sys.executable,str(root/'ci_scope_gate.py'),'--repo',str(self.repo),'--base',self.base,'--commit',self.candidate(),'--policy',str(root/'.github/scope-policy.json'),'--assignment','CI-PILOT'],capture_output=True,text=True)
        self.assertEqual(p.returncode,2);self.assertIn('OWNER_APPROVED_BASE_POLICY_REQUIRED',p.stdout)
if __name__=='__main__':unittest.main()
