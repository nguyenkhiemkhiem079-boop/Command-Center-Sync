"""Local transaction rehearsal. Protected Central writes require an external backend.

Injected adapters/verifiers belong to the trusted controller. Same-user Python code
cannot establish that trust; only disposable refs may be changed by this module.
"""
import json
from pathlib import Path
import subprocess
import tempfile
import uuid
import copy
import hashlib
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from ci_scope_gate import verify, within
from registry import clean_scope
from trust_vault import digest

class TransactionSync:
    def __init__(self,repo,central_ref,expected_base,candidates,checkpoint,scope_policy=None,journal_db=None):
        self.repo=Path(repo).resolve(); self.central_ref=central_ref; self.expected_base=expected_base
        self.candidates=candidates; self.checkpoint=checkpoint; self.scope_policy=scope_policy or {}
        self.state='NEW'; self.history=[]; self.workspace=None; self.integration_sha=None
        self.branch='ktool-txn-'+uuid.uuid4().hex; self.validated_digest=None
        self.transaction_id=uuid.uuid4().hex;self.approval_binding=None;self._version=0
        common=Path(self.git('rev-parse','--git-common-dir'))
        if not common.is_absolute(): common=self.repo/common
        self.journal_db=Path(journal_db).resolve() if journal_db else common.resolve()/'ktool-sync-journal.sqlite3'
        self.journal_db.parent.mkdir(parents=True,exist_ok=True)
        self._inputs=self._input_binding()
        self._initialize_journal()
        self.record('NEW')

    def _input_binding(self):
        return copy.deepcopy({'repo':str(self.repo),'central_ref':self.central_ref,
            'expected_base':self.expected_base,'candidates':self.candidates,
            'checkpoint':self.checkpoint,'scope_policy':self.scope_policy,'branch':self.branch})

    def _initialize_journal(self):
        with closing(sqlite3.connect(self.journal_db)) as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS cc_sync_transactions(
              id TEXT PRIMARY KEY,state TEXT NOT NULL,version INTEGER NOT NULL,
              candidate_digest TEXT NOT NULL,policy_digest TEXT NOT NULL,
              workspace TEXT,integration_sha TEXT,approval_binding TEXT,
              immutable_digest TEXT NOT NULL,payload_digest TEXT NOT NULL,
              payload TEXT NOT NULL,updated TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cc_sync_history(
              transaction_id TEXT NOT NULL,version INTEGER NOT NULL,state TEXT NOT NULL,
              payload_digest TEXT NOT NULL,at TEXT NOT NULL,payload TEXT NOT NULL,
              PRIMARY KEY(transaction_id,version));
            ''')
            columns={row[1] for row in db.execute('PRAGMA table_info(cc_sync_history)')}
            if 'payload' not in columns:
                db.execute("ALTER TABLE cc_sync_history ADD COLUMN payload TEXT NOT NULL DEFAULT ''")
                db.commit()

    def _payload(self):
        return {'transaction_id':self.transaction_id,'inputs':self._inputs,
            'state':self.state,'history':self.history,'workspace':str(self.workspace) if self.workspace else None,
            'integration_sha':self.integration_sha,'validated_digest':self.validated_digest,
            'approval_binding':self.approval_binding,'version':self._version+1}

    @classmethod
    def load(cls,journal_db,transaction_id):
        """Load a consistent journal. Hashes detect corruption, not same-user forgery."""
        path=Path(journal_db).resolve(strict=True)
        with closing(sqlite3.connect(path)) as db:
            db.row_factory=sqlite3.Row
            row=db.execute('SELECT * FROM cc_sync_transactions WHERE id=?',(transaction_id,)).fetchone()
            if row is None: raise ValueError('TRANSACTION_NOT_FOUND')
            payload=json.loads(row['payload'])
            entries=db.execute('SELECT version,state,payload_digest,payload FROM cc_sync_history WHERE transaction_id=? ORDER BY version',(transaction_id,)).fetchall()
        if (digest(payload)!=row['payload_digest'] or digest(payload['inputs'])!=row['immutable_digest']
                or payload['version']!=row['version'] or payload['transaction_id']!=transaction_id
                or payload['state']!=row['state'] or len(entries)!=row['version']
                or [entry['version'] for entry in entries]!=list(range(1,row['version']+1))
                or entries[-1]['payload_digest']!=row['payload_digest']
                or any(not entry['payload'] or digest(json.loads(entry['payload']))!=entry['payload_digest']
                       or json.loads(entry['payload'])['version']!=entry['version']
                       or json.loads(entry['payload'])['state']!=entry['state'] for entry in entries)
                or [entry['state'] for entry in entries]!=[entry['state'] for entry in payload['history']]
                or digest(payload['inputs']['candidates'])!=row['candidate_digest']
                or digest(payload['inputs']['scope_policy'])!=row['policy_digest']
                or payload['workspace']!=row['workspace'] or payload['integration_sha']!=row['integration_sha']
                or json.loads(row['approval_binding'])!=payload['approval_binding']):
            raise ValueError('TRANSACTION_JOURNAL_TAMPERED')
        self=cls.__new__(cls)
        inputs=payload['inputs'];self._inputs=inputs
        self.repo=Path(inputs['repo']);self.central_ref=inputs['central_ref'];self.expected_base=inputs['expected_base']
        self.candidates=copy.deepcopy(inputs['candidates']);self.checkpoint=inputs['checkpoint'];self.scope_policy=copy.deepcopy(inputs['scope_policy'])
        self.branch=inputs['branch'];self.transaction_id=transaction_id;self.journal_db=path
        self.state=payload['state'];self.history=payload['history'];self._version=payload['version']
        self.workspace=Path(payload['workspace']) if payload['workspace'] else None
        self.integration_sha=payload['integration_sha'];self.validated_digest=payload['validated_digest']
        self.approval_binding=payload['approval_binding']
        # Never replay worktree creation, cherry-picks, QA commands or a ref write.
        if self.state in ('INTEGRATION_QA_IN_PROGRESS','COMMIT_IN_PROGRESS'):
            self.abort('INTERRUPTED_NON_IDEMPOTENT_OPERATION_PRESERVE_CHECKPOINT_RETURN_TO_OWNER')
        return self

    @classmethod
    def recover(cls,journal_db,transaction_id):
        return cls.load(journal_db,transaction_id)
    def git(self,*args,cwd=None):
        result=subprocess.run(['git',*args],cwd=cwd or self.repo,capture_output=True,text=True,check=False)
        if result.returncode: raise ValueError('GIT_FAILED '+ ' '.join(args[:2])+': '+result.stderr[-1000:])
        return result.stdout.strip()
    def record(self,state,**evidence):
        old_state=self.state;old_history=list(self.history)
        self.state=state; self.history.append({'state':state,**evidence})
        payload=self._payload();payload_hash=digest(payload);instant=datetime.now(timezone.utc).isoformat()
        try:
            with closing(sqlite3.connect(self.journal_db,timeout=15,isolation_level=None)) as db:
                db.execute('BEGIN IMMEDIATE')
                current=db.execute('SELECT version FROM cc_sync_transactions WHERE id=?',(self.transaction_id,)).fetchone()
                if (current[0] if current else 0)!=self._version:
                    raise ValueError('TRANSACTION_JOURNAL_VERSION_CONFLICT')
                db.execute('''INSERT INTO cc_sync_transactions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET state=excluded.state,version=excluded.version,
                    candidate_digest=excluded.candidate_digest,policy_digest=excluded.policy_digest,
                    workspace=excluded.workspace,integration_sha=excluded.integration_sha,
                    approval_binding=excluded.approval_binding,immutable_digest=excluded.immutable_digest,
                    payload_digest=excluded.payload_digest,payload=excluded.payload,updated=excluded.updated''',
                    (self.transaction_id,state,self._version+1,digest(self._inputs['candidates']),digest(self._inputs['scope_policy']),
                     payload['workspace'],self.integration_sha,json.dumps(self.approval_binding),digest(self._inputs),
                     payload_hash,json.dumps(payload,sort_keys=True),instant))
                db.execute('INSERT INTO cc_sync_history(transaction_id,version,state,payload_digest,at,payload) VALUES(?,?,?,?,?,?)',
                           (self.transaction_id,self._version+1,state,payload_hash,instant,json.dumps(payload,sort_keys=True)))
                db.execute('COMMIT')
        except Exception:
            self.state=old_state;self.history=old_history
            raise
        self._version+=1
        return {'state':state,**evidence}
    def abort(self,reason):
        return self.record('ABORT',reason=str(reason),checkpoint=self.checkpoint,
                           return_to_owner=True,worker_branches_preserved=True,workspace=str(self.workspace))
    def prepare(self):
        if self.state!='NEW': raise ValueError('INVALID_TRANSITION')
        try:
            if not self.checkpoint: raise ValueError('CHECKPOINT_REQUIRED')
            if not self.candidates: raise ValueError('CANDIDATES_REQUIRED')
            if self.git('rev-parse',self.central_ref)!=self.expected_base: raise ValueError('CENTRAL_ADVANCED')
            self.git('cat-file','-e',self.expected_base+'^{commit}')
            self._inputs=self._input_binding()
            return self.record('PREPARE',base=self.expected_base,checkpoint=self.checkpoint)
        except Exception as error: return self.abort(error)
    def validate(self):
        if self.state!='PREPARE': raise ValueError('INVALID_TRANSITION')
        try:
            if self._input_binding()!=self._inputs: raise ValueError('TRANSACTION_INPUTS_CHANGED')
            scopes=[]; evidence=[]
            for candidate in self.candidates:
                scope=clean_scope(candidate['scope'])
                if any(within(scope,s) or within(s,scope) for s in scopes): raise ValueError('DUPLICATE_OWNERSHIP')
                scopes.append(scope)
                # Controller supplies scopes and immutable candidates, never worker-edited policy files.
                if candidate.get('base_sha',self.expected_base)!=self.expected_base: raise ValueError('BASE_MISMATCH')
                checked=verify(self.repo,self.expected_base,candidate['sha'],scope,
                               candidate.get('allowed_paths',[scope]),candidate.get('protected_paths',[]))
                if not checked['pass']: raise ValueError(json.dumps(checked['errors']))
                evidence.append(checked)
            self.validated_digest=digest(self.candidates)
            return self.record('VALIDATE',scope_evidence=evidence)
        except Exception as error: return self.abort(error)
    def integration_qa(self,commands):
        if self.state!='VALIDATE': raise ValueError('INVALID_TRANSITION')
        try:
            if self.validated_digest!=digest(self.candidates): raise ValueError('CANDIDATES_CHANGED')
            if self._input_binding()!=self._inputs: raise ValueError('TRANSACTION_INPUTS_CHANGED')
            if self.git('rev-parse',self.central_ref)!=self.expected_base: raise ValueError('CENTRAL_ADVANCED')
            if not isinstance(commands,list) or not commands: raise ValueError('FULL_QA_COMMANDS_REQUIRED')
            # Explicit controller manifest is required; prevent accidental tiny substitute QA.
            if self.scope_policy.get('qa_commands_digest')!=digest(commands): raise ValueError('TRUSTED_FULL_QA_MANIFEST_MISMATCH')
            parent=Path(tempfile.mkdtemp(prefix='ktool-integration-')); self.workspace=parent/'worktree'
            # Durable checkpoint precedes EVERY non-idempotent integration side effect.
            self.record('INTEGRATION_QA_IN_PROGRESS',checkpoint=self.checkpoint,
                        recovery_action='ABORT_PRESERVE_CHECKPOINT_RETURN_TO_OWNER')
            self.git('worktree','add','-q','-b',self.branch,str(self.workspace),self.expected_base)
            for candidate in self.candidates:
                commits=self.git('rev-list','--reverse',self.expected_base+'..'+candidate['sha']).splitlines()
                if not commits: raise ValueError('EMPTY_CANDIDATE')
                self.record('INTEGRATION_QA_IN_PROGRESS',operation='CHERRY_PICK',candidate_sha=candidate['sha'],
                            checkpoint=self.checkpoint,recovery_action='ABORT_PRESERVE_CHECKPOINT_RETURN_TO_OWNER')
                self.git('cherry-pick',*commits,cwd=self.workspace)
            self.integration_sha=self.git('rev-parse','HEAD',cwd=self.workspace)
            self.record('INTEGRATION_QA_IN_PROGRESS',operation='QA',integration_sha=self.integration_sha,
                        checkpoint=self.checkpoint,recovery_action='ABORT_PRESERVE_CHECKPOINT_RETURN_TO_OWNER')
            logs=[]
            for argv in commands:
                if not isinstance(argv,list) or not argv or not all(isinstance(x,str) and x for x in argv): raise ValueError('INVALID_QA_COMMAND')
                result=subprocess.run(argv,cwd=self.workspace,capture_output=True,text=True,timeout=300,check=False)
                # Durable controller journal stores output digests, never arbitrary
                # test output that could contain credentials or private text.
                logs.append({'argv':argv,'exit':result.returncode,
                    'stdout_sha256':hashlib.sha256(result.stdout.encode()).hexdigest(),
                    'stderr_sha256':hashlib.sha256(result.stderr.encode()).hexdigest()})
                if result.returncode: raise ValueError('INTEGRATION_QA_FAILED '+json.dumps(logs))
            if self.git('rev-parse','HEAD',cwd=self.workspace)!=self.integration_sha or self.git('status','--porcelain','--untracked-files=all',cwd=self.workspace):
                raise ValueError('QA_MUTATED_INTEGRATION')
            return self.record('INTEGRATION_QA',commands=logs,integration_sha=self.integration_sha,
                               full_qa_manifest_digest=digest(commands),trust='LOCAL_VERIFIED')
        except Exception as error: return self.abort(error)
    def request_approval(self):
        if self.state!='INTEGRATION_QA': raise ValueError('INVALID_TRANSITION')
        self.approval_binding={'central_ref':self.central_ref,'expected_base':self.expected_base,
                               'integration_sha':self.integration_sha,'candidates_digest':self.validated_digest,
                               'qa_digest':digest(self.history[-1])}
        return self.record('APPROVAL_PENDING',binding=self.approval_binding)
    def commit(self,approval=None,approval_verifier=None):
        if self.state!='APPROVAL_PENDING': raise ValueError('INVALID_TRANSITION')
        # This implementation has no production protected-principal write backend.
        if not self.central_ref.startswith('refs/ktool-disposable/'):
            return {'state':self.state,'status':'BLOCKED','reason':'PROTECTED_CENTRAL_BACKEND_UNAVAILABLE'}
        if approval is None or approval_verifier is None:
            return {'state':self.state,'status':'BLOCKED','reason':'GENUINE_OWNER_APPROVAL_REQUIRED'}
        try:
            proof=approval_verifier(approval,dict(self.approval_binding))
            if not isinstance(proof,dict) or proof.get('decision')!='APPROVE' or proof.get('principal_role')!='OWNER' or proof.get('binding_digest')!=digest(self.approval_binding):
                raise ValueError('OWNER_APPROVAL_INVALID')
            if proof.get('fixture') is not True: raise ValueError('DISPOSABLE_REF_REQUIRES_EXPLICIT_TEST_FIXTURE')
            if self.validated_digest!=digest(self.candidates): raise ValueError('CANDIDATES_CHANGED')
            if self._input_binding()!=self._inputs: raise ValueError('TRANSACTION_INPUTS_CHANGED')
            if self.git('rev-parse','HEAD',cwd=self.workspace)!=self.integration_sha or self.git('status','--porcelain','--untracked-files=all',cwd=self.workspace):
                raise ValueError('INTEGRATION_CHANGED_AFTER_QA')
            # Atomic compare-and-swap: no force push, no worker refs changed.
            self.record('COMMIT_IN_PROGRESS',binding_digest=digest(self.approval_binding),
                        recovery_action='ABORT_PRESERVE_CHECKPOINT_RETURN_TO_OWNER')
            self.git('update-ref',self.central_ref,self.integration_sha,self.expected_base)
            return self.record('COMMIT',integration_sha=self.integration_sha,trust='LOCAL_VERIFIED',production_trusted=False)
        except Exception as error: return self.abort(error)
