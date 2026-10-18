"""Real process interruption drill using disposable Registry and test-only credentials.
Not an Antigravity session or Google quota monitor. Never touches installed private/.
"""
import hashlib
from contextlib import closing
import json
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from registry import hash_token
from backup_registry import backup


def run():
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append({'name': name, 'status': 'PASS'})
    with tempfile.TemporaryDirectory(prefix='ktool-drill-') as folder:
        root = Path(folder)
        tokens = {r: secrets.token_urlsafe(40) for r in ('CODEX', 'ANTI-01', 'ANTI-02')}
        roles = root/'roles.json'
        roles.write_text(json.dumps({r:hash_token(t) for r,t in tokens.items()}))
        db = root/'registry.db'
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        def rpc(role, op, **args):
            req = Request(base+'/rpc', data=json.dumps({'op':op,'args':args}).encode(),
                          headers={'Authorization':'Bearer '+tokens[role],'Content-Type':'application/json'})
            try:
                with urlopen(req,timeout=5) as response:
                    return response.status,json.load(response)
            except HTTPError as err:
                return err.code,json.load(err)
        def start():
            process = subprocess.Popen([sys.executable,str(ROOT/'server.py'),'--db',str(db),
                                        '--roles',str(roles),'--port',str(port)],
                                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError('Sandbox coordinator exited early')
                try:
                    with urlopen(base+'/health',timeout=.5) as response:
                        if response.status == 200:
                            return process
                except (OSError, URLError):
                    time.sleep(.1)
            process.kill(); process.wait()
            raise RuntimeError('Sandbox startup timeout')
        process = start()
        try:
            # A real isolated Git baseline, independent of machine-specific pilot paths.
            repo=root/'git-baseline'
            repo.mkdir()
            subprocess.run(['git','init','-q',str(repo)],check=True)
            subprocess.run(['git','-C',str(repo),'-c','user.name=Recovery Drill',
                            '-c','user.email=recovery@localhost','commit','--allow-empty','-qm','drill baseline'],check=True)
            sha = subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
            for tid,scope,owner in [('DRILL-A','architectural/envelope','ANTI-01'),('DRILL-B','documentation/schedules','ANTI-02')]:
                check('create '+tid,rpc('CODEX','create_task',tid=tid,title=tid,scope=scope,
                      contract='Disposable recovery drill only',base_sha=sha,requires_preview=False)[0]==200)
                code,result=rpc('CODEX','assign_task',tid=tid,owner=owner)
                check('assign '+tid,code==200)
                if tid=='DRILL-A': old=result['result']['fencing']
                else: other=result['result']['fencing']
            check('checkpoint persisted',rpc('ANTI-01','checkpoint',tid='DRILL-A',fencing=old,message='durable checkpoint')[0]==200)
            check('worker cannot create',rpc('ANTI-01','create_task',tid='DENIED',title='Denied',scope='other',contract='deny',base_sha=sha)[0]==403)
            check('worker cannot impersonate',rpc('ANTI-02','checkpoint',tid='DRILL-A',fencing=old,message='deny')[0]==403)
            rpc('ANTI-01','heartbeat',event='QUOTA_EXHAUSTED')
            check('simulated quota retains lock',rpc('CODEX','get_task',tid='DRILL-A')[1]['result']['state']=='FROZEN')
            check('other worker unaffected',rpc('ANTI-02','checkpoint',tid='DRILL-B',fencing=other,message='still working')[0]==200)
            # Terminate this exact disposable child, never an unrelated Windows process.
            process.kill(); process.wait(timeout=10)
            check('actual coordinator process terminated',process.returncode is not None)
            process=start()
            check('restart fails closed',rpc('CODEX','control_status')[1]['result']['mode']=='RECOVERY_REQUIRED')
            check('checkpoint survives crash',rpc('CODEX','get_task',tid='DRILL-A')[1]['result']['checkpoint']=='durable checkpoint')
            check('restart freezes active worker',rpc('CODEX','get_task',tid='DRILL-B')[1]['result']['state']=='FROZEN')
            snap=backup(db,root/'verified-backups')
            snapshot=root/'verified-backups'/snap['snapshot']
            check('backup integrity and hash',snap['sqlite_integrity_check']=='ok' and hashlib.sha256(snapshot.read_bytes()).hexdigest()==snap['sha256'])
            with closing(sqlite3.connect(snapshot)) as conn:
                check('backup retains both tasks',conn.execute('select count(*) from tasks').fetchone()[0]==2)
            check('unconfirmed recovery denied',rpc('CODEX','resume_control',workers_stopped=True,backup_verified=False,operator_approval='I_APPROVE_RECOVERY')[0]==409)
            check('sandbox recovery approved',rpc('CODEX','resume_control',workers_stopped=True,backup_verified=True,operator_approval='I_APPROVE_RECOVERY')[0]==200)
            check('cross-account handover denied',rpc('CODEX','resume_frozen_task',tid='DRILL-A',owner='ANTI-02',worker_stopped=True,checkpoint_verified=True)[0]==409)
            code,result=rpc('CODEX','resume_frozen_task',tid='DRILL-A',owner='ANTI-01',worker_stopped=True,checkpoint_verified=True)
            new=result['result']['new_fencing']
            check('new fencing after recovery',code==200 and new!=old)
            check('old fencing denied',rpc('ANTI-01','checkpoint',tid='DRILL-A',fencing=old,message='stale')[0]==403)
            check('new fencing works',rpc('ANTI-01','checkpoint',tid='DRILL-A',fencing=new,message='safe resume')[0]==200)
            check('emergency stop enforced',rpc('CODEX','emergency_stop',reason='Disposable emergency stop test')[1]['result']['mode']=='EMERGENCY_STOP')
            check('new work denied on emergency',rpc('CODEX','create_task',tid='STOPPED',title='Stopped',scope='other',contract='deny',base_sha=sha)[0]==423)
            check('writes denied on emergency',rpc('ANTI-01','checkpoint',tid='DRILL-A',fencing=new,message='deny')[0]!=200)
        finally:
            if process.poll() is None:
                process.kill(); process.wait(timeout=10)
    return {'status':'PASS','checks':checks,'scope':'disposable process + HTTP + SQLite drill',
            'real_antigravity':'NOT_EXECUTED','quota':'SIMULATED_REGISTRY_EVENT','power_loss':'NOT_EXECUTED'}

if __name__=='__main__':
    print(json.dumps(run(),indent=2))
