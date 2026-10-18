"""Durable controller-owned orchestration, additive to the v0.6 Task Registry.

No provider completion implies acceptance. Shared-user persistence is LOGICAL_ONLY;
protected CI/owner approval is a separate required trust boundary.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
from datetime import datetime, timezone, timedelta
from registry import Denied, clean_scope, collide


def stamp(): return datetime.now(timezone.utc).isoformat()
def encoded(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(value): return hashlib.sha256(encoded(value).encode()).hexdigest()
def require(actor, roles=('CODEX',)):
    if actor not in roles: raise Denied('ROLE_DENIED',403)
def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',value): raise ValueError('invalid identifier')
    return value


def git_identity(repo, sha):
    if not isinstance(sha,str) or not re.fullmatch(r'[a-fA-F0-9]{40}',sha): raise ValueError('immutable SHA required')
    repo=Path(repo).resolve(strict=True)
    def git(*args):
        p=subprocess.run(['git','-C',str(repo),*args],capture_output=True,text=True,timeout=15)
        if p.returncode: raise ValueError('actual Git commit required')
        return p.stdout.strip()
    if git('rev-parse',sha+'^{commit}').lower()!=sha.lower(): raise ValueError('commit mismatch')
    return str(repo),git('rev-parse',sha+'^{tree}')


class ControlStore:
    def __init__(self, dbfile):
        self.dbfile=str(dbfile);Path(dbfile).parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
            CREATE TABLE IF NOT EXISTS cc_contracts(hash TEXT PRIMARY KEY,contract_id TEXT NOT NULL,content TEXT NOT NULL,status TEXT NOT NULL,baseline INTEGER NOT NULL,approval TEXT,created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cc_revisions(hash TEXT PRIMARY KEY,content TEXT NOT NULL,published TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cc_missions(id TEXT PRIMARY KEY,revision TEXT NOT NULL,policy TEXT NOT NULL,status TEXT NOT NULL,created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cc_waves(id TEXT PRIMARY KEY,mission TEXT NOT NULL,parent TEXT,state TEXT NOT NULL,revision TEXT NOT NULL,created TEXT NOT NULL,resumed INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS cc_teams(id TEXT PRIMARY KEY,mission TEXT NOT NULL,owner TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cc_assignments(id TEXT PRIMARY KEY,mission TEXT NOT NULL,wave TEXT NOT NULL,team TEXT NOT NULL,owner TEXT NOT NULL,contract_hash TEXT NOT NULL,revision TEXT NOT NULL,repo TEXT NOT NULL,base_sha TEXT NOT NULL,allowed TEXT NOT NULL,readonly TEXT NOT NULL,forbidden TEXT NOT NULL,resources TEXT NOT NULL,dependencies TEXT NOT NULL,acceptance TEXT NOT NULL,capabilities TEXT NOT NULL,priority INTEGER NOT NULL,deadline TEXT,status TEXT NOT NULL,attempt INTEGER NOT NULL DEFAULT 0,epoch INTEGER NOT NULL DEFAULT 0,checkpoint_id TEXT,updated TEXT NOT NULL,review_iteration INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS cc_locks(scope TEXT NOT NULL,assignment TEXT NOT NULL,owner TEXT NOT NULL,epoch INTEGER NOT NULL,state TEXT NOT NULL,PRIMARY KEY(scope,assignment));
            CREATE TABLE IF NOT EXISTS cc_resource_locks(resource TEXT PRIMARY KEY,assignment TEXT NOT NULL,owner TEXT NOT NULL,epoch INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS cc_subagents(id TEXT PRIMARY KEY,parent TEXT NOT NULL,owner TEXT NOT NULL,allowed TEXT NOT NULL,tools TEXT NOT NULL,status TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cc_checkpoints(id TEXT PRIMARY KEY,assignment TEXT NOT NULL,epoch INTEGER NOT NULL,body TEXT NOT NULL,created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cc_steering(id TEXT PRIMARY KEY,mission TEXT NOT NULL,assignment TEXT NOT NULL,target TEXT NOT NULL,context_version TEXT NOT NULL,instruction TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,created TEXT NOT NULL,acknowledged TEXT);
            CREATE TABLE IF NOT EXISTS cc_human_requests(id TEXT PRIMARY KEY,mission TEXT NOT NULL,assignment TEXT,target TEXT NOT NULL,kind TEXT NOT NULL,body TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'PENDING',created TEXT NOT NULL,response TEXT);
            CREATE TABLE IF NOT EXISTS cc_feedback(id INTEGER PRIMARY KEY AUTOINCREMENT,assignment TEXT NOT NULL,iteration INTEGER NOT NULL,issues TEXT NOT NULL,fingerprint TEXT NOT NULL,evidence TEXT NOT NULL,candidate TEXT NOT NULL,created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cc_events(id INTEGER PRIMARY KEY AUTOINCREMENT,at TEXT NOT NULL,actor TEXT NOT NULL,kind TEXT NOT NULL,target TEXT,body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cc_deliveries(id TEXT PRIMARY KEY,assignment TEXT NOT NULL,owner TEXT NOT NULL,epoch INTEGER NOT NULL,payload TEXT NOT NULL,payload_hash TEXT NOT NULL,status TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,ack_deadline TEXT NOT NULL,created TEXT NOT NULL,acknowledged TEXT,UNIQUE(assignment,epoch));
            CREATE TABLE IF NOT EXISTS cc_supervisor_summaries(mission TEXT PRIMARY KEY,body TEXT NOT NULL,updated TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cc_worktrees(path TEXT PRIMARY KEY,owner TEXT NOT NULL,branch TEXT NOT NULL,common_dir TEXT NOT NULL,created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cc_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            INSERT OR IGNORE INTO cc_meta VALUES('mode','NORMAL');
            INSERT OR IGNORE INTO cc_meta VALUES('epoch','0');
            ''')
            # Additive, serialized migration; retain every existing request and token store.
            db.execute('BEGIN IMMEDIATE')
            try:
                version=db.execute("SELECT value FROM cc_meta WHERE key='human_requests_schema_version'").fetchone()
                if version and int(version[0])>2: raise ValueError('NEWER_HUMAN_REQUEST_SCHEMA')
                columns={r['name'] for r in db.execute('PRAGMA table_info(cc_human_requests)')}
                for name in ('deadline','decided_at'):
                    if name not in columns: db.execute('ALTER TABLE cc_human_requests ADD COLUMN '+name+' TEXT')
                db.execute("INSERT OR REPLACE INTO cc_meta VALUES('human_requests_schema_version','2')")
                db.execute('COMMIT')
            except Exception:
                db.execute('ROLLBACK');raise


    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.dbfile,timeout=15,isolation_level=None);db.row_factory=sqlite3.Row
        try: yield db
        finally: db.close()

    @contextmanager
    def transaction(self):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try: yield db;db.execute('COMMIT')
            except Exception: db.execute('ROLLBACK');raise

    def event(self,db,actor,kind,target,body):
        db.execute('INSERT INTO cc_events(at,actor,kind,target,body) VALUES(?,?,?,?,?)',(stamp(),actor,kind,target,encoded(body)))

    def row(self,db,table,key):
        if table not in ('cc_missions','cc_waves','cc_assignments','cc_subagents','cc_steering','cc_human_requests'): raise ValueError('unknown table')
        row=db.execute('SELECT * FROM '+table+' WHERE id=?',(key,)).fetchone()
        if row is None: raise Denied('NOT_FOUND',404)
        return row

    def mode(self,db): return db.execute("SELECT value FROM cc_meta WHERE key='mode'").fetchone()[0]
    def active_control(self,db):
        if self.mode(db) in ('EMERGENCY_STOP','RECOVERY_REQUIRED'): raise Denied('CONTROL_FROZEN',423)
        if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='control'").fetchone():
            legacy=db.execute("SELECT value FROM control WHERE key='mode'").fetchone()
            if legacy and legacy[0] in ('EMERGENCY_STOP','RECOVERY_REQUIRED'): raise Denied('LEGACY_CONTROL_FROZEN',423)

    def planning_control(self,db):
        self.active_control(db)
        if self.mode(db)!='NORMAL': raise Denied('LEAD_UNAVAILABLE_NO_NEW_PRIVILEGES')

    def propose_contract(self,actor,contract_id,content,affects_baseline=True):
        require(actor);identifier(contract_id)
        if not isinstance(content,dict) or not content.get('acceptance_criteria'): raise ValueError('acceptance criteria required')
        if type(affects_baseline) is not bool: raise ValueError('baseline flag must be bool')
        h=digest({'contract_id':contract_id,'content':content,'affects_baseline':affects_baseline})
        with self.transaction() as db:
            self.planning_control(db)
            db.execute('INSERT OR IGNORE INTO cc_contracts VALUES(?,?,?,?,?,?,?)',(h,contract_id,encoded(content),'PROPOSED',int(affects_baseline),None,stamp()))
            self.event(db,actor,'CONTRACT_PROPOSED',h,{'contract_id':contract_id})
        return h

    def approve_contract(self,actor,h,approval=None,owner_verifier=None):
        with self.transaction() as db:
            row=db.execute('SELECT * FROM cc_contracts WHERE hash=?',(h,)).fetchone()
            if row is None: raise Denied('CONTRACT_NOT_FOUND',404)
            if row['baseline']:
                require(actor,('OWNER',))
                if owner_verifier is None or owner_verifier(approval,h) is not True: raise Denied('VERIFIED_OWNER_APPROVAL_REQUIRED',403)
            else: require(actor)
            self.planning_control(db)
            db.execute("UPDATE cc_contracts SET status='APPROVED',approval=? WHERE hash=?",(encoded({'actor':actor,'reference':approval if row['baseline'] else 'DELEGATED_OPERATIONAL_POLICY'}),h))
            self.event(db,actor,'CONTRACT_APPROVED',h,{})
        return h

    def get_contract(self,actor,h):
        require(actor,('CODEX','ANTI-01','ANTI-02'))
        with self.connection() as db:
            row=db.execute("SELECT * FROM cc_contracts WHERE hash=? AND status='APPROVED'",(h,)).fetchone()
            if row is None: raise Denied('APPROVED_CONTRACT_REQUIRED',409)
            if digest({'contract_id':row['contract_id'],'content':json.loads(row['content']),'affects_baseline':bool(row['baseline'])})!=h: raise Denied('TAMPERED_CONTRACT')
            return dict(row)

    def publish_revision(self,actor,content):
        require(actor)
        if not isinstance(content,dict) or not content.get('contracts'): raise ValueError('pinned contracts required')
        for h in content['contracts']: self.get_contract(actor,h)
        h=digest(content)
        with self.transaction() as db:
            self.planning_control(db);db.execute('INSERT OR IGNORE INTO cc_revisions VALUES(?,?,?)',(h,encoded(content),stamp()))
            self.event(db,actor,'REVISION_PUBLISHED',h,{})
        return h

    def create_mission(self,actor,mission,revision,policy=None):
        require(actor);identifier(mission)
        policy=policy or {'sandbox':True,'max_workers':2,'dispatch_without_lead':False}
        if not isinstance(policy,dict) or type(policy.get('max_workers',2)) is not int or not 1<=policy.get('max_workers',2)<=2: raise ValueError('resource cap 1..2')
        if type(policy.get('sandbox',True)) is not bool or type(policy.get('dispatch_without_lead',False)) is not bool: raise ValueError('policy booleans required')
        with self.transaction() as db:
            self.planning_control(db)
            row=db.execute('SELECT * FROM cc_revisions WHERE hash=?',(revision,)).fetchone()
            if row is None or digest(json.loads(row['content']))!=revision: raise Denied('PUBLISHED_REVISION_REQUIRED')
            db.execute('INSERT INTO cc_missions VALUES(?,?,?,?,?)',(mission,revision,encoded(policy),'ACTIVE',stamp()))
            self.event(db,actor,'MISSION_CREATED',mission,{'revision':revision})

    def queue_wave(self,actor,mission,wave,assignments,parent=None):
        require(actor);identifier(wave)
        if not isinstance(assignments,list) or not assignments: raise ValueError('children required')
        prepared=[]
        for task in assignments:
            task=dict(task);identifier(task['id']);identifier(task['team'])
            if task['owner'] not in ('ANTI-01','ANTI-02'): raise ValueError('worker owner required')
            task['allowed_paths']=[clean_scope(p) for p in task['allowed_paths']]
            if not task['allowed_paths']: raise ValueError('write allowlist required')
            for field in ('readonly_paths','forbidden_paths'): task[field]=[clean_scope(p) for p in task.get(field,[])]
            if any(collide(a,b) for a in task['allowed_paths'] for b in task['readonly_paths']+task['forbidden_paths']):
                raise ValueError('write allowlist overlaps readonly/forbidden path')
            task['repo'],_=git_identity(task['repo'],task['base_sha'])
            task['resources']=sorted(set(identifier(r).casefold() for r in task.get('resource_locks',[])))
            task['dependencies']=[identifier(d) for d in task.get('dependencies',[])]
            task['tools']=sorted(set(task.get('tools',['read_source','write_source','run_tests','checkpoint'])))
            if not set(task['tools']) <= {'read_source','write_source','run_tests','checkpoint'}: raise ValueError('worker tool policy cannot grant admin')
            if task.get('deadline'):
                deadline=datetime.fromisoformat(task['deadline'])
                if deadline.tzinfo is None: raise ValueError('deadline timezone required')
            if not task.get('acceptance_criteria'): raise ValueError('acceptance criteria required')
            if type(task.get('priority',0)) is not int: raise ValueError('priority must be int')
            self.get_contract(actor,task['contract_hash']);prepared.append(task)
        request_hash=digest({'mission':mission,'wave':wave,'parent':parent,'assignments':prepared})
        with self.transaction() as db:
            self.planning_control(db);m=self.row(db,'cc_missions',mission)
            existing_wave=db.execute('SELECT * FROM cc_waves WHERE id=?',(wave,)).fetchone()
            if existing_wave:
                previous=db.execute("SELECT body FROM cc_events WHERE kind='WAVE_ATOMIC_QUEUED' AND target=? ORDER BY id LIMIT 1",(wave,)).fetchone()
                if previous and json.loads(previous[0]).get('request_hash')==request_hash:
                    return {'wave':wave,'idempotent':True}
                raise Denied('WAVE_REVISION_CONFLICT')
            rev=json.loads(db.execute('SELECT content FROM cc_revisions WHERE hash=?',(m['revision'],)).fetchone()[0])
            graph={r['id']:json.loads(r['dependencies']) for r in db.execute('SELECT id,dependencies FROM cc_assignments WHERE mission=?',(mission,))}
            for t in prepared:
                if t['id'] in graph: raise Denied('HISTORICAL_ASSIGNMENT_IMMUTABLE')
                if t['contract_hash'] not in rev['contracts']: raise Denied('STALE_CONTRACT_REVISION')
                graph[t['id']]=t['dependencies']
            visited=set();active=set()
            def visit(node):
                if node in active: raise Denied('CIRCULAR_DEPENDENCY')
                if node in visited: return
                if node not in graph: raise Denied('UNKNOWN_DEPENDENCY')
                active.add(node)
                for dep in graph[node]: visit(dep)
                active.remove(node);visited.add(node)
            for node in graph: visit(node)
            if parent:
                p=self.row(db,'cc_assignments',parent)
                if p['mission']!=mission or p['status']!='DEVELOPMENT': raise Denied('INVALID_PARENT')
                for task in prepared:
                    if task['owner']!=p['owner'] or task['team']!=p['team'] or task['contract_hash']!=p['contract_hash']: raise Denied('CHILD_AUTHORIZATION_ESCALATION')
                    if any(not any(path==a or path.startswith(a+'/') for a in json.loads(p['allowed'])) for path in task['allowed_paths']): raise Denied('CHILD_SCOPE_ESCALATION')
                    if not set(task['resources'])<=set(json.loads(p['resources'])): raise Denied('CHILD_RESOURCE_ESCALATION')
                    parent_policy=json.loads(p['acceptance'])
                    parent_tools=parent_policy.get('_tools',[]) if isinstance(parent_policy,dict) else ['read_source','write_source','run_tests','checkpoint']
                    if not set(task['tools'])<=set(parent_tools): raise Denied('CHILD_TOOL_ESCALATION')
                    task['readonly_paths']=sorted(set(task['readonly_paths']+json.loads(p['readonly'])))
                    task['forbidden_paths']=sorted(set(task['forbidden_paths']+json.loads(p['forbidden'])))
                db.execute("UPDATE cc_assignments SET status='WAITING_FOR_CHILDREN',updated=? WHERE id=?",(stamp(),parent))
                db.execute("UPDATE cc_locks SET state='DELEGATED' WHERE assignment=?",(parent,))
            db.execute('INSERT INTO cc_waves(id,mission,parent,state,revision,created) VALUES(?,?,?,?,?,?)',(wave,mission,parent,'WAITING',m['revision'],stamp()))
            for t in prepared:
                from worktree_manager import inspect as inspect_worktree
                worktree=inspect_worktree(t['repo'],t['base_sha'])
                bound=db.execute('SELECT * FROM cc_worktrees WHERE path=?',(worktree['path'],)).fetchone()
                if bound and (bound['owner']!=t['owner'] or bound['branch']!=worktree['branch'] or bound['common_dir']!=worktree['common_dir']):raise Denied('CANT_EDIT_WORKTREE_OWNER')
                db.execute('INSERT OR IGNORE INTO cc_worktrees VALUES(?,?,?,?,?)',(worktree['path'],t['owner'],worktree['branch'],worktree['common_dir'],stamp()))
                existing=db.execute('SELECT * FROM cc_teams WHERE id=?',(t['team'],)).fetchone()
                if existing and (existing['owner']!=t['owner'] or existing['mission']!=mission): raise Denied('TEAM_OWNER_MISMATCH')
                db.execute('INSERT OR IGNORE INTO cc_teams VALUES(?,?,?)',(t['team'],mission,t['owner']))
                db.execute('''INSERT INTO cc_assignments(id,mission,wave,team,owner,contract_hash,revision,repo,base_sha,allowed,readonly,forbidden,resources,dependencies,acceptance,capabilities,priority,deadline,status,updated)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(t['id'],mission,wave,t['team'],t['owner'],t['contract_hash'],m['revision'],t['repo'],t['base_sha'],encoded(t['allowed_paths']),encoded(t['readonly_paths']),encoded(t['forbidden_paths']),encoded(t['resources']),encoded(t['dependencies']),encoded({'criteria':t['acceptance_criteria'],'_tools':t['tools']}),encoded(t.get('capabilities',[])),t.get('priority',0),t.get('deadline'),'QUEUED',stamp()))
            self.event(db,actor,'WAVE_ATOMIC_QUEUED',wave,{'children':[t['id'] for t in prepared],'parent':parent,'request_hash':request_hash})
            return {'wave':wave,'idempotent':False}

    def acquire(self,db,t):
        allowed=json.loads(t['allowed']);resources=json.loads(t['resources'])
        ancestors=[];wave=self.row(db,'cc_waves',t['wave'])
        while wave['parent']:
            parent=self.row(db,'cc_assignments',wave['parent'])
            if parent['owner']!=t['owner'] or parent['status']!='WAITING_FOR_CHILDREN': raise Denied('INVALID_PARENT_DELEGATION')
            ancestors.append(parent['id']);wave=self.row(db,'cc_waves',parent['wave'])
        for lock in db.execute('SELECT * FROM cc_locks'):
            if lock['assignment'] in ancestors and lock['state']=='DELEGATED': continue
            if any(collide(path,lock['scope']) for path in allowed): raise Denied('CANT_EDIT')
        if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='locks'").fetchone():
            for lock in db.execute('SELECT scope FROM locks'):
                if any(collide(path,lock['scope']) for path in allowed): raise Denied('CANT_EDIT')
        for resource in resources:
            held=db.execute('SELECT assignment FROM cc_resource_locks WHERE resource=?',(resource,)).fetchone()
            if held and held[0] not in ancestors: raise Denied('CANT_EDIT_SHARED_RESOURCE')
            if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='resource_locks'").fetchone() and db.execute('SELECT 1 FROM resource_locks WHERE resource=?',(resource,)).fetchone(): raise Denied('CANT_EDIT_SHARED_RESOURCE')
        epoch=int(db.execute("SELECT value FROM cc_meta WHERE key='epoch'").fetchone()[0])+1
        db.execute("UPDATE cc_meta SET value=? WHERE key='epoch'",(str(epoch),))
        for path in allowed: db.execute('INSERT INTO cc_locks VALUES(?,?,?,?,?)',(path,t['id'],t['owner'],epoch,'ACTIVE'))
        for resource in resources: db.execute('INSERT OR IGNORE INTO cc_resource_locks VALUES(?,?,?,?)',(resource,t['id'],t['owner'],epoch))
        return epoch

    def dispatch(self,actor,capabilities=None,availability=None,ack_timeout_seconds=60):
        require(actor,('CODEX','CONTROLLER'));capabilities=capabilities or {'ANTI-01':[],'ANTI-02':[]}
        if type(ack_timeout_seconds) is not int or not 1<=ack_timeout_seconds<=3600: raise ValueError('ACK_TIMEOUT_1_TO_3600')
        if availability is not None and not isinstance(availability,dict): raise ValueError('AVAILABILITY_MAPPING_REQUIRED')
        result=[];pending=[]
        with self.transaction() as db:
            self.active_control(db)
            for t in db.execute("SELECT * FROM cc_assignments WHERE status='QUEUED' ORDER BY priority DESC,coalesce(deadline,'9999'),id").fetchall():
                mission=self.row(db,'cc_missions',t['mission']);policy=json.loads(mission['policy'])
                if self.mode(db)=='LEAD_UNAVAILABLE' and not policy.get('dispatch_without_lead',False): pending.append({'id':t['id'],'reason':'WAITING_FOR_CODEX'});continue
                busy=db.execute("SELECT count(*) FROM cc_assignments WHERE status NOT IN ('QUEUED','ACCEPTED','INTEGRATED','FAILED','WAITING_FOR_CHILDREN','CHILDREN_ACCEPTED_APPROVAL_PENDING')").fetchone()[0]
                if busy>=policy.get('max_workers',2): pending.append({'id':t['id'],'reason':'RESOURCE_LIMIT'});continue
                if db.execute("SELECT 1 FROM cc_assignments WHERE owner=? AND status NOT IN ('QUEUED','ACCEPTED','INTEGRATED','FAILED','WAITING_FOR_CHILDREN','CHILDREN_ACCEPTED_APPROVAL_PENDING')",(t['owner'],)).fetchone(): pending.append({'id':t['id'],'reason':'AGENT_BUSY'});continue
                if not policy.get('sandbox',False):
                    pending.append({'id':t['id'],'reason':'VERIFIED_RUNTIME_ATTESTATION_REQUIRED'});continue
                agent=capabilities.get(t['owner'],[])
                if isinstance(agent,dict):
                    if agent.get('available') is not True: pending.append({'id':t['id'],'reason':'AGENT_UNAVAILABLE'});continue
                    scope=[clean_scope(p) for p in agent.get('allowed_paths',[])]
                    if not scope or any(not any(path==a or path.startswith(a+'/') for a in scope) for path in json.loads(t['allowed'])):
                        pending.append({'id':t['id'],'reason':'CAPABILITY_SCOPE_UNAVAILABLE'});continue
                    agent=agent.get('capabilities',[])
                if availability is not None and availability.get(t['owner']) is not True:
                    pending.append({'id':t['id'],'reason':'AGENT_UNAVAILABLE'});continue
                if not set(json.loads(t['capabilities']))<=set(agent): pending.append({'id':t['id'],'reason':'CAPABILITY_UNAVAILABLE'});continue
                deps=json.loads(t['dependencies'])
                if any(self.row(db,'cc_assignments',d)['status']!='INTEGRATED' for d in deps): pending.append({'id':t['id'],'reason':'DEPENDENCY_PENDING'});continue
                try:
                    self._verify_worktree(db,t)
                    epoch=self.acquire(db,t)
                except Denied as exc: pending.append({'id':t['id'],'reason':str(exc)});continue
                db.execute("UPDATE cc_assignments SET status='TASK_ASSIGNED',epoch=?,attempt=attempt+1,updated=? WHERE id=?",(epoch,stamp(),t['id']))
                current=self.row(db,'cc_assignments',t['id'])
                delivery=self._enqueue_delivery(db,current,ack_timeout_seconds)
                result.append({'id':t['id'],'owner':t['owner'],'epoch':epoch,'delivery_id':delivery})
                self.event(db,actor,'TASK_ASSIGNED',t['id'],result[-1])
        return {'assigned':result,'pending':pending}

    def _verify_worktree(self,db,t,candidate=None):
        from worktree_manager import inspect as inspect_worktree
        observed=inspect_worktree(t['repo'],t['base_sha'],candidate)
        bound=db.execute('SELECT * FROM cc_worktrees WHERE path=?',(observed['path'],)).fetchone()
        if bound is None or bound['owner']!=t['owner'] or bound['branch']!=observed['branch'] or bound['common_dir']!=observed['common_dir']:
            raise Denied('WORKTREE_OWNERSHIP_REVALIDATION_REQUIRED')
        return observed

    def get_assignment(self,actor,assignment):
        with self.connection() as db:
            t=self.row(db,'cc_assignments',assignment)
            require(actor,('CODEX',t['owner']))
            return dict(t)

    def owned(self,db,actor,assignment,epoch):
        t=self.row(db,'cc_assignments',assignment);require(actor,(t['owner'],))
        if type(epoch) is not int or t['epoch']!=epoch or t['status'] not in ('TASK_ASSIGNED','DEVELOPMENT','SELF_QA','SYNC_REQUEST','WAITING_FOR_CODEX_REVIEW','CHANGES_REQUESTED'): raise Denied('STALE_OR_UNAUTHORIZED_EPOCH',403)
        self.active_control(db);return t

    def _enqueue_delivery(self,db,t,ack_timeout_seconds=60):
        payload={key:t[key] for key in ('id','mission','wave','owner','epoch','contract_hash','revision','repo','base_sha','allowed','readonly','forbidden','resources','acceptance','capabilities')}
        h=digest(payload);delivery=digest({'assignment':t['id'],'epoch':t['epoch'],'payload_hash':h})
        db.execute('INSERT INTO cc_deliveries(id,assignment,owner,epoch,payload,payload_hash,status,ack_deadline,created) VALUES(?,?,?,?,?,?,?,?,?)',
                   (delivery,t['id'],t['owner'],t['epoch'],encoded(payload),h,'PENDING',(datetime.now(timezone.utc)+timedelta(seconds=ack_timeout_seconds)).isoformat(),stamp()))
        self.event(db,'CONTROLLER','DELIVERY_ENQUEUED',t['id'],{'delivery_id':delivery,'epoch':t['epoch']})
        return delivery

    def delivery_outbox(self,actor,assignment=None):
        require(actor,('CODEX','CONTROLLER','ANTI-01','ANTI-02'))
        with self.connection() as db:
            query='SELECT * FROM cc_deliveries WHERE 1=1';args=[]
            if actor in ('ANTI-01','ANTI-02'): query+=' AND owner=?';args.append(actor)
            if assignment is not None:
                t=self.row(db,'cc_assignments',assignment);require(actor,('CODEX','CONTROLLER',t['owner']))
                query+=' AND assignment=?';args.append(assignment)
            return [dict(r) for r in db.execute(query+' ORDER BY created,id',args)]

    def _expire_delivery(self,db,delivery,now):
        if delivery['status'] not in ('PENDING','SENT') or datetime.fromisoformat(delivery['ack_deadline'])>now: return False
        db.execute("UPDATE cc_deliveries SET status='UNCERTAIN' WHERE id=?",(delivery['id'],))
        db.execute("UPDATE cc_assignments SET status='FROZEN',updated=? WHERE id=? AND epoch=? AND status='TASK_ASSIGNED'",(stamp(),delivery['assignment'],delivery['epoch']))
        db.execute("UPDATE cc_locks SET state='FROZEN' WHERE assignment=? AND epoch=?",(delivery['assignment'],delivery['epoch']))
        self.event(db,'CONTROLLER','DELIVERY_TIMEOUT_FROZEN',delivery['assignment'],{'delivery_id':delivery['id'],'epoch':delivery['epoch'],'replay_execution':False})
        return True

    def delivery_attempt(self,actor,delivery_id):
        require(actor,('CODEX','CONTROLLER'))
        expired=False
        with self.transaction() as db:
            self.active_control(db)
            delivery=db.execute('SELECT * FROM cc_deliveries WHERE id=?',(delivery_id,)).fetchone()
            if delivery is None: raise Denied('DELIVERY_NOT_FOUND')
            expired=self._expire_delivery(db,delivery,datetime.now(timezone.utc))
            if not expired:
                t=self.row(db,'cc_assignments',delivery['assignment'])
                if delivery['status'] not in ('PENDING','SENT') or t['epoch']!=delivery['epoch'] or t['status']!='TASK_ASSIGNED': raise Denied('DELIVERY_NOT_RETRYABLE')
                if digest(json.loads(delivery['payload']))!=delivery['payload_hash']: raise Denied('DELIVERY_TAMPERED')
                db.execute("UPDATE cc_deliveries SET status='SENT',attempts=attempts+1 WHERE id=?",(delivery_id,))
                self.event(db,actor,'DELIVERY_ATTEMPT',delivery['assignment'],{'delivery_id':delivery_id,'attempt':delivery['attempts']+1,'execution_started':False})
                result=dict(delivery);result['status']='SENT';result['attempts']+=1
        if expired: raise Denied('DELIVERY_TIMEOUT_FROZEN')
        return result

    def acknowledge(self,actor,assignment,epoch,contract_hash,delivery_id=None):
        expired=False
        with self.transaction() as db:
            t=self.owned(db,actor,assignment,epoch)
            if contract_hash!=t['contract_hash']: raise Denied('STALE_CONTRACT')
            if t['status'] not in ('TASK_ASSIGNED','DEVELOPMENT'): raise Denied('INVALID_ACK_STATE')
            delivery=db.execute('SELECT * FROM cc_deliveries WHERE assignment=? AND epoch=?',(assignment,epoch)).fetchone()
            if delivery is None: raise Denied('DELIVERY_NOT_FOUND')
            if delivery_id is not None and delivery['id']!=delivery_id: raise Denied('WRONG_DELIVERY')
            if delivery['status']=='ACKED': return {'delivery_id':delivery['id'],'status':'ACKED','idempotent':True}
            expired=self._expire_delivery(db,delivery,datetime.now(timezone.utc))
            if not expired:
                if delivery['status'] not in ('PENDING','SENT') or digest(json.loads(delivery['payload']))!=delivery['payload_hash']: raise Denied('DELIVERY_CONTEXT_UNCERTAIN')
                db.execute("UPDATE cc_deliveries SET status='ACKED',acknowledged=? WHERE id=?",(stamp(),delivery['id']))
                db.execute("UPDATE cc_assignments SET status='DEVELOPMENT',updated=? WHERE id=?",(stamp(),assignment))
                self.event(db,actor,'TASK_ACKNOWLEDGED',assignment,{'epoch':epoch,'contract_hash':contract_hash,'delivery_id':delivery['id']})
        if expired: raise Denied('DELIVERY_TIMEOUT_FROZEN')
        return {'delivery_id':delivery['id'],'status':'ACKED','idempotent':False}

    def supervisor_tick(self,actor='CONTROLLER',now=None):
        require(actor,('CODEX','CONTROLLER'))
        now=now or datetime.now(timezone.utc)
        if not isinstance(now,datetime) or now.tzinfo is None: raise ValueError('TIMEZONE_REQUIRED')
        with self.transaction() as db:
            frozen=[]
            for delivery in db.execute("SELECT * FROM cc_deliveries WHERE status IN ('PENDING','SENT')").fetchall():
                if self._expire_delivery(db,delivery,now): frozen.append(delivery['assignment'])
            summaries=[]
            for mission in db.execute('SELECT * FROM cc_missions').fetchall():
                tasks=[dict(t) for t in db.execute('SELECT * FROM cc_assignments WHERE mission=?',(mission['id'],))]
                counts={}
                for t in tasks: counts[t['status']]=counts.get(t['status'],0)+1
                overdue=[t['id'] for t in tasks if t['deadline'] and datetime.fromisoformat(t['deadline'])<=now and t['status'] not in ('INTEGRATED','FAILED')]
                human_overdue=[r['id'] for r in db.execute("SELECT * FROM cc_human_requests WHERE mission=? AND status='PENDING'",(mission['id'],)) if r['deadline'] and datetime.fromisoformat(r['deadline'])<=now]
                states=[t['status'] for t in tasks]
                state='COMPLETE' if states and all(x=='INTEGRATED' for x in states) else 'APPROVAL_PENDING' if states and all(x in ('ACCEPTED','INTEGRATED','CHILDREN_ACCEPTED_APPROVAL_PENDING') for x in states) else 'BLOCKED' if any(x in ('FROZEN','FAILED') for x in states) or self.mode(db) in ('EMERGENCY_STOP','RECOVERY_REQUIRED') else 'WAITING_FOR_CODEX' if self.mode(db)=='LEAD_UNAVAILABLE' else 'ACTIVE'
                summary={'mission':mission['id'],'status':state,'counts':counts,'overdue_assignments':overdue,'overdue_human_requests':human_overdue,'supervisor_mode':self.mode(db),'approval_granted':False,'source':'CONTROLLER_SQLITE','as_of':now.isoformat()}
                db.execute('UPDATE cc_missions SET status=? WHERE id=?',(state,mission['id']))
                db.execute('INSERT OR REPLACE INTO cc_supervisor_summaries VALUES(?,?,?)',(mission['id'],encoded(summary),stamp()))
                summaries.append(summary)
            self.event(db,actor,'SUPERVISOR_SUMMARY','',{'missions':len(summaries),'new_timeout_freezes':frozen,'approval_granted':False})
            return {'summaries':summaries,'frozen':frozen,'approval_granted':False}

    def checkpoint(self,actor,assignment,epoch,commit,changed_paths,build_evidence,blockers=None,artifacts=None):
        with self.connection() as db:
            t=dict(self.row(db,'cc_assignments',assignment))
            require(actor,(t['owner'],))
            if t['status'] not in ('DEVELOPMENT','SELF_QA'): raise Denied('TASK_ACKNOWLEDGMENT_REQUIRED')
        repo,tree=git_identity(t['repo'],commit)
        from ci_scope_gate import verify
        # Verify all actual paths; worker-supplied lists cannot hide modifications.
        modified=[]
        p=subprocess.run(['git','-C',repo,'diff','--name-only','--no-renames','-z',t['base_sha'],commit],capture_output=True,check=True)
        modified=[clean_scope(s.decode()) for s in p.stdout.split(b'\0') if s]
        with self.connection() as db:self._verify_worktree(db,t,commit)
        allowed=json.loads(t['allowed']);forbidden=json.loads(t['forbidden'])+json.loads(t['readonly'])
        ancestry=subprocess.run(['git','-C',repo,'merge-base','--is-ancestor',t['base_sha'],commit],capture_output=True)
        if ancestry.returncode or not modified or sorted(modified)!=sorted(clean_scope(p) for p in changed_paths): raise Denied('CHECKPOINT_DIFF_MISMATCH')
        if any(not any(p==a or p.startswith(a+'/') for a in allowed) or any(collide(p,f) for f in forbidden) for p in modified): raise Denied('CANT_EDIT')
        # Independently reject links/reparse points for each allowed subtree.
        for path in allowed:
            boundary=verify(repo,t['base_sha'],commit,path,[path],forbidden)
            if any('SYMLINK' in e or 'REPARSE' in e or 'JUNCTION' in e for e in boundary['errors']): raise Denied('UNSAFE_CHECKPOINT_PATH')
        body={'base_sha':t['base_sha'],'commit_sha':commit,'tree':tree,'changed_paths':modified,'contract_hash':t['contract_hash'],
              'epoch':epoch,'build_evidence':build_evidence,'blockers':blockers or [],'artifacts':artifacts or [],'verification':'CLAIMED_PENDING_INDEPENDENT_QA'}
        h=digest({'assignment':assignment,'body':body})
        with self.transaction() as db:
            self.owned(db,actor,assignment,epoch)
            db.execute('INSERT OR IGNORE INTO cc_checkpoints VALUES(?,?,?,?,?)',(h,assignment,epoch,encoded(body),stamp()))
            db.execute('UPDATE cc_assignments SET checkpoint_id=?,updated=? WHERE id=?',(h,stamp(),assignment))
            self.event(db,actor,'CHECKPOINT_RECEIVED',assignment,{'checkpoint_id':h})
        return h

    def submit_claim(self,actor,assignment,epoch):
        with self.transaction() as db:
            t=self.owned(db,actor,assignment,epoch)
            if not t['checkpoint_id'] or t['status'] not in ('DEVELOPMENT','SELF_QA'): raise Denied('VERIFIED_CHECKPOINT_REQUIRED')
            checkpoint=db.execute('SELECT epoch FROM cc_checkpoints WHERE id=?',(t['checkpoint_id'],)).fetchone()
            if checkpoint is None or checkpoint['epoch']!=epoch: raise Denied('CURRENT_EPOCH_CHECKPOINT_REQUIRED')
            state='WAITING_FOR_CODEX_REVIEW' if self.mode(db)=='LEAD_UNAVAILABLE' else 'SYNC_REQUEST'
            db.execute('UPDATE cc_assignments SET status=?,updated=? WHERE id=?',(state,stamp(),assignment))
            self.event(db,actor,'SELF_QA_CLAIMED',assignment,{'state':state,'independent_qa':'NOT_EXECUTED'})

    def provider_completed(self,actor,assignment,epoch):
        with self.transaction() as db:
            self.owned(db,actor,assignment,epoch)
            self.event(db,actor,'PROVIDER_COMPLETED_CLAIM',assignment,{'accepted':False})

    def feedback(self,actor,assignment,issues,evidence):
        require(actor)
        if not issues or any(not all(k in i for k in ('id','severity','path','expected','actual')) for i in issues): raise ValueError('structured defects required')
        with self.transaction() as db:
            if self.mode(db)!='NORMAL': raise Denied('CODEX_REVIEW_UNAVAILABLE')
            t=self.row(db,'cc_assignments',assignment)
            if t['status'] not in ('SYNC_REQUEST','WAITING_FOR_CODEX_REVIEW'): raise Denied('REVIEW_NOT_PENDING')
            roots=[re.sub(r'\s+',' ',str(i['root_cause']).strip().casefold()) for i in issues if isinstance(i.get('root_cause'),str) and i['root_cause'].strip()]
            fp=digest({'root_causes':sorted(set(roots))}) if len(roots)==len(issues) else digest([{k:i[k] for k in ('id','path','expected','actual')} for i in issues])
            previous=db.execute('SELECT fingerprint FROM cc_feedback WHERE assignment=? ORDER BY id DESC LIMIT 2',(assignment,)).fetchall()
            frozen=len(previous)==2 and all(r[0]==fp for r in previous)
            db.execute('INSERT INTO cc_feedback(assignment,iteration,issues,fingerprint,evidence,candidate,created) VALUES(?,?,?,?,?,?,?)',
                       (assignment,t['review_iteration'],encoded(issues),fp,evidence,t['checkpoint_id'],stamp()))
            state='FROZEN' if frozen else 'CHANGES_REQUESTED'
            db.execute('UPDATE cc_assignments SET status=?,updated=? WHERE id=?',(state,stamp(),assignment))
            if frozen: db.execute("UPDATE cc_locks SET state='FROZEN' WHERE assignment=?",(assignment,))
            self.event(db,actor,'CODEX_FEEDBACK',assignment,{'state':state,'issues':issues})

    def acknowledge_feedback(self,actor,assignment,epoch):
        with self.transaction() as db:
            t=self.owned(db,actor,assignment,epoch)
            if t['status']!='CHANGES_REQUESTED': raise Denied('FEEDBACK_NOT_PENDING')
            db.execute("UPDATE cc_assignments SET status='DEVELOPMENT',review_iteration=review_iteration+1,checkpoint_id=NULL,updated=? WHERE id=?",(stamp(),assignment))
            self.event(db,actor,'FEEDBACK_ACKNOWLEDGED',assignment,{'next_iteration':t['review_iteration']+1})

    def accept(self,actor,assignment,evidence,verifier=None):
        require(actor)
        with self.connection() as db:
            t=dict(self.row(db,'cc_assignments',assignment));m=dict(self.row(db,'cc_missions',t['mission']))
            cp=db.execute('SELECT body FROM cc_checkpoints WHERE id=?',(t['checkpoint_id'],)).fetchone()
        if cp is None or verifier is None: raise Denied('INDEPENDENT_VERIFIER_REQUIRED')
        binding={'mission_id':t['mission'],'task_id':assignment,'iteration':t['review_iteration'],'epoch':t['epoch'],
                 'contract_hash':t['contract_hash'],'candidate_sha':json.loads(cp[0])['commit_sha']}
        verified=verifier(evidence,binding)
        if not json.loads(m['policy']).get('sandbox',True): raise Denied('PROTECTED_EXTERNAL_VERIFIER_NOT_CONFIGURED')
        acceptable=('LOCAL_VERIFIED',)
        if not isinstance(verified,dict) or verified.get('status') not in acceptable: raise Denied('TRUSTED_EVIDENCE_REQUIRED')
        with self.transaction() as db:
            if self.mode(db)!='NORMAL': raise Denied('CODEX_REVIEW_UNAVAILABLE')
            current=self.row(db,'cc_assignments',assignment)
            if current['epoch']!=t['epoch'] or current['checkpoint_id']!=t['checkpoint_id'] or current['status'] not in ('SYNC_REQUEST','WAITING_FOR_CODEX_REVIEW'): raise Denied('STALE_REVIEW')
            db.execute("UPDATE cc_assignments SET status='ACCEPTED',updated=? WHERE id=?",(stamp(),assignment))
            self.event(db,actor,'CODEX_ACCEPTED',assignment,{'verification':verified['status'],'release':'APPROVAL_PENDING'})
            self._barrier(db,t['wave'])

    def _barrier(self,db,wave):
        w=self.row(db,'cc_waves',wave)
        states=[r[0] for r in db.execute('SELECT status FROM cc_assignments WHERE wave=?',(wave,))]
        if states and all(s in ('ACCEPTED','INTEGRATED','FAILED') for s in states) and not w['resumed']:
            state='COMPLETE' if all(s in ('ACCEPTED','INTEGRATED') for s in states) else 'BLOCKED'
            db.execute('UPDATE cc_waves SET state=?,resumed=1 WHERE id=?',(state,wave))
            if w['parent']: db.execute("UPDATE cc_assignments SET status=?,updated=? WHERE id=? AND status='WAITING_FOR_CHILDREN'",('CHILDREN_ACCEPTED_APPROVAL_PENDING' if state=='COMPLETE' else 'BLOCKED',stamp(),w['parent']))
            self.event(db,'CONTROLLER','WAVE_BARRIER_TERMINAL',wave,{'state':state})

    def add_subagent(self,actor,assignment,epoch,subagent,allowed_paths,tools,parent_tools):
        identifier(subagent)
        if subagent in ('CODEX','ANTI-01','ANTI-02','OWNER','CONTROLLER'): raise Denied('RESERVED_AGENT_ID')
        with self.transaction() as db:
            t=self.owned(db,actor,assignment,epoch)
            allowed=[clean_scope(p) for p in allowed_paths]
            if not allowed or any(not any(p==a or p.startswith(a+'/') for a in json.loads(t['allowed'])) for p in allowed): raise Denied('CHILD_SCOPE_ESCALATION')
            # Parent tool policy is controller-owned; never trust a worker-supplied expansion.
            baseline=set(json.loads(t['acceptance']).get('_tools',[]))
            if set(parent_tools)!=baseline or not set(tools)<=baseline: raise Denied('CHILD_TOOL_ESCALATION')
            db.execute('INSERT INTO cc_subagents VALUES(?,?,?,?,?,?)',(subagent,assignment,actor,encoded(allowed),encoded(sorted(set(tools))),'AUTHORIZED'))
            self.event(db,actor,'SUBAGENT_AUTHORIZED',subagent,{'assignment':assignment})

    def steer(self,actor,mission,assignment,target,context_version,instruction):
        with self.transaction() as db:
            t=self.row(db,'cc_assignments',assignment);require(actor,('CODEX',t['owner']))
            if t['mission']!=mission or context_version!=t['revision']: raise Denied('STEERING_CONTEXT_MISMATCH')
            if t['status'] in ('ACCEPTED','INTEGRATED','FAILED'): raise Denied('COMPLETED_ASSIGNMENT_IMMUTABLE')
            valid=target==t['owner'] or db.execute('SELECT 1 FROM cc_subagents WHERE id=? AND parent=? AND owner=?',(target,assignment,t['owner'])).fetchone()
            if not valid: raise Denied('WRONG_STEERING_TARGET',403)
            if not isinstance(instruction,str) or not 1<=len(instruction)<=4000: raise ValueError('instruction required')
            h=digest({'mission':mission,'assignment':assignment,'target':target,'context':context_version,'instruction':instruction})
            db.execute('INSERT OR IGNORE INTO cc_steering VALUES(?,?,?,?,?,?,?,?,?,?)',(h,mission,assignment,target,context_version,instruction,'ADVISORY','PENDING',stamp(),None))
            self.event(db,actor,'STEERING_QUEUED',h,{'target':target,'kind':'ADVISORY'})
            return h

    def acknowledge_steering(self,actor,steering,target):
        with self.transaction() as db:
            s=self.row(db,'cc_steering',steering);t=self.row(db,'cc_assignments',s['assignment'])
            require(actor,(t['owner'],))
            if s['target']!=target: raise Denied('WRONG_STEERING_TARGET',403)
            db.execute("UPDATE cc_steering SET status='ACKNOWLEDGED',acknowledged=? WHERE id=?",(stamp(),steering))
            self.event(db,actor,'STEERING_ACKNOWLEDGED',steering,{'target':target})

    def human_request(self,actor,mission,kind,body,assignment=None,deadline=None):
        require(actor,('CODEX','ANTI-01','ANTI-02'))
        if kind not in ('input','direction','review','approval','INPUT_REQUIRED','DIRECTION_REQUIRED',
                        'PERMISSION_REQUIRED','CONTRACT_CHANGE','MERGE_APPROVAL','RELEASE_APPROVAL'):
            raise ValueError('typed request required')
        if deadline is not None:
            if not isinstance(deadline,str): raise ValueError('timezone-aware deadline required')
            try: parsed=datetime.fromisoformat(deadline.replace('Z','+00:00'))
            except ValueError: raise ValueError('timezone-aware deadline required') from None
            if parsed.tzinfo is None: raise ValueError('timezone-aware deadline required')
            if parsed<=datetime.now(timezone.utc): raise ValueError('future deadline required')
            deadline=parsed.astimezone(timezone.utc).isoformat()
        if not isinstance(body,str) or not 1<=len(body)<=4000: raise ValueError('request body required')
        with self.transaction() as db:
            self.row(db,'cc_missions',mission)
            if assignment:
                t=self.row(db,'cc_assignments',assignment);require(actor,('CODEX',t['owner']))
                if t['mission']!=mission: raise Denied('MISSION_MISMATCH')
            elif actor!='CODEX': raise Denied('ASSIGNMENT_REQUIRED')
            identity={'mission':mission,'assignment':assignment,'kind':kind,'body':body}
            if deadline is not None: identity['deadline']=deadline
            h=digest(identity)
            db.execute('INSERT OR IGNORE INTO cc_human_requests(id,mission,assignment,target,kind,body,created,deadline) VALUES(?,?,?,?,?,?,?,?)',(h,mission,assignment,'OWNER',kind,body,stamp(),deadline))
            self.event(db,actor,'HUMAN_REQUEST',h,{'kind':kind,'privilege_granted':False})
            return h

    def resolve_human_request(self,actor,request,response,approval=None,owner_verifier=None):
        require(actor,('OWNER',))
        if owner_verifier is None or owner_verifier(approval,request) is not True: raise Denied('VERIFIED_OWNER_REQUIRED')
        with self.transaction() as db:
            r=self.row(db,'cc_human_requests',request)
            if r['status']!='PENDING': raise Denied('REQUEST_ALREADY_RESOLVED')
            if r['deadline'] and datetime.fromisoformat(r['deadline'])<=datetime.now(timezone.utc):
                raise Denied('REQUEST_EXPIRED')
            db.execute("UPDATE cc_human_requests SET status='RESOLVED',response=?,decided_at=? WHERE id=?",(encoded(response),stamp(),request))
            self.event(db,actor,'HUMAN_REQUEST_RESOLVED',request,{'privilege_granted':False})

    def set_mode(self,actor,mode):
        require(actor)
        if mode not in ('NORMAL','LEAD_UNAVAILABLE','RECOVERY_REQUIRED','EMERGENCY_STOP'): raise ValueError('invalid mode')
        if mode=='NORMAL': raise Denied('VERIFIED_RECOVERY_REQUIRED')
        with self.transaction() as db:
            if self.mode(db)=='EMERGENCY_STOP' and mode!='EMERGENCY_STOP': raise Denied('OWNER_EMERGENCY_RECOVERY_REQUIRED')
            db.execute("UPDATE cc_meta SET value=? WHERE key='mode'",(mode,))
            if mode in ('EMERGENCY_STOP','RECOVERY_REQUIRED'):
                db.execute("UPDATE cc_assignments SET status='FROZEN' WHERE id IN (SELECT assignment FROM cc_locks)")
                db.execute("UPDATE cc_locks SET state='FROZEN'")
                if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='control'").fetchone():
                    db.execute("UPDATE control SET value=? WHERE key='mode'",(mode,))
                    db.execute("UPDATE locks SET state='FROZEN'")
                    db.execute("UPDATE tasks SET state='FROZEN' WHERE id IN (SELECT task_id FROM locks)")
            self.event(db,actor,'SUPERVISOR_MODE','',{'mode':mode})

    def reconcile_startup(self):
        with self.transaction() as db:
            count=db.execute("SELECT count(*) FROM cc_locks WHERE state IN ('ACTIVE','DELEGATED')").fetchone()[0]
            if count:
                db.execute("UPDATE cc_assignments SET status='FROZEN',updated=? WHERE id IN (SELECT assignment FROM cc_locks)",(stamp(),))
                db.execute("UPDATE cc_locks SET state='FROZEN'")
                db.execute("UPDATE cc_meta SET value='RECOVERY_REQUIRED' WHERE key='mode'")
                self.event(db,'CONTROLLER','STARTUP_RECONCILE','',{'frozen_locks':count})
            return {'mode':self.mode(db),'frozen_locks':count}

    def recover_lead(self,actor):
        """Re-authenticated lead recovers summaries; no worker stops or approvals inferred."""
        require(actor)
        with self.transaction() as db:
            if self.mode(db)!='LEAD_UNAVAILABLE': raise Denied('LEAD_RECOVERY_NOT_REQUIRED')
            checkpoints=[]
            for row in db.execute('SELECT * FROM cc_checkpoints'):
                task=self.row(db,'cc_assignments',row['assignment']);body=json.loads(row['body'])
                _,tree=git_identity(task['repo'],body['commit_sha'])
                if tree!=body['tree'] or digest({'assignment':row['assignment'],'body':body})!=row['id']: raise Denied('CHECKPOINT_TAMPERED')
                checkpoints.append({'assignment':row['assignment'],'checkpoint_id':row['id'],'epoch':row['epoch']})
            summary={'checkpoints':checkpoints,'source':'CONTROLLER_GIT_VERIFIED','independent_qa':'NOT_INFERRED','approval_granted':False}
            db.execute("UPDATE cc_meta SET value='NORMAL' WHERE key='mode'")
            db.execute("UPDATE cc_assignments SET status='SYNC_REQUEST' WHERE status='WAITING_FOR_CODEX_REVIEW'")
            self.event(db,actor,'LEAD_RECOVERED','',{'summary_hash':digest(summary),**summary})
            return summary

    def relinquish_after_integration(self,actor,assignment,integration_sha,proof=None,integration_verifier=None):
        require(actor)
        with self.connection() as db:
            t=dict(self.row(db,'cc_assignments',assignment));m=self.row(db,'cc_missions',t['mission'])
            if not json.loads(m['policy']).get('sandbox',True): raise Denied('PROTECTED_INTEGRATION_BACKEND_NOT_CONFIGURED')
        git_identity(t['repo'],integration_sha)
        if integration_verifier is None or integration_verifier(proof,dict(t),integration_sha) is not True: raise Denied('VERIFIED_INTEGRATION_AND_STOP_REQUIRED')
        with self.transaction() as db:
            self.planning_control(db);current=self.row(db,'cc_assignments',assignment)
            if current['status']!='ACCEPTED' or current['epoch']!=t['epoch']: raise Denied('ACCEPTED_CURRENT_EPOCH_REQUIRED')
            db.execute('DELETE FROM cc_locks WHERE assignment=?',(assignment,))
            db.execute('DELETE FROM cc_resource_locks WHERE assignment=?',(assignment,))
            db.execute("UPDATE cc_assignments SET status='INTEGRATED',updated=? WHERE id=?",(stamp(),assignment))
            self.event(db,actor,'VERIFIED_RELINQUISH',assignment,{'integration_sha':integration_sha,'sandbox_only':True})

    def resume(self,actor,assignment,process_evidence,stop_verifier=None):
        require(actor)
        if stop_verifier is None or stop_verifier(process_evidence,assignment) is not True: raise Denied('VERIFIED_PROCESS_STOP_REQUIRED')
        with self.transaction() as db:
            if self.mode(db)=='EMERGENCY_STOP': raise Denied('OWNER_EMERGENCY_RECOVERY_REQUIRED')
            t=self.row(db,'cc_assignments',assignment)
            if t['status']!='FROZEN': raise Denied('TASK_NOT_FROZEN')
            epoch=int(db.execute("SELECT value FROM cc_meta WHERE key='epoch'").fetchone()[0])+1
            db.execute("UPDATE cc_meta SET value=? WHERE key='epoch'",(str(epoch),))
            db.execute("UPDATE cc_assignments SET status='TASK_ASSIGNED',epoch=?,updated=? WHERE id=?",(epoch,stamp(),assignment))
            db.execute("UPDATE cc_locks SET state='ACTIVE',epoch=? WHERE assignment=?",(epoch,assignment))
            db.execute('UPDATE cc_resource_locks SET epoch=? WHERE assignment=?',(epoch,assignment))
            db.execute("UPDATE cc_meta SET value='NORMAL' WHERE key='mode'")
            db.execute("UPDATE cc_deliveries SET status='SUPERSEDED' WHERE assignment=? AND status IN ('PENDING','SENT','UNCERTAIN')",(assignment,))
            self._enqueue_delivery(db,self.row(db,'cc_assignments',assignment))
            self.event(db,actor,'SAFE_RESUME',assignment,{'epoch':epoch,'checkpoint_id':t['checkpoint_id']})
            return epoch

    def snapshot(self,actor='CODEX'):
        require(actor)
        with self.connection() as db:
            result={name:[dict(r) for r in db.execute('SELECT * FROM '+table)] for name,table in (
                ('missions','cc_missions'),('waves','cc_waves'),('teams','cc_teams'),('assignments','cc_assignments'),
                ('subagents','cc_subagents'),('revisions','cc_revisions'),('steering','cc_steering'),('human_requests','cc_human_requests'),
                ('events','cc_events'),('deliveries','cc_deliveries'),('supervisor_summaries','cc_supervisor_summaries'),('checkpoints','cc_checkpoints'),('contracts','cc_contracts'),('feedback','cc_feedback'))}
            result['supervisor_mode']=self.mode(db)
            result['performance']=[{'agent':owner,'source':'CONTROLLER_MEASURED','accepted_tasks':sum(t['owner']==owner and t['status'] in ('ACCEPTED','INTEGRATED') for t in result['assignments']),
                'correction_iterations':sum(t['review_iteration']-1 for t in result['assignments'] if t['owner']==owner),
                'blocked_tasks':sum(t['owner']==owner and t['status']=='FROZEN' for t in result['assignments']),
                'cost_per_accepted_task':'UNKNOWN','provider_quota':'UNKNOWN','teamwork':'UNKNOWN'} for owner in ('ANTI-01','ANTI-02')]
            result.update({'isolation_level':'LOGICAL_ONLY','source':'CONTROLLER_SQLITE','last_verified_at':stamp(),
                           'trusted_ci':'UNKNOWN','owner_release_approval':'UNKNOWN','real_antigravity_sessions':'UNKNOWN'})
            return result
