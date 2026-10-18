"""K-TOOL MCP stdio tools for CODEX and both independent Antigravity workers.

Each process pins an explicit identity and credential file; no shared-token fallback.
"""
from __future__ import annotations
import json
import argparse
import os
from pathlib import Path
import urllib.error
import urllib.request
from mcp.server.fastmcp import FastMCP

mcp=FastMCP('K-TOOL Worksharing Recovery v0.7')
PORT=os.environ.get('KTOOL_COORDINATOR_PORT','8876')
if not PORT.isdecimal() or not 1 <= int(PORT) <= 65535:
    raise RuntimeError('Invalid loopback coordinator port')
URL='http://127.0.0.1:'+PORT+'/rpc'

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # The coordinator never redirects. Keep bearer credentials on its endpoint.
        return None

_HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

_TOKEN = None
_IDENTITY = None

def configure(identity, token_path):
    global _TOKEN, _IDENTITY
    if identity not in ('CODEX', 'ANTI-01', 'ANTI-02') or not token_path:
        raise RuntimeError('Explicit identity and token path required')
    token = Path(token_path).read_text(encoding='utf-8').strip()
    if not token:
        raise RuntimeError('Missing client token')
    _TOKEN, _IDENTITY = token, identity
    try:
        result = _request('status')
        if not result.get('ok') or result.get('result', {}).get('actor') != identity:
            raise RuntimeError('Coordinator identity verification failed')
    except Exception:
        _TOKEN, _IDENTITY = None, None
        raise RuntimeError('Coordinator identity verification failed') from None

def _call(op, **args):
    if _TOKEN is None or _IDENTITY is None:
        raise RuntimeError('Adapter identity not verified')
    return _request(op, **args)

def _request(op,**args):
    req=urllib.request.Request(URL,data=json.dumps({'op':op,'args':args}).encode('utf-8'),method='POST',headers={
        'Authorization':'Bearer '+_TOKEN,'Content-Type':'application/json'})
    try:
        with _HTTP.open(req,timeout=12) as response:return json.loads(response.read())
    except urllib.error.HTTPError as err:
        try: message=json.loads(err.read()).get('error','HTTP_ERROR')
        except Exception: message='HTTP_ERROR'
        return {'ok':False,'status':err.code,'error':message}
    except (OSError,TimeoutError) as err:
        return {'ok':False,'error':'Coordinator unavailable: '+str(err)}

@mcp.tool()
def status()->dict:
    """View assigned tasks and registry states, NOT actual Antigravity Teamwork status."""
    return _call('status')

@mcp.tool()
def heartbeat(event:str='AVAILABLE')->dict:
    """Workers only: publish MCP contact (not live IDE/teamwork attestation)."""
    return _call('heartbeat',event=event)

@mcp.tool()
def create_task(tid:str,title:str,scope:str,contract:str,base_sha:str,wave_id:str='PILOT',requires_preview:bool=True,exclusive_resources:list[str]|None=None,depends_on:list[str]|None=None)->dict:
    """Codex only: create scoped work with real SHA and wave ID."""
    return _call('create_task',tid=tid,title=title,scope=scope,contract=contract,base_sha=base_sha,wave_id=wave_id,requires_preview=requires_preview,exclusive_resources=exclusive_resources or [],depends_on=depends_on or [])

@mcp.tool()
def assign_task(tid:str,owner:str)->dict:
    """Codex only: assign task to either worker with non-overlapping ownership lock."""
    return _call('assign_task',tid=tid,owner=owner)

@mcp.tool()
def get_task(tid:str)->dict:
    """Worker: read only own task; Codex: read any task."""
    return _call('get_task',tid=tid)

@mcp.tool()
def submit_checkpoint(tid:str,fencing:int,message:str)->dict:
    """Worker only: persist progress under ownership fencing."""
    return _call('checkpoint',tid=tid,fencing=fencing,message=message)

@mcp.tool()
def submit_self_qa(tid:str,fencing:int,commit_sha:str,changed_paths:list[str],checks:dict[str,bool],build_status:str,test_status:str,evidence_ref:str,preview_status:str='NOT_EXECUTED')->dict:
    """Worker mandatory pre-sync self QA. 4 check flags: scope,diff,regression,safety. PASS is a WORKER CLAIM."""
    return _call('submit_self_qa',tid=tid,fencing=fencing,commit_sha=commit_sha,changed_paths=changed_paths,checks=checks,build_status=build_status,test_status=test_status,preview_status=preview_status,evidence_ref=evidence_ref)

@mcp.tool()
def acknowledge_feedback(tid:str,fencing:int)->dict:
    """Worker acknowledges Codex feedback, begins next QA cycle, retains same exclusive lock."""
    return _call('acknowledge_feedback',tid=tid,fencing=fencing)

@mcp.tool()
def feedback_history(tid:str)->dict:
    """Task owner or Codex can read all QA feedback cycles."""
    return _call('feedback_history',tid=tid)

@mcp.tool()
def submit_result(tid:str,fencing:int,commit_sha:str,summary:str,build_status:str,test_status:str,evidence_ref:str)->dict:
    """Worker only: submit unverified commit+build/test claims and evidence for Codex review."""
    return _call('submit_result',tid=tid,fencing=fencing,commit_sha=commit_sha,summary=summary,build_status=build_status,test_status=test_status,evidence_ref=evidence_ref)

@mcp.tool()
def freeze_task(tid:str,reason:str)->dict:
    """Codex only: freeze work; retain lock."""
    return _call('freeze',tid=tid,reason=reason)

@mcp.tool()
def read_review(tid:str)->dict:
    """Codex only: read submitted task and all evidence."""
    return _call('read_review',tid=tid)

@mcp.tool()
def review_task(tid:str,decision:str,report:str,evidence_ref:str,build_verified:bool=False,tests_verified:bool=False,preview_verified:bool=False,preview_evidence_ref:str='',issues:list[dict]|None=None)->dict:
    """Codex only: PASS_CODE_REVIEW, CHANGES_REQUESTED or BLOCKED. No auto-release."""
    return _call('review_task',tid=tid,decision=decision,report=report,evidence_ref=evidence_ref,build_verified=build_verified,tests_verified=tests_verified,preview_verified=preview_verified,preview_evidence_ref=preview_evidence_ref,issues=issues or [])

@mcp.tool()
def close_task(tid:str,integration_sha:str,source_stopped:bool)->dict:
    """Codex only: close reviewed task after externally confirming worker stopped and integration SHA."""
    return _call('close_task',tid=tid,integration_sha=integration_sha,source_stopped=source_stopped)

@mcp.tool()
def wave_report(wave_id:str='PILOT',requires_preview:bool=True)->dict:
    """Codex only: aggregate both workers' real registry statuses and review decisions."""
    return _call('report',wave_id=wave_id)

@mcp.tool()
def audit_log()->dict:
    """Codex only: immutable-like append-only event trail (pilot DB, not tamper-proof)."""
    return _call('audit')


@mcp.tool()
def control_status()->dict:
    """Codex: recovery / emergency stop mode and frozen lock counts."""
    return _call('control_status')

@mcp.tool()
def emergency_stop(reason:str)->dict:
    """Codex: freeze all active ownerships; DOES NOT kill Windows processes."""
    return _call('emergency_stop',reason=reason)

@mcp.tool()
def resume_control(workers_stopped:bool,backup_verified:bool,operator_approval:str)->dict:
    """Codex only: manually re-enable new work after OS stoppage + DB backup verified."""
    return _call('resume_control',workers_stopped=workers_stopped,backup_verified=backup_verified,operator_approval=operator_approval)

@mcp.tool()
def resume_frozen_task(tid:str,owner:str,worker_stopped:bool,checkpoint_verified:bool)->dict:
    """Codex: resume same-owner task with NEW fencing token; cross-account handover prohibited."""
    return _call('resume_frozen_task',tid=tid,owner=owner,worker_stopped=worker_stopped,checkpoint_verified=checkpoint_verified)

@mcp.tool()
def sweep_stale_workers(max_age_seconds:int=180)->dict:
    """Codex: freeze agent tasks with stale MCP contact; never auto-release ownership."""
    return _call('stale_sweep',max_age_seconds=max_age_seconds)

@mcp.tool()
def independent_qa_evidence(tid:str)->dict:
    """Codex: read independent QA runner records. Missing record = NOT EXECUTED."""
    return _call('qa_evidence',tid=tid)

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--identity', choices=('CODEX','ANTI-01','ANTI-02'), default=os.environ.get('KTOOL_IDENTITY'))
    parser.add_argument('--token-file', default=os.environ.get('KTOOL_TOKEN_FILE'))
    opts=parser.parse_args(argv)
    try:
        configure(opts.identity, opts.token_file)
    except Exception:
        parser.exit(2, 'K-TOOL identity verification failed; check identity, credential path and coordinator.\n')
    mcp.run(transport='stdio')


@mcp.tool()
def control_snapshot()->dict:
    """CODEX: read durable mission orchestration; provider/session status remains evidence-bound."""
    return _call('control_snapshot')

@mcp.tool()
def get_assignment(assignment:str)->dict:
    """Read own assignment; CODEX may read all. Does not grant write approval."""
    return _call('get_assignment',assignment=assignment)

@mcp.tool()
def acknowledge_assignment(assignment:str,epoch:int,contract_hash:str)->dict:
    """Assigned worker acknowledges its exact approved immutable contract and epoch."""
    return _call('acknowledge_assignment',assignment=assignment,epoch=epoch,contract_hash=contract_hash)

@mcp.tool()
def assignment_checkpoint(assignment:str,epoch:int,commit:str,changed_paths:list[str],build_evidence:dict,blockers:list[str]|None=None,artifacts:list[str]|None=None)->dict:
    """Worker submits actual Git candidate and untrusted QA evidence for independent review."""
    return _call('assignment_checkpoint',assignment=assignment,epoch=epoch,commit=commit,changed_paths=changed_paths,build_evidence=build_evidence,blockers=blockers or [],artifacts=artifacts or [])

@mcp.tool()
def assignment_submit_claim(assignment:str,epoch:int)->dict:
    """Worker requests review; provider completion never implies acceptance."""
    return _call('assignment_submit_claim',assignment=assignment,epoch=epoch)

@mcp.tool()
def steering_ack(steering:str,target:str)->dict:
    """Owning worker acknowledges steering delivered to its exact target."""
    return _call('steering_ack',steering=steering,target=target)

@mcp.tool()
def propose_contract(contract_id:str,content:dict,affects_baseline:bool=True)->dict:
    """CODEX proposes a contract; this never approves the proposal."""
    return _call('propose_contract',contract_id=contract_id,content=content,affects_baseline=affects_baseline)

@mcp.tool()
def read_approved_contract(contract_hash:str)->dict:
    """Read immutable approved contract; unapproved proposals are denied."""
    return _call('read_approved_contract',contract_hash=contract_hash)

@mcp.tool()
def publish_revision(content:dict)->dict:
    """CODEX publishes a revision pinned to already approved contracts."""
    return _call('publish_revision',content=content)

@mcp.tool()
def create_mission(mission:str,revision:str,policy:dict|None=None)->dict:
    """CODEX creates mission under approved revision; no release approval."""
    return _call('create_mission',mission=mission,revision=revision,policy=policy)

@mcp.tool()
def queue_wave(mission:str,wave:str,assignments:list[dict],parent:str|None=None)->dict:
    """CODEX queues bounded worker assignments; does not start provider execution."""
    return _call('queue_wave',mission=mission,wave=wave,assignments=assignments,parent=parent)

@mcp.tool()
def dispatch(capabilities:dict|None=None)->dict:
    """CODEX allocates eligible scopes/epochs; does not remotely control Antigravity."""
    return _call('dispatch',capabilities=capabilities)

@mcp.tool()
def steer(mission:str,assignment:str,target:str,context_version:str,instruction:str)->dict:
    """Queue advisory steering for an exact active owner/member and revision."""
    return _call('steer',mission=mission,assignment=assignment,target=target,context_version=context_version,instruction=instruction)

@mcp.tool()
def human_request(mission:str,kind:str,body:str,assignment:str|None=None,deadline:str|None=None)->dict:
    """Record input/direction/review/approval request; never grants approval."""
    return _call('human_request',mission=mission,kind=kind,body=body,assignment=assignment,deadline=deadline)

if __name__=='__main__':
    main()
