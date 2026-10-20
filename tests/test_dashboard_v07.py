import json
from pathlib import Path
from unittest.mock import patch
import unittest
from tests import test_dashboard as dashboard_base
from registry import Denied


class TestDashboardV07(unittest.TestCase):
    setUp=dashboard_base.TestDashboard.setUp
    call=dashboard_base.TestDashboard.call
    login=dashboard_base.TestDashboard.login
    def test_backup_auth_csrf_and_manifest(self):
        self.assertEqual(self.call('/ui/api/backup',{})[0],401)
        self.login()
        self.assertEqual(self.call('/ui/api/backup',{},csrf=False)[0],403)
        self.assertEqual(self.call('/ui/api/backup',{},origin=False)[0],403)
        status,data=self.call('/ui/api/backup',{'out':'C:/untrusted'})
        self.assertEqual(status,200)
        manifest=data['result']
        self.assertEqual(manifest['sqlite_integrity_check'],'ok')
        self.assertEqual(manifest['restoration'],'MANUAL_ONLY')
        self.assertFalse(manifest['includes_oauth_tokens'])
        self.assertTrue((Path(self.tmp.name)/'backups'/manifest['snapshot']).is_file())
        for token in self.tokens.values():self.assertNotIn(token,json.dumps(data))
        self.assertNotIn('C:/untrusted',json.dumps(data))

    def test_task_evidence_authenticated_dedicated_read(self):
        self.assertEqual(self.call('/ui/api/task-evidence?tid=T1')[0],401)
        self.login()
        self.db.create_task('CODEX','T1','Evidence','module','bounded task',self.sha)
        self.db.assign('CODEX','T1','ANTI-01')
        with patch.object(self.db,'qa_evidence',return_value=[{'commit_sha':self.sha,'changed_paths':['module/a.py'],'result':'FAIL'}]) as read:
            status,data=self.call('/ui/api/task-evidence?tid=T1')
            self.assertEqual(status,200)
            read.assert_called_once_with('CODEX','T1')
        result=data['result']
        self.assertEqual(result['independent_qa'][0]['result'],'FAIL')
        self.assertEqual(result['task']['id'],'T1')
        self.assertEqual(result['feedback']['history'],[])
        self.assertEqual(result['diff_content'],'NOT_LOADED')
        self.assertEqual(self.call('/ui/api/task-evidence?tid=missing')[0],404)

    def test_ui_reality_labels_and_no_file_read_endpoint(self):
        _,html=self.call('/ui')
        self.assertIn(b'LOGICAL_ONLY',html)
        self.assertIn(b'Git &amp; Diff',html)
        self.assertEqual(self.call('/ui/api/task-evidence?path=C:/Windows/win.ini')[0],401)
        _,js=self.call('/ui/dashboard.js')
        self.assertIn(b'Quota:',js)
        self.assertIn(b'NOT_VERIFIED',js)
        self.assertIn(b'OWNER_APPROVAL_REQUIRED',js)

    def test_manual_account_switch_guide_does_not_handle_credentials_or_claim_runtime(self):
        status,js=self.call('/ui/dashboard.js')
        self.assertEqual(status,200)
        source=js.decode('utf-8')
        for expected in ('data-act="account-switch"','ANTI-01','ANTI-02',
                         'C:\\\\KTOOL\\\\Workspaces\\\\${escapeHtml(selected)}',
                         'đăng xuất/đăng nhập chính thức','actor: ${escapeHtml(selected)}',
                         'Resume task FROZEN','NOT_VERIFIED'):
            self.assertIn(expected,source)
        self.assertNotIn('/ui/api/account-switch',source)
        self.assertNotIn('oauth_token',source.lower())
        status,css=self.call('/ui/dashboard.css')
        self.assertEqual(status,200)
        self.assertIn(b'.switch-guide',css)

    def test_remote_control_is_human_handoff_only(self):
        status,js=self.call('/ui/dashboard.js')
        self.assertEqual(status,200)
        source=js.decode('utf-8')
        for expected in ('https://antigravity.google/','Mở Antigravity Remote Control',
                         'target="_blank" rel="noopener noreferrer"',
                         'Trạng thái Remote Control trong K-TOOL: UNKNOWN',
                         'K-TOOL không có API được hỗ trợ'):
            self.assertIn(expected,source)
        self.assertNotIn('/ui/api/remote-control',source)

    def test_manual_switch_freeze_keeps_lock_and_resume_remains_blocked(self):
        self.db.create_task('CODEX','SWITCH1','Switch handoff','module/switch','bounded task',self.sha)
        self.db.assign('CODEX','SWITCH1','ANTI-01')
        self.login()
        status,data=self.call('/ui/api/freeze',{'tid':'SWITCH1','reason':'Manual account switch handoff'})
        self.assertEqual(status,200)
        self.assertFalse(data['result']['lock_released'])
        snapshot=self.db.dashboard_snapshot('CODEX')
        task=next(t for t in snapshot['tasks'] if t['id']=='SWITCH1')
        lock=next(l for l in snapshot['locks'] if l['task_id']=='SWITCH1')
        self.assertEqual(task['state'],'FROZEN')
        self.assertEqual(lock['state'],'FROZEN')
        self.assertEqual(self.db.resume_frozen_task.__name__,'resume_frozen_task')
        with self.assertRaises(Denied):
            self.db.resume_frozen_task('CODEX','SWITCH1','ANTI-01',True,True)
