import json
from urllib.request import Request, urlopen
from tests.test_dashboard import TestDashboard


class AgentWorldDashboardTests(TestDashboard):
    def test_dashboard_adds_agent_world_without_removing_existing_views(self):
        status, html = self.call('/ui')
        self.assertEqual(status, 200)
        self.assertIn(b'data-page="agentworld"', html)
        self.assertIn(b'data-page="fleet"', html)
        self.assertIn(b'data-page="studio"', html)
        self.assertIn(b'/ui/agent-world.css', html)

    def test_bundled_assets_are_same_origin_and_exactly_whitelisted(self):
        for route, expected in [
            ('/ui/agent-world.css', b'.aw-shell'),
            ('/ui/agent-world/agent-world.js', b'WebGL2'),
            ('/ui/agent-world/three-LICENSE.txt', b'MIT License'),
        ]:
            status, body = self.call(route)
            self.assertEqual(status, 200, route)
            self.assertIn(expected, body, route)
        self.assertEqual(self.call('/ui/agent-world/unlisted.js')[0], 404)
        self.assertEqual(self.call('/ui/agent-world/%2e%2e%2fprivate%2froles.json')[0], 404)

    def test_csp_and_authenticated_cockpit_observation(self):
        request = Request(self.base + '/ui')
        with urlopen(request, timeout=5) as response:
            csp = response.headers.get('Content-Security-Policy', '')
        self.assertIn("script-src 'self'", csp)
        self.assertNotIn('unsafe-inline', csp)
        self.assertEqual(self.call('/ui/api/cockpit')[0], 401)
        self.login()
        status, data = self.call('/ui/api/cockpit')
        self.assertEqual(status, 200)
        identities = data['result']['identity_layers']
        self.assertEqual([record['id'] for record in identities], ['CODEX', 'ANTI-01', 'ANTI-02'])
        for record in identities:
            self.assertEqual(record['runtime']['teamwork'], 'UNKNOWN')
        self.assertEqual(data['result']['source'], 'CONTROLLER_METADATA_PROJECTION')


if __name__ == '__main__':
    import unittest
    unittest.main()
