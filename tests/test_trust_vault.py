import copy
from datetime import datetime,timezone,timedelta
import tempfile
from pathlib import Path
import unittest
import subprocess
from trust_vault import digest,file_digest,verify_evidence

class TrustVaultTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.repo=self.root/'repo';self.repo.mkdir()
        self.git('init','-q');self.git('config','user.name','Trust test')
        self.git('config','user.email','trust@example.test')
        (self.repo/'README.md').write_text('base\n')
        self.git('add','.');self.git('commit','-qm','base')
        self.base=self.git('rev-parse','HEAD')
        (self.repo/'module').mkdir();(self.repo/'module'/'a').write_text('candidate\n')
        self.git('add','.');self.git('commit','-qm','candidate')
        self.head=self.git('rev-parse','HEAD');self.tree=self.git('rev-parse','HEAD^{tree}')
        for name in ('profile','suite','artifact'): (self.root/name).write_text(name)
        self.commands=[{'argv':['python','tests.py'],'exit':0}]
        expected=dict(mission='M',task='T',iteration=1,identity='ANTI-01',epoch=3,repo='owner/repo',
                      contract_hash='c'*64,workflow_revision='d'*64,verifier_identity='LOCAL_FIXTURE_RUNNER',approval_status='NOT_APPROVED',
                      base_sha=self.base,candidate_sha=self.head,tree_sha=self.tree,paths=['module/a'],
                      profile_digest=file_digest(self.root/'profile'),suite_digest=file_digest(self.root/'suite'))
        self.policy={'expected':expected,'commands_digest':digest(self.commands),'profile_path':str(self.root/'profile'),
                     'suite_path':str(self.root/'suite'),'max_age_seconds':60,'repo_path':str(self.repo),
                     'scope':'module','allowed_paths':['module'],'protected_paths':['secrets'],
                     'ci':{'repo':'owner/repo','workflow':'protected-ci.yml','workflow_sha':'d'*40,'issuer':'github','required_checks':['full-qa']}}
        self.evidence={**expected,'commands':self.commands,'artifacts':[{'name':'log','path':str(self.root/'artifact'),'sha256':file_digest(self.root/'artifact')}],
                       'timestamp':datetime.now(timezone.utc).isoformat(),'provenance':'LOCAL_SAME_USER','trust_policy_digest':digest(self.policy)}
    def check(self,**kw): return verify_evidence(self.evidence,self.policy,**kw)
    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.repo),*args],text=True,stderr=subprocess.PIPE).strip()
    def rebind(self,**values):
        self.evidence.update(values);self.policy['expected'].update(values)
        self.evidence['trust_policy_digest']=digest(self.policy)
    def test_local_never_production_trusted(self):
        r=self.check();self.assertEqual(r['status'],'LOCAL_VERIFIED');self.assertFalse(r['production_trusted'])
        self.assertTrue(r['source_verification']['commits_verified'])
        self.assertEqual(r['command_evidence'],'CONSISTENCY_ONLY_NOT_EXECUTION_PROOF')
    def test_nonexistent_candidate_with_matching_policy_rejected(self):
        self.rebind(candidate_sha='a'*40)
        self.assertEqual(self.check()['status'],'REJECTED')
    def test_tree_mismatch_with_matching_policy_rejected(self):
        self.rebind(tree_sha=self.git('rev-parse',self.base+'^{tree}'))
        self.assertEqual(self.check()['status'],'REJECTED')
    def test_fabricated_changed_paths_with_matching_policy_rejected(self):
        self.rebind(paths=['module/fabricated'])
        self.assertEqual(self.check()['status'],'REJECTED')
    def test_nonancestor_baseline_rejected(self):
        self.git('checkout','--orphan','unrelated')
        self.git('commit','-qm','unrelated same tree')
        self.rebind(candidate_sha=self.git('rev-parse','HEAD'))
        self.assertEqual(self.check()['status'],'REJECTED')
    def test_missing_local_checkout_for_remote_repo_rejected(self):
        del self.policy['repo_path'];self.evidence['trust_policy_digest']=digest(self.policy)
        self.assertEqual(self.check()['status'],'REJECTED')
    def test_scope_policy_restricts_actual_source_paths(self):
        self.policy['allowed_paths']=['other'];self.evidence['trust_policy_digest']=digest(self.policy)
        self.assertEqual(self.check()['status'],'REJECTED')
    def test_subdirectory_is_not_repository_root(self):
        self.policy['repo_path']=str(self.repo/'module');self.evidence['trust_policy_digest']=digest(self.policy)
        self.assertEqual(self.check()['status'],'REJECTED')
    def test_contract_revision_verifier_and_approval_are_bound(self):
        for key in ('contract_hash','workflow_revision','verifier_identity','approval_status'):
            original=self.evidence[key];self.evidence[key]='different'
            self.assertEqual(self.check()['status'],'REJECTED')
            self.evidence[key]=original

    def test_local_result_cannot_be_rebound_to_approved(self):
        self.rebind(approval_status='APPROVED')
        self.assertEqual(self.check()['status'],'REJECTED')

    def test_missing_fields_rejected(self):
        del self.evidence['epoch'];self.assertEqual(self.check()['status'],'REJECTED')
    def test_binding_epoch_mismatch(self):
        self.evidence['epoch']=2;self.assertEqual(self.check()['status'],'REJECTED')
    def test_stale(self):
        self.evidence['timestamp']=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat();self.assertEqual(self.check()['status'],'REJECTED')
    def test_config_and_artifact_tampering(self):
        for name in ('profile','suite','artifact'):
            with self.subTest(name=name):
                p=self.root/name;old=p.read_text();p.write_text('tampered')
                self.assertEqual(self.check()['status'],'REJECTED');p.write_text(old)
    def test_nonexistent_artifact(self):
        (self.root/'artifact').unlink();self.assertEqual(self.check()['status'],'REJECTED')
    def test_changed_policy(self):
        self.policy['max_age_seconds']=99999;self.assertEqual(self.check()['status'],'REJECTED')
    def test_command_failure_or_substitution(self):
        self.evidence['commands']=[{'argv':['echo','fake'],'exit':0}];self.assertEqual(self.check()['status'],'REJECTED')
    def test_worker_pass_boolean_not_accepted(self):
        self.evidence['provenance']='PROTECTED_CI';self.evidence['trusted']=True
        self.assertEqual(self.check()['status'],'BLOCKED')
    def adapter(self):
        self.evidence['provenance']='PROTECTED_CI';self.evidence['run_id']='123'
        response={'repo':'owner/repo','workflow':'protected-ci.yml','workflow_sha':'d'*40,'issuer':'github','run_id':'123',
                  'head_sha':self.head,'conclusion':'success','status':'completed','evidence_digest':digest(self.evidence),
                  'policy_digest':digest(self.policy),'artifacts':{'log':self.evidence['artifacts'][0]['sha256']},'checks':{'full-qa':'success'}}
        def synthetic_fetch(repo,run_id): return copy.deepcopy(response)
        synthetic_fetch.synthetic=True
        return synthetic_fetch,response
    def test_synthetic_ci_never_production_trusted(self):
        adapter,_=self.adapter();r=self.check(ci_fetch=adapter)
        self.assertEqual(r['status'],'BLOCKED');self.assertFalse(r['production_trusted'])
    def test_matching_fake_cannot_enable_production_by_clearing_synthetic_flag(self):
        adapter,response=self.adapter()
        adapter.synthetic=False
        response['synthetic']=False
        r=self.check(ci_fetch=adapter)
        self.assertEqual(r['status'],'BLOCKED')
        self.assertFalse(r['production_trusted'])
        self.assertIn('PROTECTED_TRUST_BOUNDARY_NOT_CONFIGURED',r['errors'])
    def test_missing_synthetic_attribute_cannot_enable_production(self):
        adapter,_=self.adapter()
        del adapter.synthetic
        r=self.check(ci_fetch=adapter)
        self.assertEqual(r['status'],'BLOCKED')
        self.assertFalse(r['production_trusted'])
    def test_mismatched_remote_sha_and_workflow_rejected(self):
        for field in ('head_sha','workflow','workflow_sha','evidence_digest','policy_digest','artifacts'):
            with self.subTest(field=field):
                adapter,response=self.adapter();response[field]='wrong'
                self.assertEqual(self.check(ci_fetch=adapter)['status'],'REJECTED')

if __name__=='__main__':unittest.main()
