"""Controller-owned process handles and additive recovery drills.

Process registry is deliberately in-memory: after controller loss, no persisted PID
or worker boolean can reconstitute ownership. Recovery then fails closed.
"""
from contextlib import closing
from datetime import datetime,timezone
import ctypes
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import time
from trust_vault import digest,file_digest

def stamp(): return datetime.now(timezone.utc).isoformat()

def creation_identity(process):
    if os.name=='nt':
        from ctypes import wintypes
        created=wintypes.FILETIME(); exited=wintypes.FILETIME(); kernel=wintypes.FILETIME(); user=wintypes.FILETIME()
        fn=ctypes.windll.kernel32.GetProcessTimes
        fn.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.FILETIME),ctypes.POINTER(wintypes.FILETIME),ctypes.POINTER(wintypes.FILETIME),ctypes.POINTER(wintypes.FILETIME)]
        fn.restype=wintypes.BOOL
        if not fn(wintypes.HANDLE(int(process._handle)),ctypes.byref(created),ctypes.byref(exited),ctypes.byref(kernel),ctypes.byref(user)):
            raise OSError('PROCESS_CREATION_TIME_UNAVAILABLE')
        return str((created.dwHighDateTime<<32)|created.dwLowDateTime)
    proc=Path('/proc')/str(process.pid)/'stat'
    if proc.exists(): return proc.read_text().rsplit(')',1)[1].split()[19]
    raise OSError('PROCESS_CREATION_IDENTITY_UNAVAILABLE')

class OwnedProcessRegistry:
    def __init__(self): self._records={};self._proofs={};self.events=[]
    def launch(self,assignment,argv,cwd=None):
        if not assignment or not isinstance(argv,list) or not argv: raise ValueError('ASSIGNMENT_AND_ARGV_REQUIRED')
        process=subprocess.Popen(argv,cwd=cwd,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try: identity=creation_identity(process)
        except Exception:
            process.terminate();process.wait(timeout=10);raise
        self._proofs={key:value for key,value in self._proofs.items() if value['assignment']!=assignment}
        record=secrets.token_hex(24)
        self._records[record]={'assignment':assignment,'process':process,'pid':process.pid,'creation':identity,'launched_ns':time.time_ns()}
        event={'kind':'OWNED_PROCESS_STARTED','record_id':record,'assignment':assignment,'pid':process.pid,'creation':identity,'at':stamp()}
        self.events.append(event);return dict(event)
    def terminate(self,record_id,assignment,timeout=10):
        record=self._records.get(record_id)
        if record is None or record['assignment']!=assignment: raise ValueError('CONTROLLER_HANDLE_NOT_OWNED')
        process=record['process']
        if process.pid!=record['pid'] or creation_identity(process)!=record['creation']: raise ValueError('PROCESS_IDENTITY_CHANGED')
        if process.poll() is None:
            # Popen uses its owned Windows handle; no arbitrary PID is accepted.
            process.terminate()
        process.wait(timeout=timeout)
        proof={'kind':'OWNED_PROCESS_STOPPED','record_id':record_id,'assignment':assignment,'pid':record['pid'],
               'creation':record['creation'],'launched_ns':record['launched_ns'],'exit':process.returncode,
               'proof_id':secrets.token_hex(24),'at':stamp(),'descendants':'NOT_VERIFIED'}
        self._proofs[proof['proof_id']]=dict(proof);self.events.append(dict(proof));return proof
    def verify_stop(self,evidence,assignment):
        if not isinstance(evidence,dict): return False
        proof=self._proofs.get(evidence.get('proof_id'))
        if proof is None or proof!=evidence or proof['assignment']!=assignment: return False
        record=self._records.get(proof['record_id'])
        if any(r['assignment']==assignment and r['process'].poll() is None for r in self._records.values()): return False
        return bool(record and record['assignment']==assignment and record['pid']==proof['pid'] and
                    record['creation']==proof['creation'] and record['launched_ns']==proof['launched_ns'] and
                    record['process'].pid==record['pid'] and record['process'].poll() is not None and
                    record['process'].returncode==proof['exit'])

class RecoveryManager:
    def __init__(self): self.events=[]
    def event(self,kind,**fields):
        result={'kind':kind,'at':stamp(),**fields};self.events.append(result);return result
    def git(self,repo,*args):
        result=subprocess.run(['git','-C',str(repo),*args],capture_output=True,text=True,check=False)
        if result.returncode: raise ValueError('GIT_RECOVERY_FAILED: '+result.stderr[-1000:])
        return result.stdout.strip()
    def checkpoint_bundle(self,repo,commit,target):
        target=Path(target).resolve();repo=Path(repo).resolve(strict=True)
        if target.exists(): raise ValueError('NEW_BUNDLE_TARGET_REQUIRED')
        if len(commit)!=40 or self.git(repo,'rev-parse',commit+'^{commit}')!=commit: raise ValueError('IMMUTABLE_COMMIT_REQUIRED')
        # Require candidate reachable from an existing ref so --all actually preserves it.
        if not self.git(repo,'for-each-ref','--contains',commit,'--format=%(refname)'): raise ValueError('CHECKPOINT_UNREFERENCED')
        self.git(repo,'bundle','create',str(target),'--all')
        snapshot={'repo':str(repo),'commit_sha':commit,'tree_sha':self.git(repo,'rev-parse',commit+'^{tree}'),
                  'bundle':str(target),'sha256':file_digest(target),'timestamp':stamp()}
        self.event('CHECKPOINT_BUNDLE_CREATED',snapshot=snapshot,snapshot_digest=digest(snapshot))
        return snapshot
    def verify_bundle(self,snapshot,expected_digest):
        if digest(snapshot)!=expected_digest or file_digest(snapshot['bundle'])!=snapshot['sha256']: raise ValueError('SNAPSHOT_TAMPERED')
        self.git(snapshot['repo'],'bundle','verify',snapshot['bundle'])
        heads=self.git(snapshot['repo'],'bundle','list-heads',snapshot['bundle'])
        # Bundle commit must be present: clone into new disposable target and inspect object.
        import tempfile
        with tempfile.TemporaryDirectory(prefix='ktool-bundle-verify-') as temp:
            result=subprocess.run(['git','clone','--bare','-q',snapshot['bundle'],str(Path(temp)/'verify.git')],capture_output=True,text=True)
            if result.returncode: raise ValueError('BUNDLE_NOT_SELF_CONTAINED')
            tree=self.git(Path(temp)/'verify.git','rev-parse',snapshot['commit_sha']+'^{tree}')
            if tree!=snapshot['tree_sha']: raise ValueError('CHECKPOINT_TREE_MISMATCH')
        return self.event('CHECKPOINT_BUNDLE_VERIFIED',snapshot_digest=expected_digest,commit_sha=snapshot['commit_sha'])
    def backup_sqlite(self,source,target):
        source=Path(source).resolve(strict=True);target=Path(target).resolve()
        if source==target or target.exists(): raise ValueError('NEW_BACKUP_TARGET_REQUIRED')
        # Exclusive reservation prevents accidental overwrites, including another drill.
        with target.open('xb'): pass
        try:
            with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(target)) as dst:
                src.backup(dst)
                dst.commit()
                dst.execute('PRAGMA journal_mode=DELETE')
                if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('BACKUP_INTEGRITY_FAILED')
            snapshot={'source':str(source),'backup':str(target),'sha256':file_digest(target),'timestamp':stamp()}
            self.event('SQLITE_BACKUP_CREATED',snapshot=snapshot,snapshot_digest=digest(snapshot));return snapshot
        except Exception:
            # Preserve failed drill output for inspection; never touch live source.
            self.event('SQLITE_BACKUP_FAILED',source=str(source),target=str(target));raise
    def restore_sqlite(self,snapshot,expected_digest,target):
        if digest(snapshot)!=expected_digest or file_digest(snapshot['backup'])!=snapshot['sha256']: raise ValueError('BACKUP_TAMPERED')
        if any(Path(snapshot['backup']+suffix).exists() for suffix in ('-wal','-journal')): raise ValueError('BACKUP_SIDECAR_UNVERIFIED')
        target=Path(target).resolve()
        if target.exists() or str(target)==snapshot['source']: raise ValueError('NEW_RESTORE_TARGET_REQUIRED')
        restored=self.backup_sqlite(snapshot['backup'],target)
        return self.event('SQLITE_RESTORE_DRILL_VERIFIED',target=str(target),source_preserved=snapshot['source'],restored_sha256=restored['sha256'],trust='LOCAL_VERIFIED')
