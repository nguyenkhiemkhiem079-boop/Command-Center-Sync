import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from anti_runtime import Assignment, Mode, StreamAudit, build_argv, capabilities, parse_file, supervise

CID = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'


def init():
    return {'event':'init','conversation_id':CID,'init':{'secret':'NEVER_SAVE'}}


def result(**changes):
    body = dict(conversation_id=CID,status='SUCCESS',response='done')
    body.update(changes)
    return {'event':'result','result':body}


class RuntimeTests(unittest.TestCase):
    def audit(self,*events,**finish):
        audit = StreamAudit()
        for event in events:
            audit.feed(json.dumps(event))
        return audit.finish(**finish)

    def test_success_is_unverified_not_acceptance(self):
        value = self.audit(init(),result())
        self.assertEqual(value['status'],'COMPLETED_UNVERIFIED')
        self.assertFalse(value['native_teamwork_accepted'])

    def test_denied_success_is_blocked(self):
        value = self.audit(init(),result(denied_actions=[{'secret':'TOKEN'}],response=''))
        self.assertEqual(value['status'],'BLOCKED')
        self.assertIn('DENIED_ACTIONS',value['flags'])

    def test_tool_error_survives_success_and_redacts_everything(self):
        event = {'event':'step_update','step_update':{'conversation_id':CID,'step_type':'tool',
            'state':'ERROR','tool_name':'run_command','text_delta':'PRIVATE_REASONING',
            'tool_info':{'parameters':{'password':'SECRET'},'output':'PRIVATE_OUTPUT',
                         'error':{'message':'SECRET_ERROR'}}}}
        value = self.audit(init(),event,result())
        self.assertEqual(value['status'],'FAIL')
        serialized = json.dumps(value)
        for secret in ('NEVER_SAVE','PRIVATE_REASONING','PRIVATE_OUTPUT','SECRET_ERROR','password','parameters','text_delta'):
            self.assertNotIn(secret,serialized)

    def test_empty_missing_timeout_nonzero_and_malformed_fail_closed(self):
        self.assertEqual(self.audit(init(),result(response=''))['status'],'FAIL')
        self.assertEqual(self.audit(init())['status'],'FAIL')
        self.assertEqual(self.audit(init(),result(),exit_code=7)['status'],'FAIL')
        self.assertEqual(self.audit(init(),result(),timed_out=True)['status'],'BLOCKED')
        audit=StreamAudit();audit.feed('not json')
        self.assertEqual(audit.finish()['status'],'FAIL')

    def test_conversation_continuity_and_duplicate_results(self):
        self.assertIn('CONVERSATION_CHANGED',self.audit(init(),result(conversation_id=OTHER))['flags'])
        self.assertIn('INVALID_EVENT_ORDER',self.audit(init(),result(),result())['flags'])
        audit = StreamAudit(expected_conversation=OTHER)
        audit.feed(json.dumps(init()))
        audit.feed(json.dumps(result()))
        self.assertEqual(audit.finish()['status'],'FAIL')

    def test_local_pilots_blocked_despite_success(self):
        folder=ROOT.parent/'evidence-v07'
        for name in ('agy-01-teamwork.jsonl','agy-02-teamwork.jsonl'):
            with self.subTest(name=name):
                path=folder/name
                if not path.exists():
                    self.skipTest('Captured pilot logs are not distributed with this source')
                value=parse_file(path)
                self.assertEqual(value['status'],'BLOCKED')
                self.assertGreater(value['denied_actions'],0)
                self.assertGreater(value['tool_errors'],0)
                self.assertIn('EMPTY_RESPONSE',value['flags'])

    def test_modes_argv_and_no_native_entitlement_inference(self):
        with tempfile.TemporaryDirectory() as temp:
            task=Assignment('ANTI-01','A','arch',Path(temp),1)
            detected={'executable':sys.executable,'AGY_HEADLESS':True,'TEAMWORK_NATIVE':False}
            argv=build_argv(sys.executable,Mode.AGY_HEADLESS,'fix scope',task,detected,resume=CID)
            self.assertEqual(argv[-2:],['--conversation',CID])
            self.assertNotIn('--dangerously-skip-permissions',argv)
            with self.assertRaises(RuntimeError):
                build_argv(sys.executable,Mode.TEAMWORK_NATIVE,'task',task,detected)
            with self.assertRaises(RuntimeError):
                build_argv(sys.executable,Mode.SUPERVISED_IDE,'task',task,detected)
            value=capabilities('--print --output-format --conversation',sys.executable)
            self.assertTrue(value['AGY_HEADLESS'])
            self.assertFalse(value['TEAMWORK_NATIVE'])
            self.assertIn('UNAVAILABLE',value['api_coding_worker'])

    def test_native_teamwork_flags_cannot_fabricate_attestation(self):
        value=capabilities('--print --output-format --conversation',sys.executable,
                           native_teamwork_verified=True)
        self.assertFalse(value['TEAMWORK_NATIVE'])
        self.assertFalse(value['native_teamwork_verified'])
        with tempfile.TemporaryDirectory() as temp:
            task=Assignment('ANTI-01','A','arch',Path(temp),1)
            fabricated={'executable':sys.executable,'AGY_HEADLESS':True,'TEAMWORK_NATIVE':True,
                        'native_teamwork_verified':True}
            with self.assertRaisesRegex(RuntimeError,'SUPERVISED_MANUAL_LAUNCH_REQUIRED'):
                build_argv(sys.executable,Mode.TEAMWORK_NATIVE,'task',task,fabricated)

    def test_fixture_process_success_and_timeout_no_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            task=Assignment('ANTI-02','B','docs',Path(temp),9)
            code='import json;print('+repr(json.dumps(init()))+');print('+repr(json.dumps(result()))+')'
            value=supervise([sys.executable,'-c',code],task,timeout_seconds=5)
            self.assertEqual(value['status'],'COMPLETED_UNVERIFIED')
            self.assertEqual(value['assignment']['fencing'],9)
            value=supervise([sys.executable,'-c','import time;time.sleep(30)'],task,timeout_seconds=.2)
            self.assertEqual(value['status'],'BLOCKED')
            self.assertIn('TIMEOUT',value['flags'])
            self.assertFalse(value['automatic_restart'])


if __name__=='__main__':
    unittest.main()
