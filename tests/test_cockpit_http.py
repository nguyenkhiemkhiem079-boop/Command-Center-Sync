import unittest
from tests import test_dashboard as dashboard
from tests import test_run_studio as studio
class CockpitHttpTests(unittest.TestCase):
    setUp=dashboard.TestDashboard.setUp
    call=dashboard.TestDashboard.call
    login=dashboard.TestDashboard.login
    rpc=studio.TestRunStudio.rpc
    def test_cockpit_session_and_bad_diff_query(self):
        self.assertEqual(self.call('/ui/api/cockpit')[0],401)
        self.assertEqual(self.call('/ui/api/assignment-diff?assignment=missing')[0],401)
        self.login();code,data=self.call('/ui/api/cockpit')
        self.assertEqual(code,200);self.assertEqual(data['result']['owner_approval_action'],'DISABLED_EXTERNAL_PRINCIPAL_REQUIRED')
        self.assertEqual(self.call('/ui/api/assignment-diff?path=C:/Windows/win.ini&arbitrary=yes')[0],400)
        self.assertIn(b'Fleet Cockpit',self.call('/ui')[1]);self.assertEqual(self.call('/ui/cockpit.js')[0],200)
    def test_backend_principal_from_bearer_not_body(self):
        code,data=self.rpc('ANTI-01','governance_identity',{'role':'OWNER','actor':'CODEX','environment':'TEST_FIXTURE'})
        self.assertEqual(code,200);self.assertEqual(data['result']['role'],'ANTI_WORKER')
        self.assertEqual(self.rpc('ANTI-01','governance_authorize',{'action':'release','role':'OWNER'})[0],403)
        self.assertEqual(self.rpc('ANTI-01','knowledge_publish',{'key':'ADR','content':{'baseline':'weaken'},'provenance':{'source_ref':'test','source_sha256':'a'*64,'kind':'OPERATOR_ASSERTION'}})[0],403)
        self.assertEqual(self.rpc('CODEX','decide_bound_approval',{'request_id':'anything','role':'OWNER','approved':True})[0],403)
if __name__=='__main__':unittest.main()
