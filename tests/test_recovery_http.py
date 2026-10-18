import json
from http.cookiejar import CookieJar
from http.server import ThreadingHTTPServer
from tempfile import TemporaryDirectory
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request,build_opener,HTTPCookieProcessor
import unittest
from registry import Registry,hash_token
from server import handler_factory

class TestRecoveryHttp(unittest.TestCase):
 def setUp(self):
  self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.db=Registry(Path(self.tmp.name)/'db.sqlite3')
  self.tokens={'CODEX':'test-codex','ANTI-01':'test-a','ANTI-02':'test-b'}
  self.server=ThreadingHTTPServer(('127.0.0.1',0),handler_factory(self.db,{k:hash_token(v) for k,v in self.tokens.items()}))
  self.addCleanup(self.server.server_close)
  self.thread=Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.addCleanup(self.server.shutdown)
  self.base='http://127.0.0.1:'+str(self.server.server_port)
  self.opener=build_opener(HTTPCookieProcessor(CookieJar()))
  self.csrf=None
 def req(self,path,body=None,headers=None):
  hs=headers or {}
  if body is not None:
   hs['Origin']=self.base;hs['Content-Type']='application/json'
   if self.csrf:hs['X-KTOOL-CSRF']=self.csrf
  try:
   with self.opener.open(Request(self.base+path,None if body is None else json.dumps(body).encode(),headers=hs),timeout=5) as r:return r.status,json.load(r)
  except HTTPError as e:return e.code,json.load(e)
 def login(self):
  self.assertEqual(self.req('/ui/api/login',{'token':self.tokens['CODEX']})[0],200)
  self.csrf=self.req('/ui/api/snapshot')[1]['csrf']
 def test_recovery_ui_requires_login(self):
  self.assertEqual(self.req('/ui/api/snapshot')[0],401)
  self.assertEqual(self.req('/ui/api/emergency-stop',{'reason':'Unauthorized stop'})[0],401)
 def test_emergency_ui_role_csrf_and_readiness(self):
  self.login()
  self.assertEqual(self.req('/ui/api/create',{'tid':'A','title':'X','scope':'arch','contract':'task','base_sha':'a'*40})[0],200)
  self.assertEqual(self.req('/ui/api/assign',{'tid':'A','owner':'ANTI-01'})[0],200)
  code,r=self.req('/ui/api/emergency-stop',{'reason':'Stop due to unsafe writes'})
  self.assertEqual(code,200)
  self.assertEqual(r['result']['mode'],'EMERGENCY_STOP')
  self.assertEqual(self.req('/ui/api/snapshot')[1]['result']['control']['mode'],'EMERGENCY_STOP')
  self.assertEqual(self.req('/ui/api/create',{'tid':'B','title':'B','scope':'mep','contract':'task','base_sha':'a'*40})[0],423)
  self.assertEqual(self.req('/ui/api/resume-control',{'workers_stopped':False,'backup_verified':True,'operator_approval':'I_APPROVE_RECOVERY'})[0],409)
  self.assertEqual(self.req('/ui/api/resume-control',{'workers_stopped':True,'backup_verified':True,'operator_approval':'I_APPROVE_RECOVERY'})[0],200)
  self.assertEqual(self.req('/ui/api/snapshot')[1]['result']['control']['mode'],'NORMAL')
  self.assertEqual(self.req('/ui/api/resume-task',{'tid':'A','owner':'ANTI-01','worker_stopped':True,'checkpoint_verified':True})[0],200)
 def test_worker_cannot_admin_over_mcp(self):
  for op in ('emergency_stop','resume_control','stale_sweep','qa_evidence'):
   args={'reason':'stop due to failure','workers_stopped':True,'backup_verified':True,'operator_approval':'I_APPROVE_RECOVERY','tid':'A'}
   c,_=self.req('/rpc',{'op':op,'args':args},{'Authorization':'Bearer '+self.tokens['ANTI-01']})
   self.assertEqual(c,403)

if __name__=='__main__':unittest.main()
