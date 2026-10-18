"""Conservative Antigravity process adapter; runtime success is never QA acceptance.
No OAuth, credential lookup, automatic retry, restart, merge or permission bypass.
Raw model text, reasoning, parameters, output and stderr are never retained.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time
import uuid


class Mode(str, Enum):
    AGY_HEADLESS = 'AGY_HEADLESS'
    TEAMWORK_NATIVE = 'TEAMWORK_NATIVE'
    SUPERVISED_IDE = 'SUPERVISED_IDE'


def conversation_id(value):
    try:
        return str(uuid.UUID(value)) if isinstance(value, str) else None
    except ValueError:
        return None


def capabilities(help_text='', executable=None, native_teamwork_verified=False):
    """Detection is metadata only: never logs in or treats docs as live entitlement."""
    resolved = shutil.which(executable or 'agy')
    headless = bool(resolved and all(x in help_text for x in ('--print', '--output-format', '--conversation')))
    return {'executable': resolved, 'AGY_HEADLESS': headless,
            'TEAMWORK_NATIVE': False,
            'TEAMWORK_NATIVE_STATUS': 'BLOCKED_NO_VERIFIED_START_MONITOR_BACKEND',
            'SUPERVISED_IDE': True, 'native_teamwork_verified': False,
            'api_coding_worker': 'UNAVAILABLE_NO_AUTHORIZED_API_CONFIGURATION',
            'os_isolation': 'LOGICAL_ONLY'}


@dataclass(frozen=True)
class Assignment:
    worker: str
    task_id: str
    scope: str
    worktree: Path
    fencing: int

    def validate(self):
        from registry import clean_scope
        if self.worker not in ('ANTI-01', 'ANTI-02') or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', self.task_id):
            raise ValueError('Invalid worker/task identity')
        clean_scope(self.scope)
        if type(self.fencing) is not int or self.fencing < 1 or not self.worktree.is_dir():
            raise ValueError('Existing worktree and positive fencing required')


def build_argv(executable, mode, prompt, assignment, detected, resume=None):
    """Explicit argv; no shell, permission bypass, guessed account or --continue."""
    assignment.validate()
    mode = Mode(mode)
    if mode == Mode.SUPERVISED_IDE:
        raise RuntimeError('SUPERVISED_IDE_REQUIRES_HUMAN_DISPATCH')
    if mode == Mode.TEAMWORK_NATIVE:
        # A caller's Boolean or fabricated capability dict is not session attestation.
        raise RuntimeError('TEAMWORK_NATIVE_BLOCKED_SUPERVISED_MANUAL_LAUNCH_REQUIRED')
    if not detected.get(mode.value) or not detected.get('executable'):
        raise RuntimeError('RUNTIME_CAPABILITY_NOT_VERIFIED')
    if Path(executable).resolve() != Path(detected['executable']).resolve():
        raise ValueError('Executable differs from detected executable')
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 24000:
        raise ValueError('Bounded task prompt required')
    if resume is not None and not conversation_id(resume):
        raise ValueError('Explicit conversation UUID required')
    prefix = '/teamwork-preview ' if mode == Mode.TEAMWORK_NATIVE else ''
    metadata = (f'Task {assignment.task_id}; worker {assignment.worker}; owned scope {assignment.scope}; '
                f'fencing {assignment.fencing}. Do not edit outside owned scope. ')
    argv = [str(executable), '--print', prefix + metadata + prompt, '--output-format', 'stream-json']
    if resume:
        argv += ['--conversation', conversation_id(resume)]
    return argv


@dataclass
class StreamAudit:
    expected_conversation: str | None = None
    events: list = field(default_factory=list)
    flags: set = field(default_factory=set)
    conversation: str | None = None
    results: int = 0
    terminal_success: bool = False
    tool_errors: int = 0
    denied_actions: int = 0
    subagents: set = field(default_factory=set)
    initialized: bool = False

    def _bind(self, value):
        ident = conversation_id(value)
        if not ident:
            self.flags.add('INVALID_CONVERSATION_ID')
        elif (self.conversation and self.conversation != ident) or (self.expected_conversation and ident != self.expected_conversation):
            self.flags.add('CONVERSATION_CHANGED')
        else:
            self.conversation = ident

    def feed(self, line):
        if len(line) > 1024 * 1024:
            self.flags.add('EVENT_TOO_LARGE')
            return
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            self.flags.add('MALFORMED_EVENT')
            return
        if not isinstance(event, dict):
            self.flags.add('MALFORMED_EVENT')
            return
        kind = event.get('event')
        if kind == 'init':
            if self.initialized or self.results:
                self.flags.add('INVALID_EVENT_ORDER')
            self.initialized = True
            self._bind(event.get('conversation_id'))
            self.events.append({'event': 'status', 'state': 'INITIALIZED'})
        elif kind == 'step_update':
            if not self.initialized or self.results:
                self.flags.add('INVALID_EVENT_ORDER')
            step = event.get('step_update')
            if not isinstance(step, dict):
                self.flags.add('MALFORMED_EVENT')
                return
            self._bind(step.get('conversation_id'))
            # Agent response, text_delta, thinking, usage and tool outputs are discarded.
            if step.get('step_type') == 'tool':
                info = step.get('tool_info') or {}
                if not isinstance(info, dict):
                    self.flags.add('MALFORMED_EVENT')
                    return
                failed = step.get('state') in ('ERROR','FAILED','FAIL') or bool(info.get('error')) or info.get('is_error') is True
                self.tool_errors += int(failed)
                state = step.get('state') if step.get('state') in ('ACTIVE','DONE','ERROR','FAILED','FAIL') else 'UNKNOWN'
                name = step.get('tool_name')
                name = name if isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,120}',name) else 'UNSPECIFIED'
                self.events.append({'event': 'tool', 'name': name, 'state': state, 'error': failed})
            info = step.get('subagent_info')
            if isinstance(info, dict):
                children = info.get('subagents',[])
                if not isinstance(children,list):
                    self.flags.add('MALFORMED_EVENT')
                    return
                for child in children:
                    if isinstance(child, dict) and conversation_id(child.get('conversation_id')):
                        self.subagents.add(conversation_id(child['conversation_id']))
        elif kind == 'result':
            if not self.initialized or self.results:
                self.flags.add('INVALID_EVENT_ORDER')
            result = event.get('result')
            if not isinstance(result, dict):
                self.flags.add('MALFORMED_EVENT')
                return
            self._bind(result.get('conversation_id'))
            self.results += 1
            status = result.get('status')
            self.terminal_success = status == 'SUCCESS'
            denied = result.get('denied_actions',[])
            if not isinstance(denied,list):
                self.flags.add('MALFORMED_DENIALS')
            else:
                self.denied_actions += len(denied)
            if result.get('error'):
                self.flags.add('RESULT_ERROR')
            if status in ('TIMEOUT','CANCELLED','PERMISSION_DENIED','AUTHENTICATION_REQUIRED','QUOTA_EXHAUSTED'):
                self.flags.add('RUNTIME_BLOCKED')
            elif status != 'SUCCESS':
                self.flags.add('RESULT_NOT_SUCCESS')
            if not isinstance(result.get('response'), str) or not result['response'].strip():
                self.flags.add('EMPTY_RESPONSE')
            self.events.append({'event': 'status', 'state': 'SUCCESS' if status == 'SUCCESS' else 'NOT_SUCCESS'})
        # Unknown event bodies are discarded, never copied to evidence.
        else:
            self.flags.add('UNKNOWN_EVENT')
        if len(self.events) > 10000:
            self.events = self.events[-10000:]
            self.flags.add('EVENT_LIMIT')

    def finish(self, exit_code=0, timed_out=False):
        flags = set(self.flags)
        if timed_out:
            flags.add('TIMEOUT')
        if exit_code != 0:
            flags.add('PROCESS_EXIT_NONZERO')
        if self.results != 1:
            flags.add('TERMINAL_RESULT_REQUIRED')
        if self.tool_errors:
            flags.add('TOOL_ERROR')
        if self.denied_actions:
            flags.add('DENIED_ACTIONS')
        blocked = bool({'TIMEOUT','DENIED_ACTIONS','RUNTIME_BLOCKED'} & flags)
        return {'status': 'BLOCKED' if blocked else ('FAIL' if flags else 'COMPLETED_UNVERIFIED'),
                'flags': sorted(flags), 'conversation_id': self.conversation,
                'tool_errors': self.tool_errors, 'denied_actions': self.denied_actions,
                'subagent_count': len(self.subagents), 'native_teamwork_accepted': False,
                'events': self.events, 'independent_qa': 'NOT_EXECUTED', 'automatic_restart': False}


def parse_file(path, expected_conversation=None):
    audit = StreamAudit(expected_conversation=expected_conversation)
    with Path(path).open(encoding='utf-8-sig') as source:
        for line in source:
            if line.strip():
                audit.feed(line)
    return audit.finish()


def supervise(argv, assignment, timeout_seconds=300, expected_conversation=None):
    """One explicitly requested process; tests supply a fixture, never real credentials.
    Args are a trusted supervisor input. No raw stdout/stderr or prompt is returned.
    """
    assignment.validate()
    if not isinstance(argv,(list,tuple)) or not argv or not all(isinstance(x,str) and x for x in argv):
        raise ValueError('Explicit argv list required')
    if not 0 < timeout_seconds <= 3600:
        raise ValueError('Bounded timeout required')
    audit = StreamAudit(expected_conversation=expected_conversation)
    messages = queue.Queue(maxsize=100)
    try:
        process = subprocess.Popen(argv,cwd=assignment.worktree,stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',errors='replace',shell=False)
    except OSError:
        audit.flags.add('PROCESS_START_FAILED')
        return audit.finish(exit_code=None)
    stopped = threading.Event()
    def read():
        try:
            while not stopped.is_set():
                line = process.stdout.readline(1024*1024+1)
                if not line:
                    break
                while not stopped.is_set():
                    try:
                        messages.put(line,timeout=.1)
                        break
                    except queue.Full:
                        pass
        finally:
            while not stopped.is_set():
                try:
                    messages.put(None,timeout=.1)
                    break
                except queue.Full:
                    pass
    reader = threading.Thread(target=read,daemon=True)
    reader.start()
    deadline = time.monotonic()+timeout_seconds
    timed_out = False
    try:
        while True:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            try:
                line = messages.get(timeout=min(remaining,.1))
            except queue.Empty:
                continue
            if line is None:
                break
            audit.feed(line)
        if not timed_out:
            try:
                process.wait(timeout=max(.001,deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                timed_out = True
    finally:
        stopped.set()
        if process.poll() is None:
            if os.name == 'nt':
                try:
                    cleanup=subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
                    if cleanup.returncode:
                        audit.flags.add('DESCENDANT_CLEANUP_NOT_VERIFIED')
                except (OSError,subprocess.TimeoutExpired):
                    audit.flags.add('DESCENDANT_CLEANUP_NOT_VERIFIED')
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
        reader.join(timeout=2)
        if reader.is_alive():
            audit.flags.add('DESCENDANT_CLEANUP_NOT_VERIFIED')
        else:
            process.stdout.close()
    result = audit.finish(process.returncode,timed_out)
    result['assignment'] = {'worker':assignment.worker,'task_id':assignment.task_id,
                            'scope':assignment.scope,'fencing':assignment.fencing}
    result['descendant_cleanup'] = 'TASKKILL_REQUESTED_ON_TIMEOUT' if timed_out and os.name=='nt' else 'NOT_VERIFIED'
    return result
