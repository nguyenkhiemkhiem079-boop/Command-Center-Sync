# Reset / token rotation (pilot only)

Before resetting, stop `server.py`, stop all Codex/Antigravity MCP adapters, and verify no worker writes or tasks are in progress.

To reset a *throwaway pilot* only, delete the `private` folder and run `py -3 bootstrap.py` again; then rerun `scripts/install-client.ps1` for EACH role with the new token. This destroys all pilot tasks/audit/locks. Never do this for production data.

If a token is exposed, stop the coordinator immediately. Plan a role-specific rotation workflow in a later version; v0.2 only supports full reprovisioning and should not be used with real protected source access.
