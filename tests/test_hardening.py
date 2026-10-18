"""Real Git regression coverage for independent QA and Windows lock inputs."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from qa_runner import assess
from registry import Registry, Denied, clean_scope


class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'QA regression')
        self.git('config', 'user.email', 'qa@example.test')
        (self.repo / 'README.md').write_text('base\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'base')
        self.base = self.git('rev-parse', 'HEAD')
        (self.repo / 'arch').mkdir()
        (self.repo / 'arch' / 'new.txt').write_text('implementation\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'implementation')
        self.head = self.git('rev-parse', 'HEAD')
        self.dbpath = self.root / 'registry.db'
        self.db = Registry(self.dbpath)

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.repo, check=True,
                              capture_output=True, text=True).stdout.strip()

    def submit(self, base=None, head=None):
        head = head or self.head
        self.db.create_task('CODEX', 'A', 'Regression', 'arch', 'QA regression',
                            base or self.base, requires_preview=False)
        fence = self.db.assign('CODEX', 'A', 'ANTI-01')['fencing']
        self.db.submit_self_qa('ANTI-01', 'A', fence, head, ['arch/new.txt'],
            dict(scope=True, diff=True, regression=True, safety=True),
            'PASS', 'PASS', 'NOT_APPLICABLE', 'qa/self.json')
        self.db.submit_result('ANTI-01', 'A', fence, head, 'Implemented regression fixture',
                              'PASS', 'PASS', 'qa/result.json')

    def run_qa(self, test_code='print("tests passed")'):
        profile = self.root / 'profile.json'
        profile.write_text(json.dumps({'build': [sys.executable, '-c', 'print("build passed")'],
                                     'tests': [sys.executable, '-c', test_code]}))
        return assess(self.dbpath, 'A', self.repo, profile)

    def test_valid_descendant_clean_checkout_passes(self):
        self.submit()
        self.assertEqual(self.run_qa()['result'], 'PASS')

    def test_tests_dirty_tracked_source_fail(self):
        self.submit()
        result = self.run_qa('from pathlib import Path; Path("arch/new.txt").write_text("changed")')
        self.assertEqual(result['result'], 'FAIL')

    def test_tests_change_head_fail(self):
        self.submit()
        code = 'import subprocess; subprocess.run(["git","checkout","--detach","' + self.base + '"],check=True)'
        self.assertEqual(self.run_qa(code)['result'], 'FAIL')

    def test_nonancestor_baseline_never_executes_commands(self):
        self.git('checkout', '--orphan', 'unrelated')
        self.git('add', '.')
        self.git('commit', '-qm', 'unrelated identical implementation tree')
        orphan = self.git('rev-parse', 'HEAD')
        self.submit(head=orphan)
        marker = self.root / 'should-not-exist'
        code = 'from pathlib import Path; Path(' + repr(str(marker)) + ').write_text("executed")'
        self.assertEqual(self.run_qa(code)['result'], 'FAIL')
        self.assertFalse(marker.exists())

    def test_windows_alias_scopes_rejected(self):
        for scope in ('arch.', 'arch ', 'arch./file', 'arch /file', '/arch',
                      '\\arch', 'C:/arch', 'arch/NUL.txt', 'COM1/file', 'arch/a?b'):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                clean_scope(scope)
        self.assertEqual(clean_scope('Arch\\Module'), 'arch/module')

    def test_nonboolean_stop_confirmation_denied(self):
        for value in ('false', 'true', 1, [], None):
            with self.subTest(value=value), self.assertRaisesRegex(Denied, 'VERIFIED_INTEGRATION_PROOF_REQUIRED'):
                self.db.close_task('CODEX', 'not-even-created', 'a' * 40, value)


if __name__ == '__main__':
    unittest.main()
