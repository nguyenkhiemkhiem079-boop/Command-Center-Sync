"""Concurrent real stdio adapters under one OS user; disposable credentials only.
This validates MCP/RBAC, not Antigravity Teamwork or OS account isolation.
"""
import asyncio
from contextlib import AsyncExitStack
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from registry import Registry, hash_token
from server import handler_factory



class ClientIdentityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ktool-identities-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tokens = {role: secrets.token_urlsafe(36) for role in ('CODEX','ANTI-01','ANTI-02')}
        self.paths = {}
        for role, token in self.tokens.items():
            folder = self.root / 'identities' / role
            folder.mkdir(parents=True)
            self.paths[role] = folder / 'client_token.txt'
            self.paths[role].write_text(token)
        self.store = Registry(self.root / 'registry.db')
        self.http = ThreadingHTTPServer(('127.0.0.1',0),handler_factory(self.store,{r:hash_token(t) for r,t in self.tokens.items()}))
        self.thread = threading.Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_http)
        self.env = dict(os.environ, KTOOL_COORDINATOR_PORT=str(self.http.server_port))
        for name in ('KTOOL_IDENTITY','KTOOL_TOKEN_FILE'):
            self.env.pop(name,None)

    def stop_http(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=5)

    async def adapter(self, stack, role):
        params = StdioServerParameters(command=sys.executable,
            args=[str(ROOT/'client_mcp.py'),'--identity',role,'--token-file',str(self.paths[role])],env=self.env)
        reader,writer = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(reader,writer))
        await session.initialize()
        return session

    async def call(self, session, name, args=None):
        result = await session.call_tool(name,args or {})
        self.assertFalse(result.isError, str(result))
        return json.loads(result.content[0].text)

    async def test_three_concurrent_adapters_same_os_positive_negative_rbac(self):
        async with AsyncExitStack() as stack:
            sessions = {}
            for role in self.tokens:
                sessions[role] = await self.adapter(stack,role)
            states = await asyncio.gather(*(self.call(s,'status') for s in sessions.values()))
            self.assertEqual([x['result']['actor'] for x in states],list(self.tokens))
            for session in sessions.values():
                tools = await session.list_tools()
                self.assertIn('status',[x.name for x in tools.tools])
            codex = sessions['CODEX']
            for tid,scope,worker in [('A','arch','ANTI-01'),('B','docs','ANTI-02')]:
                made = await self.call(codex,'create_task',dict(tid=tid,title='Disposable task',scope=scope,
                    contract='Identity integration test',base_sha='a'*40,requires_preview=False))
                self.assertTrue(made['ok'])
                assigned = await self.call(codex,'assign_task',dict(tid=tid,owner=worker))
                self.assertTrue(assigned['ok'])
            hearts = await asyncio.gather(*(self.call(sessions[r],'heartbeat') for r in ('ANTI-01','ANTI-02')))
            self.assertEqual([x['result']['agent'] for x in hearts],['ANTI-01','ANTI-02'])
            for worker,own,other in [('ANTI-01','A','B'),('ANTI-02','B','A')]:
                self.assertTrue((await self.call(sessions[worker],'get_task',dict(tid=own)))['ok'])
                denied = await self.call(sessions[worker],'get_task',dict(tid=other))
                self.assertEqual(denied['status'],403)
                denied = await self.call(sessions[worker],'emergency_stop',dict(reason='Worker must never administer'))
                self.assertEqual(denied['status'],403)
            self.assertEqual((await self.call(codex,'heartbeat'))['status'],403)

    async def test_mismatch_exits_before_stdio_tools_and_never_prints_token(self):
        command = [sys.executable,str(ROOT/'client_mcp.py'),'--identity','CODEX',
                   '--token-file',str(self.paths['ANTI-01'])]
        process = await asyncio.create_subprocess_exec(*command,env=self.env,
                    stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        stdout,stderr = await asyncio.wait_for(process.communicate(),timeout=20)
        self.assertEqual(process.returncode,2)
        self.assertEqual(stdout,b'')
        self.assertIn(b'identity verification failed',stderr)
        for token in self.tokens.values():
            self.assertNotIn(token.encode(),stdout+stderr)

    async def test_explicit_process_environment_identity(self):
        env = dict(self.env,KTOOL_IDENTITY='ANTI-02',KTOOL_TOKEN_FILE=str(self.paths['ANTI-02']))
        params = StdioServerParameters(command=sys.executable,args=[str(ROOT/'client_mcp.py')],env=env)
        async with stdio_client(params) as (reader,writer):
            async with ClientSession(reader,writer) as session:
                await session.initialize()
                status = await self.call(session,'status')
                self.assertEqual(status['result']['actor'],'ANTI-02')

    async def test_invalid_port_cannot_redirect_credentials(self):
        env = dict(self.env,KTOOL_COORDINATOR_PORT='8876@example.invalid')
        process = await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'client_mcp.py'),
            '--identity','CODEX','--token-file',str(self.paths['CODEX']),env=env,
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        stdout,stderr = await asyncio.wait_for(process.communicate(),timeout=20)
        self.assertNotEqual(process.returncode,0)
        self.assertEqual(stdout,b'')
        self.assertNotIn(self.tokens['CODEX'].encode(),stderr)

    async def test_redirects_never_forward_bearer_credentials(self):
        received = []
        class Receiver(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append(self.headers.get('Authorization'))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{}')
            do_POST = do_GET
            def log_message(self,*args):
                pass
        receiver = ThreadingHTTPServer(('127.0.0.1',0),Receiver)
        receiver_thread = threading.Thread(target=receiver.serve_forever,daemon=True)
        receiver_thread.start()
        try:
            for code in (301,302,303,307,308):
                with self.subTest(code=code):
                    class Redirector(BaseHTTPRequestHandler):
                        def do_POST(self):
                            self.send_response(code)
                            self.send_header('Location',f'http://127.0.0.1:{receiver.server_port}/capture')
                            self.send_header('Content-Length','0')
                            self.end_headers()
                        def log_message(self,*args):
                            pass
                    redirector = ThreadingHTTPServer(('127.0.0.1',0),Redirector)
                    redirect_thread = threading.Thread(target=redirector.serve_forever,daemon=True)
                    redirect_thread.start()
                    try:
                        env = dict(self.env,KTOOL_COORDINATOR_PORT=str(redirector.server_port))
                        process = await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'client_mcp.py'),
                            '--identity','CODEX','--token-file',str(self.paths['CODEX']),env=env,
                            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
                        stdout,stderr = await asyncio.wait_for(process.communicate(),timeout=20)
                        self.assertEqual(process.returncode,2)
                        self.assertEqual(stdout,b'')
                        self.assertEqual(received,[])
                        self.assertNotIn(self.tokens['CODEX'].encode(),stderr)
                    finally:
                        redirector.shutdown()
                        redirector.server_close()
                        redirect_thread.join(timeout=5)
        finally:
            receiver.shutdown()
            receiver.server_close()
            receiver_thread.join(timeout=5)

    async def test_legacy_common_file_without_explicit_identity_cannot_start(self):
        home = self.root/'appdata'/'KTOOLMCP'
        home.mkdir(parents=True)
        (home/'client_token.txt').write_text(self.tokens['CODEX'])
        env = dict(self.env,APPDATA=str(home.parent))
        process = await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'client_mcp.py'),env=env,
                    stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        stdout,stderr = await asyncio.wait_for(process.communicate(),timeout=20)
        self.assertEqual(process.returncode,2)
        self.assertEqual(stdout,b'')


if __name__ == '__main__':
    unittest.main()
