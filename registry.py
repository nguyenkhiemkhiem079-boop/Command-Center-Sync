"""K-TOOL Command Center v0.6: fail-closed Recovery, QA Evidence and Worksharing.

Ownership enforcement remains REGISTRY_ONLY until NTFS + CI gates have been verified.

CODEX creates/assigns/reviews; ANTI-01 and ANTI-02 have identical worker capabilities.
SQLite serializes ownership changes; overlapping paths cannot acquire concurrent locks.
"""
from __future__ import annotations
from contextlib import contextmanager
import datetime as dt
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
import os
import secrets

ROLES = ('CODEX', 'ANTI-01', 'ANTI-02')
WORKERS = ('ANTI-01', 'ANTI-02')
SHA40 = re.compile(r'^[a-fA-F0-9]{40}$')


def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def clean_scope(scope: str) -> str:
    if not isinstance(scope, str) or len(scope) > 240:
        raise ValueError('invalid scope')
    scope = scope.replace('\\', '/')
    parts = scope.split('/')
    if (not scope or any(c in scope for c in ':*?"<>|') or
            any(ord(c) < 32 for c in scope) or
            any(p in ('', '.', '..') or p.endswith((' ', '.')) or
                re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p)
                for p in parts)):
        raise ValueError('invalid scope')
    return scope.casefold()


def collide(a: str, b: str) -> bool:
    a, b = clean_scope(a), clean_scope(b)
    return a == b or a.startswith(b + '/') or b.startswith(a + '/')


class Denied(Exception):
    def __init__(self, message: str, http_status: int = 409):
        self.http_status = http_status
        super().__init__(message)


class Registry:
    def __init__(self, dbfile):
        self.dbfile = str(dbfile)
        Path(self.dbfile).parent.mkdir(parents=True, exist_ok=True)
        self.init()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.dbfile, timeout=15, isolation_level=None)
        try:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA busy_timeout=15000')
            db.execute('PRAGMA foreign_keys=ON')
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.execute('COMMIT')
            except Exception:
                db.execute('ROLLBACK')
                raise

    def init(self):
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
            CREATE TABLE IF NOT EXISTS tasks (
              id TEXT PRIMARY KEY, title TEXT NOT NULL, scope TEXT NOT NULL,
              contract TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'QUEUED',
              owner TEXT, base_sha TEXT NOT NULL,
              fencing INTEGER NOT NULL DEFAULT 0, checkpoint TEXT, checkpoint_at TEXT,
              qa_result TEXT, qa_actor TEXT, updated TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS locks (
              scope TEXT PRIMARY KEY, task_id TEXT NOT NULL UNIQUE,
              owner TEXT NOT NULL, fencing INTEGER NOT NULL,
              state TEXT NOT NULL CHECK(state IN ('ACTIVE','FROZEN')),
              FOREIGN KEY(task_id) REFERENCES tasks(id)
            );
            CREATE TABLE IF NOT EXISTS audit (
              id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
              actor TEXT NOT NULL, action TEXT NOT NULL, task_id TEXT,
              detail TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
            INSERT OR IGNORE INTO meta(key,value) VALUES('epoch',0);
            CREATE TABLE IF NOT EXISTS agents (
              id TEXT PRIMARY KEY, last_seen TEXT, last_event TEXT NOT NULL DEFAULT 'NOT_VERIFIED'
            );
            INSERT OR IGNORE INTO agents(id) VALUES('ANTI-01');
            INSERT OR IGNORE INTO agents(id) VALUES('ANTI-02');
            ''')
            existing = {r['name'] for r in db.execute('PRAGMA table_info(tasks)')}
            # Idempotent migration for existing v0.3 database, preserving all tasks and credentials.
            for name, definition in [('wave_id', "TEXT NOT NULL DEFAULT 'PILOT'"),
                                     ('result_json','TEXT'), ('review_at','TEXT'),
                                     ('integration_sha','TEXT'),
                                     ('self_qa_json','TEXT'),('qa_round','INTEGER NOT NULL DEFAULT 1'),
                                     ('rework_count','INTEGER NOT NULL DEFAULT 0'),
                                     ('requires_preview','INTEGER NOT NULL DEFAULT 0')]:
                if name not in existing:
                    db.execute(f'ALTER TABLE tasks ADD COLUMN {name} {definition}')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS control (
                  key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                INSERT OR IGNORE INTO control(key,value) VALUES('mode','NORMAL');
                CREATE TABLE IF NOT EXISTS qa_evidence (
                  id TEXT PRIMARY KEY, at TEXT NOT NULL,
                  task_id TEXT NOT NULL, qa_round INTEGER NOT NULL,
                  commit_sha TEXT NOT NULL, baseline_sha TEXT NOT NULL,
                  scope TEXT NOT NULL, result TEXT NOT NULL,
                  build_exit INTEGER, tests_exit INTEGER,
                  git_scope_pass INTEGER NOT NULL, clean_tree INTEGER NOT NULL,
                  changed_paths TEXT NOT NULL, evidence_json TEXT NOT NULL,
                  FOREIGN KEY(task_id) REFERENCES tasks(id)
                );
                CREATE TABLE IF NOT EXISTS recovery_events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
                  kind TEXT NOT NULL, detail TEXT NOT NULL
                );
            ''')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS resource_locks (
                  resource TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                  owner TEXT NOT NULL, fencing INTEGER NOT NULL,
                  FOREIGN KEY(task_id) REFERENCES tasks(id)
                );
            ''')
            for name,definition in [('exclusive_resources',"TEXT NOT NULL DEFAULT '[]'"),('depends_on',"TEXT NOT NULL DEFAULT '[]'")]:
                if name not in existing:db.execute(f'ALTER TABLE tasks ADD COLUMN {name} {definition}')
            db.execute('''CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
                task_id TEXT NOT NULL, cycle INTEGER NOT NULL, reviewer TEXT NOT NULL,
                decision TEXT NOT NULL, report TEXT NOT NULL, issues_json TEXT NOT NULL,
                evidence_ref TEXT NOT NULL, FOREIGN KEY(task_id) REFERENCES tasks(id)
            )''')

    def _mode(self, db):
        return db.execute("SELECT value FROM control WHERE key='mode'").fetchone()['value']

    def _allow_activity(self, db):
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cc_meta'").fetchone():
            shared=db.execute("SELECT value FROM cc_meta WHERE key='mode'").fetchone()
            if shared and shared['value'] in ('EMERGENCY_STOP','RECOVERY_REQUIRED'):
                raise Denied('CONTROL_PLANE_NOT_NORMAL: '+shared['value'],423)
        if self._mode(db) != 'NORMAL':
            raise Denied('CONTROL_PLANE_NOT_NORMAL: ' + self._mode(db), 423)

    def control_status(self, actor):
        self._require(actor, ('CODEX',))
        with self.connect() as db:
            mode=self._mode(db)
            freeze=db.execute("SELECT COUNT(*) c FROM locks WHERE state='FROZEN'").fetchone()['c']
            return {'mode':mode,'frozen_locks':freeze,
                    'physical_windows_processes':'NOT_VERIFIED',
                    'advisory_registry_only':True,
                    'automatic_account_rotation':'NOT_SUPPORTED'}

    def emergency_stop(self, actor, reason):
        self._require(actor, ('CODEX',))
        if not isinstance(reason,str) or len(reason.strip())<8 or len(reason)>800:
            raise ValueError('meaningful reason required')
        with self.transaction() as db:
            db.execute("UPDATE control SET value='EMERGENCY_STOP' WHERE key='mode'")
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cc_meta'").fetchone():
                db.execute("UPDATE cc_meta SET value='EMERGENCY_STOP' WHERE key='mode'")
                db.execute("UPDATE cc_assignments SET status='FROZEN' WHERE id IN (SELECT assignment FROM cc_locks)")
                db.execute("UPDATE cc_locks SET state='FROZEN'")
            db.execute("UPDATE locks SET state='FROZEN' WHERE state='ACTIVE'")
            db.execute("UPDATE tasks SET state='FROZEN',updated=? WHERE id IN (SELECT task_id FROM locks)", (utcnow(),))
            db.execute("INSERT INTO recovery_events(at,kind,detail) VALUES(?,?,?)",(utcnow(),'EMERGENCY_STOP',reason[:800]))
            self._audit(db,actor,'EMERGENCY_STOP','',reason)
        return {'mode':'EMERGENCY_STOP','new_work_blocked':True,'locks_frozen':True,
                'processes_killed':False,'note':'Kill or isolate OS processes separately; registry cannot kill Antigravity.'}

    def reconcile_startup(self):
        # Called once by server on launch; fail closed after crash or restart.
        with self.transaction() as db:
            count=db.execute("SELECT COUNT(*) c FROM locks WHERE state='ACTIVE'").fetchone()['c']
            if count:
                db.execute("UPDATE locks SET state='FROZEN' WHERE state='ACTIVE'")
                db.execute("UPDATE tasks SET state='FROZEN',updated=? WHERE id IN (SELECT task_id FROM locks)",(utcnow(),))
                db.execute("UPDATE control SET value='RECOVERY_REQUIRED' WHERE key='mode'")
                db.execute("INSERT INTO recovery_events(at,kind,detail) VALUES(?,?,?)",(utcnow(),'STARTUP_RECONCILE',str(count)+' live locks frozen'))
                self._audit(db,'SYSTEM','STARTUP_RECONCILE','',str(count)+' locks frozen')
            return {'frozen_active_locks':count,'mode':self._mode(db)}

    def stale_sweep(self, actor, max_age_seconds=180):
        self._require(actor,('CODEX',))
        if type(max_age_seconds) is not int or not 60<=max_age_seconds<=86400:
            raise ValueError('max_age_seconds 60..86400')
        now=dt.datetime.now(dt.timezone.utc)
        frozen=[]
        with self.transaction() as db:
            for agent in db.execute('SELECT * FROM agents'):
                if not agent['last_seen']:
                    continue  # Unknown is not proof of alive or dead.
                try: age=(now-dt.datetime.fromisoformat(agent['last_seen'])).total_seconds()
                except ValueError: age=max_age_seconds+1
                if age <= max_age_seconds:continue
                for l in db.execute("SELECT task_id FROM locks WHERE owner=? AND state='ACTIVE'",(agent['id'],)).fetchall():
                    db.execute("UPDATE locks SET state='FROZEN' WHERE task_id=?",(l['task_id'],))
                    db.execute("UPDATE tasks SET state='FROZEN',updated=? WHERE id=?",(utcnow(),l['task_id']))
                    self._audit(db,actor,'STALE_HEARTBEAT_FREEZE',l['task_id'],agent['id']+' age='+str(int(age)))
                    frozen.append(l['task_id'])
        return {'frozen_tasks':frozen,'released_locks':0,'worker_stopped':'NOT_VERIFIED'}

    def resume_control(self, actor, workers_stopped, backup_verified, operator_approval):
        self._require(actor,('CODEX',))
        # Deprecated legacy route has no protected process/backup verifier bridge.
        raise Denied('VERIFIED_PROCESS_PROOF_REQUIRED: legacy boolean recovery is disabled',409)

    def resume_frozen_task(self, actor, tid, owner, worker_stopped, checkpoint_verified):
        self._require(actor,('CODEX',))
        raise Denied('VERIFIED_PROCESS_PROOF_REQUIRED: use controller-owned process recovery',409)

    def register_local_qa(self, tid, qa_round, commit_sha, git_scope_pass,
                          clean_tree, changed_paths, build_exit, tests_exit, payload):
        # Trusted local runner only; not exposed via RPC/MCP. OS ACL and CI also required.
        if not isinstance(commit_sha,str) or not SHA40.fullmatch(commit_sha):raise ValueError('invalid sha')
        if not isinstance(payload,dict):raise ValueError('invalid payload')
        with self.transaction() as db:
            t=self._task(db,tid)
            if int(qa_round)!=t['qa_round'] or t['state'] not in ('SUBMITTED','CODE_REVIEWED'):
                raise Denied('QA_TASK_STATE_CHANGED')
            res=json.loads(t['result_json'] or '{}')
            if res.get('commit_sha')!=commit_sha.lower():raise Denied('QA_SHA_CHANGED')
            if not (isinstance(changed_paths,list) and all(isinstance(x,str) for x in changed_paths)):
                raise ValueError('invalid changed_paths')
            claimed=json.loads(t['self_qa_json'] or '{}').get('changed_paths',[])
            paths_ok=sorted([clean_scope(p) for p in changed_paths])==sorted(claimed)
            result='PASS' if git_scope_pass and clean_tree and build_exit==0 and tests_exit==0 and bool(changed_paths) and paths_ok and payload.get('git_verified') and payload.get('path_check') else 'FAIL'
            evidence_id=secrets.token_hex(16)
            db.execute("""INSERT INTO qa_evidence(id,at,task_id,qa_round,commit_sha,baseline_sha,scope,result,build_exit,tests_exit,git_scope_pass,clean_tree,changed_paths,evidence_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(evidence_id,utcnow(),tid,qa_round,commit_sha.lower(),t['base_sha'],t['scope'],result,
                      build_exit,tests_exit,int(bool(git_scope_pass)),int(bool(clean_tree)),json.dumps(changed_paths),json.dumps(payload)))
            self._audit(db,'LOCAL_QA_RUNNER','QA_EVIDENCE',tid,result+' '+evidence_id[:12])
        return {'evidence_id':evidence_id,'result':result,'commit_sha':commit_sha.lower()}

    def qa_evidence(self, actor, tid):
        self._require(actor,('CODEX',))
        with self.connect() as db:
            self._task(db,tid)
            return [dict(x) for x in db.execute('SELECT id,at,qa_round,commit_sha,result,build_exit,tests_exit,git_scope_pass,clean_tree,changed_paths FROM qa_evidence WHERE task_id=? ORDER BY at DESC',(tid,))]

    def _audit(self, db, actor, action, task='', detail=''):
        db.execute('INSERT INTO audit(at,actor,action,task_id,detail) VALUES(?,?,?,?,?)',
                   (utcnow(), actor, action, task, str(detail)[:800]))

    def _task(self, db, tid):
        row=db.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
        if not row: raise Denied('TASK_NOT_FOUND',404)
        return row

    def _require(self, actor, expected):
        if actor not in expected: raise Denied('ROLE_DENIED',403)

    def heartbeat(self, actor, event='AVAILABLE'):
        self._require(actor, WORKERS)
        if event not in ('AVAILABLE','WORKING','CHECKPOINTING','PAUSED','QUOTA_EXHAUSTED','DISCONNECTED'):
            raise ValueError('invalid event')
        with self.transaction() as db:
            db.execute('UPDATE agents SET last_seen=?,last_event=? WHERE id=?',(utcnow(), event, actor))
            if event in ('QUOTA_EXHAUSTED','DISCONNECTED'):
                for l in db.execute("SELECT task_id FROM locks WHERE owner=? AND state='ACTIVE'",(actor,)).fetchall():
                    db.execute("UPDATE locks SET state='FROZEN' WHERE task_id=?",(l['task_id'],))
                    db.execute("UPDATE tasks SET state='FROZEN',updated=? WHERE id=?",(utcnow(),l['task_id']))
                    self._audit(db,actor,'WORKER_INTERRUPTED_FREEZE',l['task_id'],event)
        return {'agent':actor,'mcp_contact':'RECORDED','antigravity_teamwork':'NOT_VERIFIED'}

    def status(self, actor):
        with self.connect() as db:
            rows=[dict(r) for r in db.execute('SELECT id,title,scope,state,owner,wave_id,updated FROM tasks ORDER BY updated DESC')]
            if actor!='CODEX':rows=[r for r in rows if r['owner']==actor]
            return {'actor':actor,'tasks':rows,'control_mode':self._control_mode_read(),'integration':self._integration(),'qa_process':'SELF_QA_THEN_CODEX_REVIEW'}

    def _control_mode_read(self):
        with self.connect() as db:return self._mode(db)

    def _integration(self):
        return {'antigravity_teamwork':'NOT_VERIFIED','codex_agent_runtime':'NOT_VERIFIED',
                'isolation_level':'LOGICAL_ONLY','role_separation':'ROLE_SEPARATION_LOGICAL_ONLY',
                'windows_acl':'SHARED_WINDOWS_PRINCIPAL','github_ci':'NOT_CONNECTED','revit_host':'NOT_EXECUTED',
                'lock_enforcement':'REGISTRY_ONLY','local_qa_runner':'AVAILABLE_NOT_ALWAYS_EXECUTED', 'disaster_recovery':'FAIL_CLOSED_ON_RESTART'}

    def dashboard_snapshot(self, actor):
        self._require(actor,('CODEX',))
        with self.connect() as db:
            tasks=[dict(r) for r in db.execute('SELECT * FROM tasks ORDER BY updated DESC,id ASC')]
            locks=[dict(r) for r in db.execute('SELECT * FROM locks ORDER BY scope')]
            resources=[dict(r) for r in db.execute('SELECT * FROM resource_locks ORDER BY resource')]
            audit=[dict(r) for r in db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 100')]
            agents=[]
            for a in db.execute('SELECT * FROM agents ORDER BY id'):
                recent=False
                if a['last_seen']:
                    try:
                        recent=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(a['last_seen'])).total_seconds()<90
                    except ValueError: pass
                agents.append({'id':a['id'],'role':'Development', 'last_seen':a['last_seen'],
                               'mcp_recent':recent,'mcp_event':a['last_event'],
                               'teamwork':'NOT_VERIFIED'})
        return {'tasks':tasks,'locks':locks,'audit':audit,'agents':agents,
                'control':self.control_status('CODEX'),'resource_locks':resources,
                'integration':self._integration(),'provenance':'LOCAL_REGISTRY_ONLY',
                'work_mode':'DUAL_TEAMWORK_SELF_QA_CODEX_REVIEW_LOOP'}

    def create_task(self, actor, tid, title, scope, contract, base_sha, wave_id='PILOT', requires_preview=True, exclusive_resources=None, depends_on=None):
        self._require(actor,('CODEX',))
        tid, title, contract, wave_id = str(tid).strip(), str(title).strip(), str(contract).strip(), str(wave_id).strip()
        if not tid or len(tid)>64 or not title or len(title)>180 or not contract or len(contract)>12000:
            raise ValueError('invalid task id/title/contract')
        if not wave_id or len(wave_id)>64 or not re.fullmatch(r'[A-Za-z0-9_-]+', wave_id):
            raise ValueError('invalid wave_id')
        if not isinstance(base_sha,str) or not SHA40.fullmatch(base_sha):
            raise ValueError('base_sha must be real 40-hex Git SHA')
        scope=clean_scope(scope)
        if type(requires_preview) is not bool: raise ValueError('requires_preview must be bool')
        exclusive_resources=[] if exclusive_resources is None else exclusive_resources
        depends_on=[] if depends_on is None else depends_on
        if not isinstance(exclusive_resources,list) or len(exclusive_resources)>24 or any(
            not isinstance(x,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',x) for x in exclusive_resources):
            raise ValueError('invalid exclusive_resources')
        if not isinstance(depends_on,list) or len(depends_on)>24 or any(
            not isinstance(x,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',x) for x in depends_on):
            raise ValueError('invalid depends_on')
        exclusive_resources=sorted(set(x.casefold() for x in exclusive_resources))
        depends_on=sorted(set(depends_on))
        if tid in depends_on:raise ValueError('self-dependency')
        with self.transaction() as db:
            self._allow_activity(db)
            for dep in depends_on:
                if not db.execute('SELECT 1 FROM tasks WHERE id=?',(dep,)).fetchone():
                    raise Denied('UNKNOWN_DEPENDENCY: '+dep,409)
            db.execute('INSERT INTO tasks(id,title,scope,contract,base_sha,wave_id,requires_preview,updated,exclusive_resources,depends_on) VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (tid,title,scope,contract,base_sha.lower(),wave_id,int(requires_preview),utcnow(),json.dumps(exclusive_resources),json.dumps(depends_on)))
            self._audit(db,actor,'CREATE',tid,f'{wave_id} {scope}')
        return {'id':tid,'state':'QUEUED','scope':scope,'wave_id':wave_id}

    def assign(self, actor, tid, owner):
        self._require(actor,('CODEX',))
        if owner not in WORKERS: raise ValueError('unknown worker')
        with self.transaction() as db:
            self._allow_activity(db)
            t=self._task(db,tid)
            if t['state']!='QUEUED': raise Denied('TASK_NOT_QUEUED')
            for dep in json.loads(t['depends_on']):
                state=db.execute('SELECT state FROM tasks WHERE id=?',(dep,)).fetchone()
                if not state or state['state']!='CLOSED':raise Denied('DEPENDENCY_NOT_INTEGRATED: '+dep)
            for resource in json.loads(t['exclusive_resources']):
                existing=db.execute('SELECT task_id FROM resource_locks WHERE resource=?',(resource,)).fetchone()
                if existing:raise Denied('CANT_EDIT_SHARED_RESOURCE: '+resource+' owned by '+existing['task_id'])
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cc_resource_locks'").fetchone():
                for resource in json.loads(t['exclusive_resources']):
                    if db.execute('SELECT 1 FROM cc_resource_locks WHERE resource=?',(resource,)).fetchone():
                        raise Denied('CANT_EDIT_SHARED_RESOURCE: controller owns '+resource)
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cc_locks'").fetchone():
                for lock in db.execute('SELECT scope FROM cc_locks'):
                    if collide(t['scope'],lock['scope']): raise Denied('CANT_EDIT: controller scope ownership')
            # Pilot cap: each anti owns at most one unresolved task.
            if db.execute("SELECT 1 FROM tasks WHERE owner=? AND state IN ('RUNNING','SELF_QA_READY','FROZEN','SUBMITTED','REWORK_REQUIRED','CODE_REVIEWED')",(owner,)).fetchone():
                raise Denied('AGENT_BUSY')
            for old in db.execute("SELECT * FROM locks WHERE state IN ('ACTIVE','FROZEN')"):
                if collide(t['scope'],old['scope']):
                    raise Denied('CANT_EDIT: scope owned by '+old['owner']+' task '+old['task_id'])
            db.execute("UPDATE meta SET value=value+1 WHERE key='epoch'")
            epoch=db.execute("SELECT value FROM meta WHERE key='epoch'").fetchone()['value']
            db.execute('INSERT INTO locks(scope,task_id,owner,fencing,state) VALUES(?,?,?,?,?)',
                       (t['scope'],tid,owner,epoch,'ACTIVE'))
            for resource in json.loads(t['exclusive_resources']):
                db.execute('INSERT INTO resource_locks(resource,task_id,owner,fencing) VALUES(?,?,?,?)',(resource,tid,owner,epoch))
            db.execute("UPDATE tasks SET state='RUNNING',owner=?,fencing=?,updated=? WHERE id=?",(owner,epoch,utcnow(),tid))
            self._audit(db,actor,'ASSIGN',tid,f'{owner} fencing={epoch}')
        return {'task_id':tid,'owner':owner,'fencing':epoch,'scope':t['scope']}

    def get_task(self, actor, tid):
        with self.connect() as db:
            t=self._task(db,tid)
            if actor!='CODEX' and t['owner']!=actor:
                raise Denied('ROLE_DENIED: task not assigned to you',403)
            return dict(t)

    def checkpoint(self, actor, tid, fencing, message):
        self._require(actor,WORKERS)
        if not isinstance(message,str) or not 1<=len(message)<=12000:
            raise ValueError('message length 1..12000')
        with self.transaction() as db:
            self._allow_activity(db)
            t=self._task(db,tid)
            lock=db.execute('SELECT * FROM locks WHERE task_id=?',(tid,)).fetchone()
            if not lock or t['state']!='RUNNING' or t['owner']!=actor or lock['owner']!=actor or lock['state']!='ACTIVE' or lock['fencing']!=fencing:
                raise Denied('STALE_OR_UNAUTHORIZED_LOCK',403)
            db.execute('UPDATE tasks SET checkpoint=?,checkpoint_at=?,updated=? WHERE id=?',
                       (message,utcnow(),utcnow(),tid))
            self._audit(db,actor,'CHECKPOINT',tid,'worker checkpoint')
        return {'task_id':tid,'checkpoint':'SAVED','fencing':fencing}

    def submit_self_qa(self, actor, tid, fencing, commit_sha, changed_paths, checks,
                       build_status, test_status, preview_status, evidence_ref):
        """Record worker self-test before review. ALL values are still worker claims.

        The backend enforces input shape and claimed path scope, not actual Git diffs.
        """
        self._require(actor, WORKERS)
        if not isinstance(commit_sha,str) or not SHA40.fullmatch(commit_sha):
            raise ValueError('commit_sha must be full 40-hex SHA')
        if not isinstance(changed_paths,list) or not changed_paths or len(changed_paths)>250:
            raise ValueError('changed_paths must be nonempty list')
        if not isinstance(checks,dict) or set(checks)!={'scope','diff','regression','safety'} or any(type(v) is not bool for v in checks.values()):
            raise ValueError('checks must include scope, diff, regression, safety booleans')
        if build_status not in ('PASS','FAIL','NOT_EXECUTED') or test_status not in ('PASS','FAIL','NOT_EXECUTED'):
            raise ValueError('invalid self-QA build/test')
        if preview_status not in ('PASS','FAIL','NOT_EXECUTED','NOT_APPLICABLE'):
            raise ValueError('invalid preview status')
        if not isinstance(evidence_ref,str) or not 5<=len(evidence_ref)<=1000:
            raise ValueError('evidence_ref required')
        normalized = [clean_scope(p) for p in changed_paths]
        with self.transaction() as db:
            self._allow_activity(db)
            t=self._task(db,tid)
            lock=db.execute('SELECT * FROM locks WHERE task_id=?',(tid,)).fetchone()
            if t['owner']!=actor or t['state']!='RUNNING' or not lock or lock['fencing']!=fencing or lock['state']!='ACTIVE':
                raise Denied('STALE_OR_UNAUTHORIZED_LOCK',403)
            outside=[p for p in normalized if p!=t['scope'] and not p.startswith(t['scope']+'/')]
            if outside:
                db.execute("UPDATE tasks SET state='FROZEN',updated=? WHERE id=?",(utcnow(),tid))
                db.execute("UPDATE locks SET state='FROZEN' WHERE task_id=?",(tid,))
                self._audit(db,actor,'OUT_OF_SCOPE_SELF_QA',tid,';'.join(outside)[:800])
                return {'task_id':tid,'state':'FROZEN','accepted':False,'error':'OUT_OF_SCOPE_CHANGED_PATHS', 'lock_released':False}
            passed = (build_status=='PASS' and test_status=='PASS' and all(checks.values()) and preview_status!='FAIL')
            result={'cycle':t['qa_round'],'commit_sha':commit_sha.lower(),'changed_paths':normalized,
                    'checks':checks,'build_claim':build_status,'test_claim':test_status,
                    'preview_claim':preview_status,'evidence_ref':evidence_ref,'pass_claim':passed,
                    'provenance':'WORKER_SELF_REPORTED_NOT_INDEPENDENTLY_VERIFIED'}
            newstate='SELF_QA_READY' if passed else 'RUNNING'
            db.execute('UPDATE tasks SET self_qa_json=?,state=?,updated=? WHERE id=?',
                       (json.dumps(result,ensure_ascii=False),newstate,utcnow(),tid))
            self._audit(db,actor,'SELF_QA_'+('PASS_CLAIM' if passed else 'FAIL_CLAIM'),tid,f'cycle={t["qa_round"]}')
        return {'task_id':tid,'state':newstate,'self_qa_claim':('PASS' if passed else 'FAIL'), 'independent_verification':'NOT_EXECUTED'}

    def acknowledge_feedback(self, actor, tid, fencing):
        """Worker acknowledges Codex findings before starting fresh self-QA cycle."""
        self._require(actor,WORKERS)
        with self.transaction() as db:
            self._allow_activity(db)
            t=self._task(db,tid)
            lock=db.execute('SELECT * FROM locks WHERE task_id=?',(tid,)).fetchone()
            if t['owner']!=actor or t['state']!='REWORK_REQUIRED' or not lock or lock['state']!='ACTIVE' or lock['fencing']!=fencing:
                raise Denied('NO_ACTIVE_FEEDBACK_OR_STALE_LOCK',403)
            db.execute("UPDATE tasks SET state='RUNNING',self_qa_json=NULL,result_json=NULL,qa_round=qa_round+1,updated=? WHERE id=?",(utcnow(),tid))
            self._audit(db,actor,'ACK_FEEDBACK_START_REWORK',tid,f'cycle={t["qa_round"]+1}')
        return {'task_id':tid,'state':'RUNNING','qa_round':t['qa_round']+1,'fencing':fencing, 'lock_released':False}

    def feedback_history(self, actor, tid):
        self._require(actor,('CODEX','ANTI-01','ANTI-02'))
        with self.connect() as db:
            t=self._task(db,tid)
            if actor!='CODEX' and t['owner']!=actor:raise Denied('ROLE_DENIED',403)
            return {'task_id':tid,'qa_round':t['qa_round'],'history':[dict(r) for r in
                db.execute('SELECT at,cycle,decision,report,issues_json,evidence_ref FROM reviews WHERE task_id=? ORDER BY id',(tid,))]}

    def submit_result(self, actor, tid, fencing, commit_sha, summary, build_status, test_status, evidence_ref):
        self._require(actor,WORKERS)
        if not isinstance(commit_sha,str) or not SHA40.fullmatch(commit_sha): raise ValueError('commit_sha must be 40 hex')
        if not isinstance(summary,str) or not 10<=len(summary)<=12000: raise ValueError('summary too short/long')
        if build_status not in ('PASS','FAIL','NOT_EXECUTED') or test_status not in ('PASS','FAIL','NOT_EXECUTED'):
            raise ValueError('invalid test statuses')
        if not isinstance(evidence_ref,str) or not 5<=len(evidence_ref)<=1000: raise ValueError('evidence_ref required')
        with self.transaction() as db:
            self._allow_activity(db)
            t=self._task(db,tid)
            lock=db.execute('SELECT * FROM locks WHERE task_id=?',(tid,)).fetchone()
            if t['owner']!=actor or t['state']!='SELF_QA_READY' or not lock or lock['fencing']!=fencing or lock['state']!='ACTIVE':
                raise Denied('SELF_QA_REQUIRED_OR_STALE_LOCK',403)
            self_qa=json.loads(t['self_qa_json'] or '{}')
            if self_qa.get('commit_sha')!=commit_sha.lower() or not self_qa.get('pass_claim') or build_status!='PASS' or test_status!='PASS':
                raise Denied('SELF_QA_COMMIT_OR_RESULT_MISMATCH',409)
            result={'commit_sha':commit_sha.lower(),'summary':summary,'build_claim':build_status,
                    'test_claim':test_status,'evidence_ref':evidence_ref,'qa_round':t['qa_round'],'source':'WORKER_SELF_REPORTED'}
            db.execute("UPDATE tasks SET result_json=?,state='SUBMITTED',qa_result=NULL,qa_actor=NULL,updated=? WHERE id=?",
                       (json.dumps(result,ensure_ascii=False),utcnow(),tid))
            self._audit(db,actor,'SUBMIT_RESULT',tid,commit_sha[:12])
        return {'task_id':tid,'state':'SUBMITTED','lock_released':False}

    def read_review(self, actor, tid):
        self._require(actor,('CODEX',))
        return self.get_task(actor,tid)

    def review_task(self, actor, tid, decision, report, evidence_ref, build_verified=False, tests_verified=False, preview_verified=False, preview_evidence_ref='', issues=None):
        self._require(actor,('CODEX',))
        if decision not in ('PASS_CODE_REVIEW','CHANGES_REQUESTED','BLOCKED'):
            raise ValueError('invalid QA decision')
        if not isinstance(report,str) or not 15<=len(report)<=12000:
            raise ValueError('QA report required')
        if not isinstance(evidence_ref,str) or not 5<=len(evidence_ref)<=1000:
            raise ValueError('review evidence reference required')
        if decision=='PASS_CODE_REVIEW' and not (build_verified is True and tests_verified is True):
            raise Denied('QA_GATE: independently verified build + tests required',409)
        if issues is None:issues=[]
        if not isinstance(issues,list) or len(issues)>100 or any(not isinstance(i,dict) or not all(k in i for k in ('id','file','expected','actual')) for i in issues):
            raise ValueError('issues must be list of {id,file,expected,actual}')
        if decision=='CHANGES_REQUESTED' and not issues:
            raise Denied('STRUCTURED_FEEDBACK_REQUIRED',409)
        with self.transaction() as db:
            self._allow_activity(db)
            t=self._task(db,tid)
            if t['state']!='SUBMITTED' or not t['result_json']:
                raise Denied('QA_SOURCE_NOT_READY')
            if decision=='PASS_CODE_REVIEW':
                res=json.loads(t['result_json'] or '{}')
                ev=db.execute("SELECT id FROM qa_evidence WHERE task_id=? AND qa_round=? AND commit_sha=? AND result='PASS' ORDER BY at DESC LIMIT 1",(tid,t['qa_round'],res.get('commit_sha',''))).fetchone()
                if not ev:raise Denied('INDEPENDENT_LOCAL_QA_EVIDENCE_REQUIRED',409)
            if decision=='PASS_CODE_REVIEW' and t['requires_preview'] and (preview_verified is not True or not isinstance(preview_evidence_ref,str) or len(preview_evidence_ref)<5):
                raise Denied('PREVIEW_GATE: independent preview evidence required',409)
            review={'status':decision,'report':report,'review_evidence':evidence_ref,
                    'reviewer':'CODEX','build_verified_by_codex':bool(build_verified),
                    'tests_verified_by_codex':bool(tests_verified),
                    'preview_verified_by_codex':bool(preview_verified),
                    'preview_evidence_ref':preview_evidence_ref, 'issues':issues, 'cycle':t['qa_round'],
                    'revit_host':'NOT_EXECUTED_UNLESS_EXTERNAL_EVIDENCE_VERIFIED'}
            nextstate={'PASS_CODE_REVIEW':'CODE_REVIEWED','CHANGES_REQUESTED':'REWORK_REQUIRED','BLOCKED':'FROZEN'}[decision]
            repeated=False
            if decision=='CHANGES_REQUESTED':
                previous=db.execute("SELECT issues_json FROM reviews WHERE task_id=? AND decision='CHANGES_REQUESTED' ORDER BY id DESC LIMIT 2",(tid,)).fetchall()
                fingerprint=json.dumps(issues,sort_keys=True,ensure_ascii=False)
                repeated=len(previous)==2 and all(json.dumps(json.loads(x['issues_json']),sort_keys=True,ensure_ascii=False)==fingerprint for x in previous)
                if repeated:nextstate='FROZEN'
            db.execute('UPDATE tasks SET state=?,qa_actor=?,qa_result=?,review_at=?,rework_count=rework_count+?,updated=? WHERE id=?',
                       (nextstate,actor,json.dumps(review,ensure_ascii=False),utcnow(),int(decision=='CHANGES_REQUESTED'),utcnow(),tid))
            db.execute('INSERT INTO reviews(at,task_id,cycle,reviewer,decision,report,issues_json,evidence_ref) VALUES(?,?,?,?,?,?,?,?)',
                       (utcnow(),tid,t['qa_round'],actor,decision,report,json.dumps(issues,ensure_ascii=False),evidence_ref))
            if nextstate=='FROZEN':db.execute("UPDATE locks SET state='FROZEN' WHERE task_id=?",(tid,))
            self._audit(db,actor,'CODEX_REVIEW',tid,decision+' cycle='+str(t['qa_round']))
        return {'task_id':tid,'state':nextstate,'decision':decision,'cycle':t['qa_round'],'escalation_recommended':decision=='CHANGES_REQUESTED' and t['rework_count']+1>=3,'no_progress_freeze':repeated,'lock_released':False}

    def freeze(self, actor, tid, reason):
        self._require(actor,('CODEX',))
        if not reason or len(reason)>500:raise ValueError('reason required')
        with self.transaction() as db:
            t=self._task(db,tid)
            if t['state'] not in ('RUNNING','SELF_QA_READY','REWORK_REQUIRED','SUBMITTED','CODE_REVIEWED'):
                raise Denied('TASK_NOT_FREEZABLE')
            db.execute("UPDATE tasks SET state='FROZEN',updated=? WHERE id=?",(utcnow(),tid))
            db.execute("UPDATE locks SET state='FROZEN' WHERE task_id=?",(tid,))
            self._audit(db,actor,'FREEZE',tid,reason)
        return {'task_id':tid,'state':'FROZEN','lock_released':False}

    def close_task(self, actor, tid, integration_sha, source_stopped):
        self._require(actor,('CODEX',))
        # Boolean stop assertions and arbitrary SHA strings are not integration proof.
        # No protected legacy release bridge is configured; retain all locks.
        raise Denied('VERIFIED_INTEGRATION_PROOF_REQUIRED: legacy release is disabled',409)

    def _qa_label(self, tid, qa_round):
        with self.connect() as db:
            row=db.execute('SELECT id,result FROM qa_evidence WHERE task_id=? AND qa_round=? ORDER BY at DESC LIMIT 1',(tid,qa_round)).fetchone()
            return row['result']+' #'+row['id'] if row else 'NOT_EXECUTED'

    def report(self, actor, wave_id='PILOT'):
        self._require(actor,('CODEX',))
        if not isinstance(wave_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',wave_id):
            raise ValueError('invalid wave_id')
        with self.connect() as db:
            tasks=[dict(r) for r in db.execute('SELECT * FROM tasks WHERE wave_id=? ORDER BY id',(wave_id,))]
        counters={s:sum(t['state']==s for t in tasks) for s in ('QUEUED','RUNNING','SELF_QA_READY','SUBMITTED','REWORK_REQUIRED','CODE_REVIEWED','FROZEN','CLOSED')}
        lines=[f'# K-TOOL Codex Wave Report — {wave_id}', '',f'Generated UTC: {utcnow()}',
               '',f'Tasks: {len(tasks)} | Running: {counters["RUNNING"]} | Submitted: {counters["SUBMITTED"]} | Code reviewed: {counters["CODE_REVIEWED"]} | Closed: {counters["CLOSED"]}',
               '', '> Registry evidence only. Worker PASS claims are not independently verified. Revit host: NOT_EXECUTED; GitHub CI: NOT_CONNECTED.', '']
        for t in tasks:
            res=json.loads(t['result_json']) if t['result_json'] else {}
            qa=json.loads(t['qa_result']) if t['qa_result'] else {}
            lines += [f'## {t["id"]} — {t["title"]}',f'- Owner: {t["owner"] or "UNASSIGNED"}; State: {t["state"]}; Scope: `{t["scope"]}`',
                      f'- Base: `{t["base_sha"]}`; Result: `{res.get("commit_sha","NONE")}`; Integration: `{t["integration_sha"] or "NONE"}`',
                      f'- Worker build/test claims: {res.get("build_claim","UNKNOWN")} / {res.get("test_claim","UNKNOWN")}',
                      f'- Worker evidence: {res.get("evidence_ref","NONE")}',
                      f'- QA loop: {t["qa_round"]} (reworks {t["rework_count"]}); Self-QA: {"RECORDED" if t["self_qa_json"] else "PENDING"}',
                      f'- Codex review: {qa.get("status","PENDING")} — {qa.get("review_evidence","NO REVIEW EVIDENCE")}',
                      f'- Local QA verified evidence: {self._qa_label(t["id"], t["qa_round"])}', '']
        return {'wave_id':wave_id,'tasks':tasks,'counts':counters,'markdown':'\n'.join(lines),
                'integration':self._integration(),'provenance':'LOCAL_REGISTRY_ONLY','qa_process':'SELF_QA_THEN_CODEX_REVIEW'}

    def audit(self, actor):
        self._require(actor,('CODEX',))
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 100')]


def hash_token(s): return hashlib.sha256(s.encode('utf-8')).hexdigest()


def identify(authorization, hashed_tokens):
    if not authorization.startswith('Bearer '):return None
    digest=hash_token(authorization[7:])
    for role, expected in hashed_tokens.items():
        if hmac.compare_digest(digest,expected): return role
    return None
