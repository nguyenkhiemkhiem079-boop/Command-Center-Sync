"""Run Agent World through real headless Chrome against an isolated temporary server."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from registry import hash_token

OUT = ROOT / "docs" / "agent-world-3d"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not CHROME.is_file():
        raise SystemExit("Chrome not installed at the verified path")
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        raise SystemExit("Node.js is required only to run the CDP browser harness")
    token = secrets.token_urlsafe(32)
    roles = {identity: hash_token(secrets.token_urlsafe(32)) for identity in ("CODEX", "ANTI-01", "ANTI-02")}
    roles["CODEX"] = hash_token(token)
    port = free_port()
    screenshot = OUT / "AGENT_WORLD_SCREENSHOTS" / "agent-world-chrome-staging.png"
    browser_report = OUT / "AGENT_WORLD_SCREENSHOTS" / "browser-e2e.json"
    fallback_screenshot = OUT / "AGENT_WORLD_SCREENSHOTS" / "agent-world-chrome-no-webgl.png"
    fallback_report = OUT / "AGENT_WORLD_SCREENSHOTS" / "browser-fallback-e2e.json"
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ktool-agent-world-stage-") as temp:
        temp_path = Path(temp)
        roles_file, token_file = temp_path / "roles.json", temp_path / "codex-token.txt"
        roles_file.write_text(json.dumps(roles), encoding="utf-8")
        token_file.write_text(token, encoding="utf-8")
        token = ""  # Avoid retaining the staging credential past the launch configuration.
        log_file = (temp_path / "server.log").open("w", encoding="utf-8")
        server = subprocess.Popen([
            sys.executable, str(ROOT / "server.py"), "--db", str(temp_path / "registry.sqlite"),
            "--roles", str(roles_file), "--port", str(port),
        ], cwd=ROOT, stdout=log_file, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            ready = False
            for _ in range(100):
                if server.poll() is not None:
                    break
                try:
                    with urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                        ready = response.status == 200
                        if ready:
                            break
                except Exception:
                    time.sleep(0.2)
            if not ready:
                raise RuntimeError("Disposable Command Center server failed to become healthy")
            command = [
                node, str(ROOT / "tests" / "browser_agent_world.mjs"),
                f"--url=http://127.0.0.1:{port}/ui",
                f"--tokenFile={token_file}", f"--screenshot={screenshot}", f"--report={browser_report}",
                f"--browser={CHROME}",
            ]
            results = []
            for mode, image, report in (("webgl", screenshot, browser_report), ("fallback", fallback_screenshot, fallback_report)):
                mode_command = [
                    node, str(ROOT / "tests" / "browser_agent_world.mjs"),
                    f"--url=http://127.0.0.1:{port}/ui", f"--tokenFile={token_file}",
                    f"--screenshot={image}", f"--report={report}", f"--browser={CHROME}",
                    f"--expectFallback={'true' if mode == 'fallback' else 'false'}",
                ]
                completed = subprocess.run(mode_command, cwd=ROOT, capture_output=True, text=True, timeout=90)
                (OUT / "AGENT_WORLD_SCREENSHOTS" / f"browser-{mode}.stdout.txt").write_text(completed.stdout.strip() + "\n", encoding="utf-8")
                if completed.returncode:
                    raise RuntimeError(f"Browser {mode} harness failed ({completed.returncode}): {completed.stderr[-3000:]}")
                result = json.loads(report.read_text(encoding="utf-8"))
                if result["status"] != "PASS":
                    raise RuntimeError(f"Browser {mode} report did not pass")
                results.append(result)
            print(json.dumps({"status": "PASS", "port": port, "browser": results[0]["browserVersion"], "renderer": results[0]["result"]["renderer"], "webgl": str(screenshot.relative_to(ROOT)), "fallback": str(fallback_screenshot.relative_to(ROOT))}))
            return 0
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # This is only the disposable server process created above.
                server.kill()
                server.wait(timeout=5)
            log_file.close()


if __name__ == "__main__":
    raise SystemExit(main())
