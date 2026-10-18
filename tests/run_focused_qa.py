"""Distinct local audit passes. External/host acceptance is never inferred."""
import argparse,datetime,json,subprocess,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PY=[sys.executable,'-X','utf8','-m','unittest','-v']
GROUPS={
 '01':[['git','fsck','--full'],['git','diff','--check'],PY+['tests.test_human_requests']],
 '02':[PY+['tests.test_governance','tests.test_private_acl','tests.test_client_identity']],
 '03':[PY+['tests.test_trust_vault','tests.test_scope_policy']],
 '04':[PY+['tests.test_scope_gate','tests.test_legacy_boundaries','tests.test_worktree_manager']],
 '05':[PY+['tests.test_dispatch_delivery','tests.test_orchestration.OrchestrationTests.test_atomic_wave_idempotent_retry_and_restart','tests.test_orchestration.OrchestrationTests.test_circular_dependencies_rollback_parent_and_children','tests.test_orchestration.OrchestrationTests.test_provider_completion_and_early_child_never_complete_wave','tests.test_orchestration.OrchestrationTests.test_wrong_owner_steering_and_durable_ack','tests.test_orchestration.OrchestrationTests.test_subagent_cannot_expand_parent_tools_or_scope']],
 '06':[PY+['tests.test_transaction_sync']],
 '07':[[sys.executable,'-X','utf8',str(ROOT/'tests/e2e_local_harness.py'),'--out','FEEDBACK_OUT'],PY+['tests.test_dispatch_delivery.DeliveryTests.test_normalized_root_cause_freezes_with_changing_defect_ids']],
 '08':[[sys.executable,'-X','utf8',str(ROOT/'tests/process_recovery_drill.py')],PY+['tests.test_recovery_manager','tests.test_mission_recovery']],
}

def run(number,out):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    before_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    before_dirty=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
    rows=[]
    for index,argv in enumerate(GROUPS[number],1):
        argv=[str(out/'feedback-harness') if value=='FEEDBACK_OUT' else value for value in argv]
        before=datetime.datetime.now(datetime.timezone.utc).isoformat()
        p=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=240)
        log=out/f'QA-{number}-{index}.txt';log.write_bytes(p.stdout+b'\n'+p.stderr)
        rows.append({'argv':argv,'cwd':str(ROOT),'exit_code':p.returncode,'started_at':before,'ended_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'log':log.name})
    result={'pass_id':'QA-'+number,'execution_status':'PASS' if all(r['exit_code']==0 for r in rows) else 'FAIL','provenance':'LOCAL_WINDOWS_NOT_PRODUCTION_TRUSTED','commands':rows,'native_antigravity':'NOT_EXECUTED','revit':'NOT_EXECUTED','hosted_ci':'NOT_EXECUTED'}
    result['code_sha']=before_sha;result['source_dirty_before']=bool(before_dirty)
    result['source_changed_during_execution']=(before_sha!=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip() or before_dirty!=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True))
    if result['source_changed_during_execution']:result['execution_status']='FAIL_SOURCE_CHANGED'
    (out/f'QA-{number}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'pass_id':result['pass_id'],'execution_status':result['execution_status']}))
    return 0 if result['execution_status']=='PASS' else 1
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pass-number',choices=GROUPS,required=True);p.add_argument('--out',required=True);a=p.parse_args();raise SystemExit(run(a.pass_number,a.out))
