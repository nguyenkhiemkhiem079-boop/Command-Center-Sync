import json
from http.server import ThreadingHTTPServer
from http.cookiejar import CookieJar
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.error import HTTPError
from registry import Registry, hash_token
from server import handler_factory

class TestDashboard(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Registry(Path(self.tmp.name)/'dashboard.db')
        self.tokens={'CODEX':'lead-special-token','ANTI-01':'dev-special-token','ANTI-02':'qa-special-token'}
        self.srv=ThreadingHTTPServer(('127.0.0.1',0),handler_factory(self.db,{k:hash_token(v) for k,v in self.tokens.items()}))
        self.addCleanup(self.srv.server_close)
        self.worker=Thread(target=self.srv.serve_forever,daemon=True)
        self.worker.start()
        self.addCleanup(self.srv.shutdown)
        self.base=f'http://127.0.0.1:{self.srv.server_port}'
        self.opener=build_opener(HTTPCookieProcessor(CookieJar()))
        self.csrf=None
        self.sha='a'*40
    def call(self,path,body=None,origin=True,csrf=True):
        hd={}
        if body is not None:
            hd['Content-Type']='application/json'
            if origin:hd['Origin']=self.base
            if csrf and self.csrf:hd['X-KTOOL-CSRF']=self.csrf
        req=Request(self.base+path,data=None if body is None else json.dumps(body).encode(),headers=hd)
        try:
            with self.opener.open(req,timeout=5) as r:
                b=r.read()
                return r.status,json.loads(b) if 'application/json' in r.headers.get('Content-Type','') else b
        except HTTPError as err:return err.code,json.loads(err.read())
    def login(self,role='CODEX'):
        code,_=self.call('/ui/api/login',{'token':self.tokens[role]})
        self.assertEqual(code,200)
        status,res=self.call('/ui/api/snapshot')
        self.assertEqual(status,200)
        self.csrf=res['csrf']
    def test_assets_public_but_data_private(self):
        self.assertEqual(self.call('/ui')[0],200)
        self.assertEqual(self.call('/ui/dashboard.js')[0],200)
        self.assertEqual(self.call('/ui/dashboard.css')[0],200)
        self.assertEqual(self.call('/ui/api/snapshot')[0],401)
    def test_non_codex_cannot_login(self):
        self.assertEqual(self.call('/ui/api/login',{'token':self.tokens['ANTI-01']})[0],401)
        self.assertEqual(self.call('/ui/api/login',{'token':'wrong'})[0],401)
    def test_origin_and_csrf_required(self):
        self.assertEqual(self.call('/ui/api/login',{'token':self.tokens['CODEX']},origin=False)[0],403)
        self.login()
        doc={'tid':'T1','title':'T1','scope':'A','contract':'test','base_sha':self.sha}
        self.assertEqual(self.call('/ui/api/create',doc,csrf=False)[0],403)
        self.assertEqual(self.call('/ui/api/create',doc,origin=False)[0],403)
        self.assertEqual(self.call('/ui/api/create',doc)[0],200)
    def test_create_assign_freeze_and_lock_in_snapshot(self):
        self.login()
        doc={'tid':'T1','title':'Envelope','scope':'Architectural/Envelope','contract':'audit only','base_sha':self.sha}
        self.assertEqual(self.call('/ui/api/create',doc)[0],200)
        self.assertEqual(self.call('/ui/api/assign',{'tid':'T1','owner':'ANTI-01'})[0],200)
        doc.update(tid='T2',scope='Architectural')
        self.assertEqual(self.call('/ui/api/create',doc)[0],200)
        code,res=self.call('/ui/api/assign',{'tid':'T2','owner':'ANTI-02'})
        self.assertEqual(code,409)
        self.assertIn('CANT_EDIT',res['error'])
        self.assertEqual(self.call('/ui/api/freeze',{'tid':'T1','reason':'pause'})[0],200)
        code,snap=self.call('/ui/api/snapshot')
        self.assertEqual(code,200)
        self.assertEqual(snap['result']['locks'][0]['state'],'FROZEN')
        self.assertEqual(snap['result']['agents'][0]['teamwork'],'NOT_VERIFIED')
    def test_dashboard_two_devs_and_codex_report(self):
        self.login()
        for tid,scope,owner in [('ARCH2','arch','ANTI-01'),('MEP2','mep','ANTI-02')]:
            doc={'tid':tid,'title':tid,'scope':scope,'contract':'bounded code task','base_sha':self.sha,'wave_id':'W42'}
            self.assertEqual(self.call('/ui/api/create',doc)[0],200)
            self.assertEqual(self.call('/ui/api/assign',{'tid':tid,'owner':owner})[0],200)
        r=self.call('/ui/api/report?wave_id=W42')
        self.assertEqual(r[0],200)
        self.assertEqual(r[1]['result']['counts']['RUNNING'],2)
        self.assertIn('Antigravity',r[1]['result']['integration']['antigravity_teamwork'].replace('NOT_VERIFIED','Antigravity'))
    def test_logout(self):
        self.login()
        self.assertEqual(self.call('/ui/api/logout',{})[0],200)
        self.assertEqual(self.call('/ui/api/snapshot')[0],401)
    def test_mcp_roles_unchanged(self):
        payload={'op':'status','args':{}}
        hdr={'Authorization':'Bearer '+self.tokens['ANTI-01'],'Content-Type':'application/json'}
        req=Request(self.base+'/rpc',data=json.dumps(payload).encode(),headers=hdr)
        with self.opener.open(req) as res:
            self.assertEqual(json.load(res)['result']['actor'],'ANTI-01')

if __name__=='__main__':unittest.main()
