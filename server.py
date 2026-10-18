"""K-TOOL v0.6 loopback registry, operator dashboard and recovery API."""
from __future__ import annotations
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Lock
import secrets
import time
from urllib.parse import urlsplit
from registry import Registry, identify, Denied

OPS = ('status','heartbeat','create_task','assign_task','get_task','checkpoint','submit_self_qa','submit_result','acknowledge_feedback','feedback_history','freeze','review_task','read_review','close_task','report','audit','control_status','emergency_stop','resume_control','resume_frozen_task','stale_sweep','qa_evidence')
WEB = Path(__file__).resolve().with_name('web')
SESSION_TTL = 8*3600


def handler_factory(store: Registry, hashes: dict):
    sessions = {}
    session_lock = Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = 'KTOOL-Local-Registry/0.6'

        def respond(self, code, data, extra=None):
            payload=json.dumps(data,ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('X-Frame-Options','DENY')
            for k,v in extra or []: self.send_header(k,v)
            self.send_header('Content-Length',str(len(payload)))
            self.end_headers(); self.wfile.write(payload)

        def asset(self, name, content_type):
            # Files are whitelisted, never derived from an untrusted path.
            path = WEB/name
            if not path.is_file(): return self.respond(404,{'error':'ASSET_NOT_FOUND'})
            data=path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type',content_type)
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('X-Frame-Options','DENY')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'none'; connect-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
            self.send_header('Content-Length',str(len(data)))
            self.end_headers(); self.wfile.write(data)

        def _session(self):
            c=self.headers.get('Cookie','')
            sid=None
            for part in c.split(';'):
                if part.strip().startswith('kt_session='):
                    sid=part.strip().partition('=')[2]
            if not sid: return None
            with session_lock:
                record=sessions.get(sid)
                if record and record['expires'] > time.time(): return record
                if sid in sessions: del sessions[sid]
            return None

        def _json_body(self, limit=22000):
            try: size=int(self.headers.get('Content-Length','0'))
            except ValueError: raise ValueError('invalid body length')
            if size < 1 or size > limit: raise ValueError('request too large or empty')
            data=json.loads(self.rfile.read(size))
            if not isinstance(data,dict): raise ValueError('JSON object required')
            return data

        def _same_origin(self):
            origin=self.headers.get('Origin','')
            expected='http://127.0.0.1:'+str(self.server.server_port)
            return origin==expected

        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/health':
                return self.respond(200,{'status':'UP','dashboard':'/ui',
                                         'note':'HTTP registry; MCP is stdio client_mcp.py'})
            if path in ('/','/ui','/ui/'):
                return self.asset('index.html','text/html; charset=utf-8')
            if path=='/ui/dashboard.css':return self.asset('dashboard.css','text/css; charset=utf-8')
            if path=='/ui/dashboard.js':return self.asset('dashboard.js','application/javascript; charset=utf-8')
            if path=='/ui/api/report':
                sess=self._session()
                if not sess:return self.respond(401,{'error':'LOGIN_REQUIRED'})
                from urllib.parse import parse_qs
                wave_id=parse_qs(urlsplit(self.path).query).get('wave_id',['PILOT'])[0]
                try: return self.respond(200,{'ok':True,'result':store.report('CODEX',wave_id)})
                except ValueError as exc: return self.respond(400,{'error':str(exc)})
            if path=='/ui/api/snapshot':
                sess=self._session()
                if not sess:return self.respond(401,{'error':'LOGIN_REQUIRED'})
                result=store.dashboard_snapshot('CODEX')
                return self.respond(200,{'ok':True,'result':result,'csrf':sess['csrf']})
            return self.respond(404,{'error':'NOT_FOUND'})

        def do_POST(self):
            path=urlsplit(self.path).path
            if path=='/rpc':
                role=identify(self.headers.get('Authorization',''),hashes)
                if role is None:return self.respond(401,{'error':'UNAUTHORIZED'})
                try:
                    body=self._json_body(20000)
                    op=body.get('op'); args=body.get('args',{})
                    if op not in OPS or not isinstance(args,dict):raise ValueError('unknown op')
                    if op=='status': result=store.status(role)
                    elif op=='heartbeat': result=store.heartbeat(role,args.get('event','AVAILABLE'))
                    elif op=='create_task': result=store.create_task(role,args['tid'],args['title'],args['scope'],args['contract'],args['base_sha'],args.get('wave_id','PILOT'),args.get('requires_preview',True),args.get('exclusive_resources',[]),args.get('depends_on',[]))
                    elif op=='assign_task': result=store.assign(role,args['tid'],args['owner'])
                    elif op=='get_task': result=store.get_task(role,args['tid'])
                    elif op=='checkpoint': result=store.checkpoint(role,args['tid'],args['fencing'],args['message'])
                    elif op=='submit_self_qa': result=store.submit_self_qa(role,args['tid'],args['fencing'],args['commit_sha'],args['changed_paths'],args['checks'],args['build_status'],args['test_status'],args.get('preview_status','NOT_EXECUTED'),args['evidence_ref'])
                    elif op=='acknowledge_feedback': result=store.acknowledge_feedback(role,args['tid'],args['fencing'])
                    elif op=='feedback_history': result=store.feedback_history(role,args['tid'])
                    elif op=='submit_result': result=store.submit_result(role,args['tid'],args['fencing'],args['commit_sha'],args['summary'],args['build_status'],args['test_status'],args['evidence_ref'])
                    elif op=='freeze': result=store.freeze(role,args['tid'],args['reason'])
                    elif op=='review_task': result=store.review_task(role,args['tid'],args['decision'],args['report'],args['evidence_ref'],args.get('build_verified',False),args.get('tests_verified',False),args.get('preview_verified',False),args.get('preview_evidence_ref',''),args.get('issues',[]))
                    elif op=='close_task': result=store.close_task(role,args['tid'],args['integration_sha'],args.get('source_stopped',False))
                    elif op=='report': result=store.report(role,args.get('wave_id','PILOT'))
                    elif op=='read_review': result=store.read_review(role,args['tid'])
                    elif op=='audit': result=store.audit(role)
                    elif op=='control_status': result=store.control_status(role)
                    elif op=='emergency_stop': result=store.emergency_stop(role,args['reason'])
                    elif op=='resume_control': result=store.resume_control(role,args.get('workers_stopped'),args.get('backup_verified'),args.get('operator_approval'))
                    elif op=='resume_frozen_task': result=store.resume_frozen_task(role,args['tid'],args['owner'],args.get('worker_stopped'),args.get('checkpoint_verified'))
                    elif op=='stale_sweep': result=store.stale_sweep(role,args.get('max_age_seconds',180))
                    elif op=='qa_evidence': result=store.qa_evidence(role,args['tid'])
                    return self.respond(200,{'ok':True,'result':result})
                except Denied as e:return self.respond(e.http_status,{'ok':False,'error':str(e)})
                except (KeyError,ValueError,TypeError) as e:return self.respond(400,{'ok':False,'error':str(e)})
                except Exception:
                    return self.respond(500,{'ok':False,'error':'INTERNAL_ERROR (see server logs)'})
            if not path.startswith('/ui/api/'):
                return self.respond(404,{'error':'NOT_FOUND'})
            if not self._same_origin():
                return self.respond(403,{'error':'INVALID_ORIGIN'})
            try:
                body=self._json_body()
                if path=='/ui/api/login':
                    tok=body.get('token','')
                    if not isinstance(tok,str) or identify('Bearer '+tok,hashes)!='CODEX':
                        return self.respond(401,{'error':'INVALID_CODEX_TOKEN'})
                    sid=secrets.token_urlsafe(36)
                    csrf=secrets.token_urlsafe(24)
                    with session_lock:
                        sessions[sid]={'expires':time.time()+SESSION_TTL,'csrf':csrf}
                    return self.respond(200,{'ok':True,'message':'SIGNED_IN'},
                                        [('Set-Cookie',f'kt_session={sid}; HttpOnly; SameSite=Strict; Path=/ui; Max-Age={SESSION_TTL}')])
                sess=self._session()
                if not sess:return self.respond(401,{'error':'LOGIN_REQUIRED'})
                if self.headers.get('X-KTOOL-CSRF','')!=sess['csrf']:
                    return self.respond(403,{'error':'CSRF_TOKEN_MISMATCH'})
                if path=='/ui/api/create':
                    result=store.create_task('CODEX',body['tid'],body['title'],body['scope'],body['contract'],body['base_sha'],body.get('wave_id','PILOT'),body.get('requires_preview',True),body.get('exclusive_resources',[]),body.get('depends_on',[]))
                elif path=='/ui/api/assign':
                    result=store.assign('CODEX',body['tid'],body['owner'])
                elif path=='/ui/api/review':
                    result=store.review_task('CODEX',body['tid'],body['decision'],body['report'],body['evidence_ref'],body.get('build_verified',False),body.get('tests_verified',False),body.get('preview_verified',False),body.get('preview_evidence_ref',''),body.get('issues',[]))
                elif path=='/ui/api/close':
                    result=store.close_task('CODEX',body['tid'],body['integration_sha'],body.get('source_stopped',False))
                elif path=='/ui/api/freeze':
                    result=store.freeze('CODEX',body['tid'],body['reason'])
                elif path=='/ui/api/emergency-stop':
                    result=store.emergency_stop('CODEX',body['reason'])
                elif path=='/ui/api/resume-control':
                    result=store.resume_control('CODEX',body.get('workers_stopped'),body.get('backup_verified'),body.get('operator_approval'))
                elif path=='/ui/api/stale-sweep':
                    result=store.stale_sweep('CODEX',body.get('max_age_seconds',180))
                elif path=='/ui/api/resume-task':
                    result=store.resume_frozen_task('CODEX',body['tid'],body['owner'],body.get('worker_stopped'),body.get('checkpoint_verified'))
                elif path=='/ui/api/logout':
                    c=self.headers.get('Cookie','')
                    for part in c.split(';'):
                        if part.strip().startswith('kt_session='):
                            sid=part.strip().partition('=')[2]
                            with session_lock:sessions.pop(sid,None)
                    return self.respond(200,{'ok':True},[('Set-Cookie','kt_session=; HttpOnly; SameSite=Strict; Path=/ui; Max-Age=0')])
                else:return self.respond(404,{'error':'NOT_FOUND'})
                return self.respond(200,{'ok':True,'result':result})
            except Denied as e:return self.respond(e.http_status,{'ok':False,'error':str(e)})
            except (KeyError,ValueError,TypeError,json.JSONDecodeError) as e:
                return self.respond(400,{'ok':False,'error':str(e)})
            except Exception:
                return self.respond(500,{'ok':False,'error':'INTERNAL_ERROR'})

        def log_message(self, fmt, *args):
            # Never write Authorization header/body to console.
            if args: print('[ktool-http] '+fmt%args,flush=True)
    return Handler


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--db',default=str(Path(__file__).with_name('private')/'registry.db'))
    p.add_argument('--roles',default=str(Path(__file__).with_name('private')/'roles.json'))
    p.add_argument('--port',type=int,default=8876)
    args=p.parse_args()
    roles=json.loads(Path(args.roles).read_text(encoding='utf-8'))
    if set(roles)!= {'CODEX','ANTI-01','ANTI-02'}:raise ValueError('Expected CODEX / ANTI-01 / ANTI-02 roles')
    if not 1<=args.port<=65535:raise ValueError('invalid port')
    # Back up the pre-migration DB BEFORE Registry.init changes schema. Fail closed if backup fails.
    db_path=Path(args.db)
    if db_path.is_file():
        from backup_registry import backup
        print('Startup SQLite backup:',backup(db_path,db_path.parent/'backups'),flush=True)
    store=Registry(args.db)
    startup=store.reconcile_startup()
    print('Recovery reconciliation:',startup,flush=True)
    httpd=ThreadingHTTPServer(('127.0.0.1',args.port),handler_factory(store,roles))
    print(f'K-TOOL Task Registry & Dashboard: http://127.0.0.1:{args.port}/ui',flush=True)
    print('MCP adapter is a separate stdio process. CTRL+C stops this server.',flush=True)
    try:httpd.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:pass
    finally:httpd.server_close()

if __name__=='__main__':main()
