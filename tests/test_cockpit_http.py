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
    def test_summary_failure_is_bounded_api_error(self):
        import sys,types
        from unittest.mock import Mock,patch
        self.login()
        module=types.ModuleType('orchestration');module.ControlStore=Mock(side_effect=RuntimeError('private filesystem detail'))
        with patch.dict(sys.modules,{'orchestration':module}):
            code,data=self.call('/ui/api/snapshot')
        self.assertEqual(code,503);self.assertEqual(data['error'],'REGISTRY_SUMMARY_UNAVAILABLE')
        self.assertNotIn('filesystem',str(data))
    def test_staging_login_does_not_overwrite_other_port_session(self):
        from http.server import ThreadingHTTPServer
        from threading import Thread
        from server import handler_factory
        from registry import Registry,hash_token
        from urllib.request import Request
        import json
        self.login()
        other=ThreadingHTTPServer(('127.0.0.1',0),handler_factory(Registry(self.db.dbfile+'-other'),{r:hash_token(t) for r,t in self.tokens.items()}))
        thread=Thread(target=other.serve_forever,daemon=True);thread.start()
        self.addCleanup(other.server_close);self.addCleanup(thread.join,3);self.addCleanup(other.shutdown)
        origin='http://127.0.0.1:'+str(other.server_port)
        request=Request(origin+'/ui/api/login',data=json.dumps({'token':self.tokens['CODEX']}).encode(),headers={'Content-Type':'application/json','Origin':origin})
        with self.opener.open(request) as response:self.assertEqual(response.status,200)
        self.assertEqual(self.call('/ui/api/snapshot')[0],200)
        jars=[h.cookiejar for h in self.opener.handlers if hasattr(h,'cookiejar')]
        names={cookie.name for jar in jars for cookie in jar}
        self.assertIn('kt_session_'+str(self.srv.server_port),names);self.assertIn('kt_session_'+str(other.server_port),names)
if __name__=='__main__':unittest.main()
