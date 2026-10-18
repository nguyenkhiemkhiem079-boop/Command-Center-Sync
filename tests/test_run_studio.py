import sys
import types
import unittest
from unittest.mock import Mock, patch
from tests import test_dashboard as base

class TestRunStudio(unittest.TestCase):
    setUp=base.TestDashboard.setUp
    call=base.TestDashboard.call
    login=base.TestDashboard.login

    def test_auth_and_controller_snapshot(self):
        fixture={k:[] for k in ('missions','waves','teams','assignments','subagents','revisions','steering','human_requests','events','performance')}
        fixture.update(supervisor_mode='TEST_ONLY',isolation_level='LOGICAL_ONLY',source='TEST_FIXTURE',last_verified_at=None)
        controller=Mock();controller.snapshot.return_value=fixture
        module=types.ModuleType('orchestration');module.ControlStore=Mock(return_value=controller)
        with patch.dict(sys.modules,{'orchestration':module}):
            self.assertEqual(self.call('/ui/api/run-studio')[0],401)
            module.ControlStore.assert_not_called()
            self.login()
            code,data=self.call('/ui/api/run-studio')
        self.assertEqual(code,200);self.assertEqual(data['result'],fixture)
        module.ControlStore.assert_called_once_with(self.db.dbfile)
        controller.snapshot.assert_called_once_with('CODEX')

    def test_fail_closed_without_controller(self):
        self.login()
        with patch.dict(sys.modules,{'orchestration':None}):
            code,data=self.call('/ui/api/run-studio')
        self.assertEqual(code,503);self.assertEqual(data['error'],'CONTROL_STORE_UNAVAILABLE')

    def test_controller_error_is_not_exposed(self):
        self.login()
        module=types.ModuleType('orchestration');module.ControlStore=Mock(side_effect=RuntimeError('sensitive internal detail'))
        with patch.dict(sys.modules,{'orchestration':module}):
            code,data=self.call('/ui/api/run-studio')
        self.assertEqual(code,500);self.assertNotIn('sensitive',str(data))

    def test_original_ui_and_unknown_defaults(self):
        self.assertIn(b'Run Studio',self.call('/ui')[1])
        js=self.call('/ui/dashboard.js')[1]
        for text in (b'Hierarchy tree',b'Workflow revisions',b'Wave timeline',b'Steering inbox',b'Human requests',b'Evidence vault',b'Performance',b'last_verified_at',b'UNKNOWN'):
            self.assertIn(text,js)
        self.assertNotIn(b'localStorage',js)

    def rpc(self,role,op,args=None):
        import json
        from urllib.request import Request
        from urllib.error import HTTPError
        req=Request(self.base+'/rpc',data=json.dumps({'op':op,'args':args or {}}).encode(),headers={'Authorization':'Bearer '+self.tokens[role],'Content-Type':'application/json'})
        try:
            with self.opener.open(req) as response:return response.status,json.load(response)
        except HTTPError as exc:return exc.code,json.load(exc)

    def controller_fixture(self):
        # TEST ONLY: direct DB record tests HTTP role/epoch dispatch without pretending execution.
        from orchestration import ControlStore
        control=ControlStore(self.db.dbfile)
        with control.transaction() as db:
            db.execute("INSERT INTO cc_assignments(id,mission,wave,team,owner,contract_hash,revision,repo,base_sha,allowed,readonly,forbidden,resources,dependencies,acceptance,capabilities,priority,status,epoch,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('A1','M1','W1','T1','ANTI-01','test-contract','test-revision',self.tmp.name,self.sha,'[\"module\"]','[]','[]','[]','[]','[\"test\"]','[]',0,'TASK_ASSIGNED',1,'TEST_ONLY'))
        return control

    def test_control_roles_ack_and_frozen_guard(self):
        control=self.controller_fixture()
        self.assertEqual(self.rpc('ANTI-01','control_snapshot')[0],403)
        self.assertEqual(self.rpc('CODEX','control_snapshot')[0],200)
        self.assertEqual(self.rpc('ANTI-02','get_assignment',{'assignment':'A1'})[0],403)
        self.assertEqual(self.rpc('ANTI-01','get_assignment',{'assignment':'A1'})[0],200)
        args={'assignment':'A1','epoch':1,'contract_hash':'test-contract','actor':'ANTI-01'}
        self.assertEqual(self.rpc('ANTI-02','acknowledge_assignment',args)[0],403)
        self.assertEqual(self.rpc('ANTI-01','acknowledge_assignment',dict(args,contract_hash='wrong'))[0],409)
        self.assertEqual(self.rpc('ANTI-01','acknowledge_assignment',args)[0],200)
        self.assertEqual(control.get_assignment('CODEX','A1')['status'],'DEVELOPMENT')
        self.db.emergency_stop('CODEX','test interruption')
        self.assertEqual(self.rpc('CODEX','dispatch')[0],423)
        self.assertEqual(self.rpc('ANTI-01','acknowledge_assignment',args)[0],423)

    def test_no_remote_approval_and_emergency_updates_both(self):
        control=self.controller_fixture()
        self.assertEqual(self.rpc('CODEX','approve_contract',{'contract_hash':'x'})[0],400)
        self.assertEqual(self.rpc('CODEX','accept',{'assignment':'A1'})[0],400)
        self.assertEqual(self.rpc('ANTI-01','propose_contract',{'contract_id':'c','content':{'acceptance_criteria':['ok']}})[0],403)
        self.assertEqual(self.rpc('CODEX','emergency_stop',{'reason':'test emergency stop'})[0],200)
        self.assertEqual(control.snapshot()['supervisor_mode'],'EMERGENCY_STOP')
        self.assertEqual(self.db.control_status('CODEX')['mode'],'EMERGENCY_STOP')
        self.assertEqual(self.call('/health')[0],200)
