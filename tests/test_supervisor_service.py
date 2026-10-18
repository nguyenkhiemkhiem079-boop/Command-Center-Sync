import io,unittest
from contextlib import redirect_stdout
from tests import test_orchestration as fixtures
from server import SupervisedHTTPServer,handler_factory
from registry import Registry,hash_token
class SupervisorServiceTests(unittest.TestCase):
    setUp=fixtures.OrchestrationTests.setUp
    git=fixtures.OrchestrationTests.git
    spec=fixtures.OrchestrationTests.spec
    start=fixtures.OrchestrationTests.start
    def test_periodic_service_freezes_real_expired_delivery_without_dispatch(self):
        self.start([self.spec('A')])
        with self.store.transaction() as db:db.execute("UPDATE cc_deliveries SET ack_deadline='2000-01-01T00:00:00+00:00'")
        server=SupervisedHTTPServer(('127.0.0.1',0),handler_factory(Registry(self.dbpath),{'CODEX':hash_token('fixture')}),self.store)
        self.addCleanup(server.server_close);server.service_actions()
        self.assertEqual(self.store.get_assignment('CODEX','A')['status'],'FROZEN')
        self.assertIsNotNone(server.supervisor_last_success);self.assertIsNone(server.supervisor_error)
        self.assertEqual(len(self.store.snapshot()['assignments']),1)
    def test_service_error_is_bounded_and_does_not_grant_fallback(self):
        class Broken:
            def supervisor_tick(self,*a):raise OSError('secret filesystem details')
        server=SupervisedHTTPServer(('127.0.0.1',0),handler_factory(Registry(self.dbpath),{'CODEX':hash_token('fixture')}),Broken())
        self.addCleanup(server.server_close);output=io.StringIO()
        with redirect_stdout(output):server.service_actions()
        self.assertEqual(server.supervisor_error,'SUPERVISOR_TICK_FAILED');self.assertIsNone(server.supervisor_last_success)
        self.assertNotIn('secret filesystem',output.getvalue())
if __name__=='__main__':unittest.main()
