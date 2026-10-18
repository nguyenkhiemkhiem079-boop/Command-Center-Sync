"""Additive local governance. No token issuance and no protected owner backend.
All authority originates in a verified bearer binding, never an HTTP role field.
Same-user Python/SQLite is LOGICAL_ONLY; production approvals always fail closed.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import copy
import json
from pathlib import Path
import re
import secrets
import sqlite3

from registry import Denied, clean_scope, identify
from orchestration import ControlStore, digest

ROLES = frozenset(('OWNER','CODEX_LEAD','ANTI_WORKER','SUBAGENT','TRUSTED_QA_RUNNER','READ_ONLY_OBSERVER'))
RISK = ('LOW','MEDIUM','HIGH','CRITICAL')
ACTIONS = {
    'status.read': ('LOW',ROLES),
    'knowledge.read': ('LOW',ROLES),
    'knowledge.write': ('MEDIUM',frozenset(('OWNER','CODEX_LEAD','TRUSTED_QA_RUNNER'))),
    'task.assign': ('MEDIUM',frozenset(('OWNER','CODEX_LEAD'))),
    'source.read': ('LOW',ROLES),
    'source.write': ('MEDIUM',frozenset(('ANTI_WORKER','SUBAGENT'))),
    'qa.execute': ('MEDIUM',frozenset(('TRUSTED_QA_RUNNER',))),
    'contract.change': ('HIGH',frozenset(('OWNER','CODEX_LEAD'))),
    'merge': ('HIGH',frozenset(('OWNER','CODEX_LEAD'))),
    'release': ('CRITICAL',frozenset(('OWNER',))),
    'data.delete': ('CRITICAL',frozenset(('OWNER',))),
    'worker.stop': ('HIGH',frozenset(('OWNER','CODEX_LEAD'))),
    'security.change': ('CRITICAL',frozenset(('OWNER',))),
    'shared_core.change': ('HIGH',frozenset(('OWNER','CODEX_LEAD'))),
}
MAP = {'CODEX':'CODEX_LEAD','ANTI-01':'ANTI_WORKER','ANTI-02':'ANTI_WORKER',
       'OWNER':'OWNER','CODEX_LEAD':'CODEX_LEAD','TRUSTED_QA_RUNNER':'TRUSTED_QA_RUNNER',
       'READ_ONLY_OBSERVER':'READ_ONLY_OBSERVER'}
HEX40 = re.compile(r'^[a-f0-9]{40}$')
HEX64 = re.compile(r'^[a-f0-9]{64}$')


def _now():
    return datetime.now(timezone.utc)


def _time(value):
    if not isinstance(value,str):
        raise ValueError('Timezone-aware timestamp required')
    value=datetime.fromisoformat(value.replace('Z','+00:00'))
    if value.tzinfo is None:
        raise ValueError('Timezone-aware timestamp required')
    return value.astimezone(timezone.utc)


def _scopes(values):
    if not isinstance(values,list) or not values:
        raise ValueError('Nonempty explicit scope list required')
    return sorted(set(clean_scope(value) for value in values))


@dataclass(frozen=True,eq=False)
class Principal:
    subject: str
    role: str
    source: str
    _handle: str
    assignment: str | None = None
    epoch: int | None = None


class GovernanceStore:
    def __init__(self,dbfile,credential_hashes=None,environment='PRODUCTION'):
        if environment not in ('PRODUCTION','TEST_FIXTURE'):
            raise ValueError('Unknown governance environment')
        self.dbfile=str(dbfile)
        self._hashes=copy.deepcopy(credential_hashes or {})
        self.environment=environment
        self._principals={}
        # Reuse the same Registry/controller DB and existing Human Requests schema.
        ControlStore(dbfile)
        with self.transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS cc_knowledge_versions(
                key TEXT NOT NULL,version INTEGER NOT NULL,hash TEXT NOT NULL UNIQUE,
                previous_hash TEXT,content TEXT NOT NULL,provenance TEXT NOT NULL,
                author TEXT NOT NULL,created TEXT NOT NULL,PRIMARY KEY(key,version))''')
            db.execute('''CREATE TABLE IF NOT EXISTS cc_principal_bindings(
                subject TEXT PRIMARY KEY,role TEXT NOT NULL,source TEXT NOT NULL,
                assignment TEXT,epoch INTEGER,updated TEXT NOT NULL)''')
            columns={row['name'] for row in db.execute('PRAGMA table_info(cc_human_requests)')}
            additions={'gov_binding':'TEXT','gov_binding_digest':'TEXT','gov_risk':'TEXT',
                'gov_requester':'TEXT','gov_environment':'TEXT','gov_decision_by':'TEXT',
                'gov_consumed_at':'TEXT','gov_use_count':'INTEGER NOT NULL DEFAULT 0'}
            for name,definition in additions.items():
                if name not in columns:
                    db.execute('ALTER TABLE cc_human_requests ADD COLUMN '+name+' '+definition)
            version=db.execute("SELECT value FROM cc_meta WHERE key='governance_schema_version'").fetchone()
            if version and int(version[0])>1:
                raise ValueError('Newer governance schema present')
            db.execute("INSERT OR REPLACE INTO cc_meta VALUES('governance_schema_version','1')")

    @contextmanager
    def transaction(self):
        db=sqlite3.connect(self.dbfile,timeout=15,isolation_level=None)
        db.row_factory=sqlite3.Row
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.execute('COMMIT')
        except Exception:
            db.execute('ROLLBACK')
            raise
        finally:
            db.close()

    def _event(self,db,principal,kind,target,body):
        db.execute('INSERT INTO cc_events(at,actor,kind,target,body) VALUES(?,?,?,?,?)',
            (_now().isoformat(),principal.subject,kind,target,json.dumps({
                'source':'GOVERNANCE','principal_role':principal.role,**body},sort_keys=True)))

    def _issue(self,subject,role,source,assignment=None,epoch=None):
        principal=Principal(subject,role,source,secrets.token_hex(24),assignment,epoch)
        self._principals[principal._handle]=principal
        return principal

    def authenticate(self,authorization):
        subject=identify(authorization,self._hashes)
        if subject is None:
            raise Denied('UNVERIFIED_PRINCIPAL',401)
        role=MAP.get(subject)
        assignment=epoch=None
        if subject.startswith('SUBAGENT:'):
            with self.transaction() as db:
                binding=db.execute('SELECT * FROM cc_principal_bindings WHERE subject=?',(subject,)).fetchone()
                if not binding or binding['role']!='SUBAGENT' or binding['source']!='CONTROLLER_SUBAGENT_BINDING':
                    raise Denied('SUBAGENT_BINDING_REQUIRED',403)
                task=db.execute('SELECT epoch,status FROM cc_assignments WHERE id=?',(binding['assignment'],)).fetchone()
                if not task or task['epoch']!=binding['epoch'] or task['status'] not in ('TASK_ASSIGNED','DEVELOPMENT','SELF_QA'):
                    raise Denied('STALE_SUBAGENT_BINDING',403)
                role='SUBAGENT';assignment=binding['assignment'];epoch=binding['epoch']
        if role not in ROLES:
            raise Denied('UNKNOWN_PRINCIPAL_ROLE',403)
        with self.transaction() as db:
            if role!='SUBAGENT':
                db.execute('INSERT OR REPLACE INTO cc_principal_bindings VALUES(?,?,?,?,?,?)',
                    (subject,role,'REGISTRY_BEARER',None,None,_now().isoformat()))
        return self._issue(subject,role,'REGISTRY_BEARER',assignment,epoch)

    def fixture_principal(self,subject,role):
        """Tests only; this can never grant a production approval or principal."""
        if self.environment!='TEST_FIXTURE' or role not in ROLES:
            raise Denied('TEST_FIXTURE_ONLY',403)
        if not isinstance(subject,str) or not re.fullmatch(r'[A-Za-z0-9:_-]{1,80}',subject):
            raise ValueError('Invalid fixture subject')
        return self._issue(subject,role,'TEST_FIXTURE')

    def principal(self,principal):
        if not isinstance(principal,Principal) or self._principals.get(principal._handle) is not principal:
            raise Denied('UNVERIFIED_PRINCIPAL',403)
        if principal.source=='TEST_FIXTURE' and self.environment!='TEST_FIXTURE':
            raise Denied('TEST_FIXTURE_ONLY',403)
        return principal

    def _authorize(self,db,principal,action,scope=None):
        self.principal(principal)
        if action not in ACTIONS:
            raise Denied('UNKNOWN_ACTION',403)
        risk,roles=ACTIONS[action]
        if principal.role not in roles:
            raise Denied('ROLE_DENIED',403)
        scopes=_scopes(scope) if scope is not None else None
        if principal.role in ('ANTI_WORKER','SUBAGENT') and action in ('source.read','source.write'):
            if scopes is None:
                raise Denied('EXPLICIT_WORKER_SCOPE_REQUIRED',403)
            if principal.role=='ANTI_WORKER':
                tasks=db.execute("SELECT * FROM cc_assignments WHERE owner=? AND status IN ('TASK_ASSIGNED','DEVELOPMENT','SELF_QA')",(principal.subject,)).fetchall()
                allowed=[path for task in tasks for path in json.loads(task['allowed'])]
                forbidden=[path for task in tasks for path in json.loads(task['forbidden'])+(json.loads(task['readonly']) if action=='source.write' else [])]
            else:
                child=db.execute('SELECT * FROM cc_subagents WHERE id=?',(principal.subject.partition(':')[2],)).fetchone()
                task=db.execute('SELECT * FROM cc_assignments WHERE id=?',(principal.assignment,)).fetchone()
                if not child or child['status']!='AUTHORIZED' or not task or task['epoch']!=principal.epoch or task['status'] not in ('TASK_ASSIGNED','DEVELOPMENT','SELF_QA'):
                    raise Denied('STALE_SUBAGENT_BINDING',403)
                tool='write_source' if action=='source.write' else 'read_source'
                if tool not in json.loads(child['tools']):
                    raise Denied('SUBAGENT_TOOL_DENIED',403)
                allowed=json.loads(child['allowed']);forbidden=json.loads(task['forbidden'])+(json.loads(task['readonly']) if action=='source.write' else [])
            if any(not any(path==base or path.startswith(base+'/') for base in allowed) for path in scopes):
                raise Denied('CANT_EDIT_SCOPE',403)
            if any(path==base or path.startswith(base+'/') or base.startswith(path+'/') for path in scopes for base in forbidden):
                raise Denied('CANT_EDIT_PROTECTED_SCOPE',403)
        return {'risk':risk,'role':principal.role,'subject':principal.subject,
                'isolation_level':'LOGICAL_ONLY','production_trusted':False}

    def authorize(self,principal,action,scope=None):
        with self.transaction() as db:
            return self._authorize(db,principal,action,scope)

    def bind_subagent(self,principal,subagent_id):
        self.principal(principal)
        if principal.role!='ANTI_WORKER':
            raise Denied('WORKER_PARENT_REQUIRED',403)
        with self.transaction() as db:
            child=db.execute('SELECT * FROM cc_subagents WHERE id=?',(subagent_id,)).fetchone()
            if not child or child['owner']!=principal.subject:
                raise Denied('OWNED_SUBAGENT_REQUIRED',403)
            task=db.execute('SELECT * FROM cc_assignments WHERE id=?',(child['parent'],)).fetchone()
            if not task or task['owner']!=principal.subject or task['status'] not in ('TASK_ASSIGNED','DEVELOPMENT','SELF_QA'):
                raise Denied('ACTIVE_PARENT_REQUIRED',403)
            subject='SUBAGENT:'+subagent_id
            db.execute('INSERT OR REPLACE INTO cc_principal_bindings VALUES(?,?,?,?,?,?)',
                (subject,'SUBAGENT','CONTROLLER_SUBAGENT_BINDING',task['id'],task['epoch'],_now().isoformat()))
            self._event(db,principal,'SUBAGENT_PRINCIPAL_BOUND',subject,{'assignment':task['id'],'epoch':task['epoch']})
        return {'subject':subject,'role':'SUBAGENT','credential_issued':False}

    def publish_knowledge(self,principal,key,content,provenance):
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',key):
            raise ValueError('Invalid knowledge key')
        if not isinstance(content,dict) or not content or len(json.dumps(content))>32000:
            raise ValueError('Bounded knowledge document required')
        if not isinstance(provenance,dict) or not isinstance(provenance.get('source_ref'),str) or not provenance['source_ref'] or not HEX64.fullmatch(provenance.get('source_sha256','')):
            raise ValueError('Explicit source reference and digest required')
        if provenance.get('kind') not in ('OPERATOR_ASSERTION','LOCAL_QA_EVIDENCE','TEST_FIXTURE'):
            raise Denied('PROTECTED_KNOWLEDGE_VERIFIER_UNAVAILABLE',423)
        if provenance['kind']=='TEST_FIXTURE' and self.environment!='TEST_FIXTURE':
            raise Denied('TEST_FIXTURE_ONLY',403)
        stored={**provenance,'verification':'SOURCE_REFERENCE_ASSERTED_NOT_PROTECTED'}
        with self.transaction() as db:
            self._authorize(db,principal,'knowledge.write')
            previous=db.execute('SELECT version,hash FROM cc_knowledge_versions WHERE key=? ORDER BY version DESC LIMIT 1',(key,)).fetchone()
            version=previous['version']+1 if previous else 1
            previous_hash=previous['hash'] if previous else None
            body={'key':key,'version':version,'previous_hash':previous_hash,'content':content,
                  'provenance':stored,'author':principal.subject}
            hashed=digest(body)
            db.execute('INSERT INTO cc_knowledge_versions VALUES(?,?,?,?,?,?,?,?)',
                (key,version,hashed,previous_hash,json.dumps(content,sort_keys=True),json.dumps(stored,sort_keys=True),principal.subject,_now().isoformat()))
            self._event(db,principal,'KNOWLEDGE_VERSION_PUBLISHED',key,{'version':version,'hash':hashed})
        return {'key':key,'version':version,'hash':hashed,'previous_hash':previous_hash,'production_trusted':False}

    def knowledge_history(self,principal,key):
        with self.transaction() as db:
            self._authorize(db,principal,'knowledge.read')
            rows=db.execute('SELECT * FROM cc_knowledge_versions WHERE key=? ORDER BY version',(key,)).fetchall()
            result=[];previous=None
            for index,row in enumerate(rows,1):
                item=dict(row);item['content']=json.loads(item['content']);item['provenance']=json.loads(item['provenance'])
                body={name:item[name] for name in ('key','version','previous_hash','content','provenance','author')}
                if item['version']!=index or item['previous_hash']!=previous or digest(body)!=item['hash']:
                    raise Denied('KNOWLEDGE_TAMPERED',409)
                result.append(item);previous=item['hash']
            return result

    def request_approval(self,principal,mission,action,scope,candidate_sha,expires_at,assignment=None):
        self.principal(principal)
        if principal.role=='READ_ONLY_OBSERVER':
            raise Denied('READ_ONLY_PRINCIPAL',403)
        if action not in ACTIONS:
            raise Denied('UNKNOWN_ACTION',403)
        scopes=_scopes(scope);expiry=_time(expires_at);risk=ACTIONS[action][0]
        maximum=timedelta(minutes=15) if risk=='CRITICAL' else timedelta(hours=24)
        if expiry<=_now() or expiry-_now()>maximum:
            raise ValueError('Future bounded approval expiry required')
        if not isinstance(candidate_sha,str) or not HEX40.fullmatch(candidate_sha):
            raise ValueError('Immutable candidate SHA required')
        binding={'mission':mission,'assignment':assignment,'action':action,'actor':principal.subject,
                 'scope':scopes,'candidate_sha':candidate_sha,'risk':risk,'expires_at':expiry.isoformat()}
        hashed=digest(binding);request=digest({'binding':binding,'environment':self.environment})
        kind={'merge':'MERGE_APPROVAL','release':'RELEASE_APPROVAL','contract.change':'CONTRACT_CHANGE'}.get(action,'PERMISSION_REQUIRED')
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM cc_missions WHERE id=?',(mission,)).fetchone():
                raise Denied('MISSION_REQUIRED',404)
            if principal.role in ('ANTI_WORKER','SUBAGENT'):
                if not assignment:
                    raise Denied('OWNED_ASSIGNMENT_REQUIRED',403)
                task=db.execute('SELECT * FROM cc_assignments WHERE id=?',(assignment,)).fetchone()
                if not task or task['mission']!=mission or (principal.role=='ANTI_WORKER' and task['owner']!=principal.subject) or (principal.role=='SUBAGENT' and principal.assignment!=assignment):
                    raise Denied('OWNED_ASSIGNMENT_REQUIRED',403)
            if assignment:
                task=db.execute('SELECT * FROM cc_assignments WHERE id=?',(assignment,)).fetchone()
                if not task or task['mission']!=mission: raise Denied('ASSIGNMENT_CONTEXT_REQUIRED',403)
                binding['ownership_epoch']=task['epoch'];binding['contract_hash']=task['contract_hash'];binding['workflow_revision']=task['revision']
                hashed=digest(binding);request=digest({'binding':binding,'environment':self.environment})
            existing=db.execute('SELECT gov_binding_digest FROM cc_human_requests WHERE id=?',(request,)).fetchone()
            if existing:
                if existing[0]!=hashed:
                    raise Denied('APPROVAL_BINDING_TAMPERED',409)
                return {'request_id':request,'binding_digest':hashed,'risk':risk,'idempotent':True,'production_trusted':False}
            db.execute('''INSERT INTO cc_human_requests(id,mission,assignment,target,kind,body,status,created,deadline,
                gov_binding,gov_binding_digest,gov_risk,gov_requester,gov_environment)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(request,mission,assignment,'OWNER',kind,
                'Bound governance approval request','PENDING',_now().isoformat(),expiry.isoformat(),
                json.dumps(binding,sort_keys=True),hashed,risk,principal.subject,self.environment))
            self._event(db,principal,'GOV_APPROVAL_REQUESTED',request,{'binding_digest':hashed,'risk':risk,'production_trusted':False})
        return {'request_id':request,'binding_digest':hashed,'risk':risk,'idempotent':False,'production_trusted':False}

    def _approval(self,db,request):
        row=db.execute('SELECT * FROM cc_human_requests WHERE id=?',(request,)).fetchone()
        if not row or not row['gov_binding']:
            raise Denied('BOUND_GOVERNANCE_REQUEST_REQUIRED',404)
        binding=json.loads(row['gov_binding'])
        if (digest(binding)!=row['gov_binding_digest'] or
                digest({'binding':binding,'environment':row['gov_environment']})!=row['id'] or
                binding['actor']!=row['gov_requester'] or binding['risk']!=row['gov_risk'] or
                binding['expires_at']!=row['deadline'] or binding['mission']!=row['mission'] or
                binding['assignment']!=row['assignment'] or binding['risk']!=ACTIONS.get(binding['action'],(None,))[0]):
            raise Denied('APPROVAL_BINDING_TAMPERED',409)
        if _time(row['deadline'])<=_now():
            raise Denied('APPROVAL_EXPIRED',409)
        return row,binding

    def approve(self,principal,request):
        self.principal(principal)
        if principal.role!='OWNER':
            raise Denied('OWNER_REQUIRED',403)
        # No protected attestation backend exists in this distribution. Neither a
        # Boolean, response field nor callback can switch production trust on.
        if self.environment!='TEST_FIXTURE':
            raise Denied('PROTECTED_OWNER_ATTESTATION_UNAVAILABLE',423)
        with self.transaction() as db:
            row,binding=self._approval(db,request)
            if row['gov_environment']!='TEST_FIXTURE':
                raise Denied('PRODUCTION_APPROVAL_BLOCKED',423)
            if row['gov_requester']==principal.subject:
                raise Denied('SELF_APPROVAL_DENIED',403)
            if row['status']!='PENDING' or row['gov_use_count']!=0:
                raise Denied('APPROVAL_ALREADY_DECIDED',409)
            response={'decision':'APPROVE','provenance':'TEST_FIXTURE','production_trusted':False,
                      'binding_digest':row['gov_binding_digest']}
            db.execute("UPDATE cc_human_requests SET status='FIXTURE_APPROVED',response=?,decided_at=?,gov_decision_by=? WHERE id=?",
                (json.dumps(response,sort_keys=True),_now().isoformat(),principal.subject,request))
            self._event(db,principal,'GOV_APPROVAL_FIXTURE_APPROVED',request,response)
        return {'status':'FIXTURE_APPROVED','production_trusted':False,'binding_digest':digest(binding)}

    def consume_approval(self,principal,request,action,scope,candidate_sha):
        self.principal(principal)
        if self.environment!='TEST_FIXTURE':
            raise Denied('PROTECTED_OWNER_ATTESTATION_UNAVAILABLE',423)
        with self.transaction() as db:
            self._authorize(db,principal,action,scope)
            row,binding=self._approval(db,request)
            if row['gov_environment']!='TEST_FIXTURE' or row['status']!='FIXTURE_APPROVED' or row['gov_use_count']!=0:
                raise Denied('APPROVAL_NOT_AVAILABLE_OR_REPLAY',409)
            if binding.get('assignment'):
                current=db.execute('SELECT epoch,contract_hash,revision FROM cc_assignments WHERE id=?',(binding['assignment'],)).fetchone()
                if not current or current['epoch']!=binding.get('ownership_epoch') or current['contract_hash']!=binding.get('contract_hash') or current['revision']!=binding.get('workflow_revision'):
                    raise Denied('STALE_APPROVAL_OWNERSHIP_CONTRACT',409)
            if binding['actor']!=principal.subject or binding['action']!=action or binding['scope']!=_scopes(scope) or binding['candidate_sha']!=candidate_sha:
                raise Denied('APPROVAL_ACTION_BINDING_MISMATCH',403)
            response=json.loads(row['response'])
            if response!={'decision':'APPROVE','provenance':'TEST_FIXTURE','production_trusted':False,'binding_digest':row['gov_binding_digest']} or not row['gov_decision_by']:
                raise Denied('APPROVAL_DECISION_TAMPERED',409)
            db.execute("UPDATE cc_human_requests SET status='CONSUMED',gov_use_count=1,gov_consumed_at=? WHERE id=? AND gov_use_count=0",
                (_now().isoformat(),request))
            self._event(db,principal,'GOV_APPROVAL_CONSUMED',request,{'binding_digest':row['gov_binding_digest'],'production_trusted':False})
        return {'status':'AUTHORIZED_TEST_FIXTURE','production_trusted':False,'request_id':request}

    def approval_history(self,principal,request):
        self.principal(principal)
        with self.transaction() as db:
            row=db.execute('SELECT gov_requester FROM cc_human_requests WHERE id=?',(request,)).fetchone()
            if not row:
                raise Denied('REQUEST_NOT_FOUND',404)
            if principal.role not in ('OWNER','CODEX_LEAD','READ_ONLY_OBSERVER') and row[0]!=principal.subject:
                raise Denied('ROLE_DENIED',403)
            return [dict(item) for item in db.execute("SELECT at,actor,kind,target,body FROM cc_events WHERE target=? AND kind LIKE 'GOV_APPROVAL_%' ORDER BY id",(request,))]
