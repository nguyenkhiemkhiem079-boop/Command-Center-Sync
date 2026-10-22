"""Local MCP bridge to the active Antigravity IDE language servers.

This uses the IDE's localhost language-server endpoint, not the `agy` CLI.
CSRF tokens are read from the running process command lines at call time and
are kept in memory only. No token is returned by an MCP tool or written here.
"""
from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP


SERVER = FastMCP("Antigravity IDE workers")
SERVICE = "exa.language_server_pb.LanguageServerService"
AGENTS = {
    "ANTI-01": "file_c_3A_KTOOL_Workspaces_ANTI_01",
    "ANTI-02": "file_c_3A_KTOOL_Workspaces_ANTI_02",
}
DEFAULT_MODEL = "MODEL_PLACEHOLDER_M318"  # Gemini 3.8 Flash (High), verified locally.
_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _instances() -> list[dict[str, Any]]:
    """Read running IDE language-server metadata without exposing CSRF tokens."""
    script = r"""
$ErrorActionPreference = 'Stop'
$items = @(Get-CimInstance Win32_Process -Filter "Name = 'language_server_windows_x64.exe'" | ForEach-Object {
    $line = $_.CommandLine
    $workspace = [regex]::Match($line, '--workspace_id(?:=|\s+)([^\s"]+)')
    $extensionPort = [regex]::Match($line, '--extension_server_port(?:=|\s+)(\d+)')
    $token = [regex]::Match($line, '--csrf_token(?:=|\s+)([^\s"]+)')
    if ($workspace.Success -and $extensionPort.Success -and $token.Success) {
        [pscustomobject]@{
            pid = [int]$_.ProcessId
            workspace = $workspace.Groups[1].Value
            extension_port = [int]$extensionPort.Groups[1].Value
            csrf_token = $token.Groups[1].Value
        }
    }
})
ConvertTo-Json -InputObject $items -Compress
"""
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError("Could not inspect local Antigravity IDE processes")
    try:
        data = json.loads(completed.stdout.strip() or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError("Could not parse local Antigravity IDE process data") from exc
    if isinstance(data, dict):
        data = [data]
    return data if isinstance(data, list) else []


def _target(agent: str) -> dict[str, Any]:
    key = agent.strip().upper()
    if key not in AGENTS:
        raise ValueError("agent must be ANTI-01 or ANTI-02")
    expected = AGENTS[key]
    matches = [p for p in _instances() if p.get("workspace", "").lower() == expected.lower()]
    if not matches:
        raise RuntimeError(f"{key} has no open Antigravity IDE workspace")
    if len(matches) > 1:
        raise RuntimeError(f"Multiple Antigravity IDE language servers match {key}; close the duplicate workspace")
    target = matches[0]
    target["agent"] = key
    target["port"] = _find_language_server_port(target)
    return target


def _headers(target: dict[str, Any]) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Connect-Protocol-Version": "1",
        "x-codeium-csrf-token": target["csrf_token"],
    }


def _post(target: dict[str, Any], method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"http://127.0.0.1:{target['port']}/{SERVICE}/{method}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload or {}).encode("utf-8"),
        headers=_headers(target),
        method="POST",
    )
    try:
        with _NO_PROXY.open(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            error = json.loads(raw)
            detail = error.get("message") or error.get("code") or "IDE language server error"
        except json.JSONDecodeError:
            detail = "IDE language server error"
        raise RuntimeError(f"{method} failed: {detail}") from None
    except (OSError, TimeoutError) as exc:
        raise RuntimeError(f"Could not reach {target['agent']} IDE language server: {exc}") from None
    try:
        value = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        raise RuntimeError(f"{method} returned invalid JSON") from None
    if not isinstance(value, dict):
        raise RuntimeError(f"{method} returned an unexpected response")
    return value


def _find_language_server_port(target: dict[str, Any]) -> int:
    base = int(target["extension_port"])
    for port in range(base + 1, base + 21):
        url = f"http://127.0.0.1:{port}/{SERVICE}/Heartbeat"
        request = urllib.request.Request(
            url,
            data=b"{}",
            headers={**_headers(target), "Content-Length": "2"},
            method="POST",
        )
        try:
            with _NO_PROXY.open(request, timeout=1) as response:
                if response.status == 200:
                    return port
        except (OSError, TimeoutError, urllib.error.HTTPError):
            continue
    raise RuntimeError(f"Could not find the localhost language-server port for {target['agent']}")


@SERVER.tool()
def list_antigravity_ide_agents() -> dict[str, Any]:
    """Show whether ANTI-01 and ANTI-02 IDE workspaces are open and reachable."""
    raw = _instances()
    rows = []
    for name, workspace_id in AGENTS.items():
        matches = [p for p in raw if p.get("workspace", "").lower() == workspace_id.lower()]
        row: dict[str, Any] = {"agent": name, "online": False}
        if matches:
            target = matches[0]
            try:
                port = _find_language_server_port(target)
                row.update({"online": True, "pid": target["pid"], "language_server_port": port})
            except RuntimeError as exc:
                row["error"] = str(exc)
        rows.append(row)
    return {"agents": rows, "surface": "Antigravity IDE local language server"}


@SERVER.tool()
def start_antigravity_ide_task(
    agent: str,
    task: str,
    model: str = DEFAULT_MODEL,
    max_output_tokens: int = 4096,
) -> dict[str, Any]:
    """Start a task in ANTI-01 or ANTI-02's Antigravity IDE workspace.

    Agentic tasks may edit that workspace and use its IDE tools. Call only for
    work the user has authorized. Returns a cascade_id for result polling.
    """
    if not isinstance(task, str) or not task.strip():
        raise ValueError("task must be non-empty")
    if len(task) > 20000:
        raise ValueError("task is too long (maximum 20,000 characters)")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must be non-empty")
    if not 64 <= int(max_output_tokens) <= 32768:
        raise ValueError("max_output_tokens must be between 64 and 32768")

    target = _target(agent)
    # CortexTrajectorySource.CASCADE_CLIENT = 1; CortexTrajectoryType.CASCADE = 4.
    started = _post(target, "StartCascade", {"source": 1, "trajectoryType": 4})
    cascade_id = started.get("cascadeId")
    if not cascade_id:
        raise RuntimeError("Antigravity IDE did not return a cascade id")

    config = {
        "plannerConfig": {
            "planModel": model,
            "conversational": {"agenticMode": True},
            "maxOutputTokens": int(max_output_tokens),
            "requestedModel": {"model": model},
        },
        "checkpointConfig": {"maxOutputTokens": int(max_output_tokens)},
        "applyModelDefaultOverride": False,
    }
    _post(target, "SendUserCascadeMessage", {
        "cascadeId": cascade_id,
        "items": [{"text": task}],
        "cascadeConfig": config,
        "clientType": "IDE",
    })
    return {
        "agent": target["agent"],
        "status": "started",
        "cascade_id": cascade_id,
        "model": model,
        "workspace_id": target["workspace"],
    }


@SERVER.tool()
def get_antigravity_ide_task_result(
    agent: str,
    cascade_id: str,
    wait_seconds: int = 0,
) -> dict[str, Any]:
    """Read a task result; optionally wait up to 180 seconds for completion."""
    if not cascade_id or len(cascade_id) > 128:
        raise ValueError("cascade_id must be non-empty and at most 128 characters")
    if not 0 <= int(wait_seconds) <= 180:
        raise ValueError("wait_seconds must be between 0 and 180")
    target = _target(agent)
    deadline = time.monotonic() + int(wait_seconds)
    while True:
        data = _post(target, "GetCascadeTrajectorySteps", {"cascadeId": cascade_id})
        steps = data.get("steps") or []
        for step in reversed(steps):
            response = (step.get("plannerResponse") or {}).get("response")
            if response:
                return {
                    "agent": target["agent"],
                    "status": "completed",
                    "cascade_id": cascade_id,
                    "response": response,
                }
        if time.monotonic() >= deadline:
            return {"agent": target["agent"], "status": "running", "cascade_id": cascade_id, "steps": len(steps)}
        time.sleep(1)


@SERVER.tool()
def cancel_antigravity_ide_task(agent: str, cascade_id: str) -> dict[str, Any]:
    """Cancel a running Antigravity IDE task by its cascade_id."""
    if not cascade_id or len(cascade_id) > 128:
        raise ValueError("cascade_id must be non-empty and at most 128 characters")
    target = _target(agent)
    _post(target, "CancelCascadeInvocation", {"cascadeId": cascade_id})
    return {"agent": target["agent"], "status": "cancelled", "cascade_id": cascade_id}


@SERVER.tool()
def list_antigravity_ide_models(agent: str) -> dict[str, Any]:
    """List models exposed by the selected Antigravity IDE account and quota."""
    target = _target(agent)
    data = _post(target, "GetCascadeModelConfigData")
    models = []
    for item in data.get("clientModelConfigs", []):
        model_ref = item.get("modelOrAlias") or {}
        quota = item.get("quotaInfo") or {}
        models.append({
            "label": item.get("label"),
            "model": model_ref.get("model") or model_ref.get("alias"),
            "recommended": bool(item.get("isRecommended")),
            "remaining_fraction": quota.get("remainingFraction"),
        })
    return {"agent": target["agent"], "models": models}


if __name__ == "__main__":
    SERVER.run(transport="stdio")
