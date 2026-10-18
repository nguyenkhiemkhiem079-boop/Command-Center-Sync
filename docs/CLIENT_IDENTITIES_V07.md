# MCP identities on one Windows user — v0.7

Every adapter process requires both an expected identity (`CODEX`, `ANTI-01`,
`ANTI-02`) and an explicit credential-file reference. These can be CLI flags
`--identity` / `--token-file`, or process-local environment variables
`KTOOL_IDENTITY` / `KTOOL_TOKEN_FILE`. Never supply token contents as a CLI argument.
There is no fallback to the old common `KTOOLMCP/client_token.txt`.

Before starting the stdio MCP transport, the adapter authenticates to the loopback
coordinator and verifies that `status.result.actor` matches the expected identity.
A mismatch, inaccessible file or unavailable coordinator stops startup. The token
is pinned in memory for that process. Backend bearer-token authentication controls
permissions; a requested identity never grants a role.

`scripts/install-client.ps1 -Role CODEX` creates `ktool-codex` through the Codex CLI.
Workers require an explicitly supplied existing MCP JSON config file:

```powershell
./scripts/install-client.ps1 -Role ANTI-01 -McpConfigPath '<actual workspace MCP JSON path>'
./scripts/install-client.ps1 -Role ANTI-02 -McpConfigPath '<other workspace MCP JSON path>'
```

Worker config locations must come from the actual client/workspace, not guesses.
Each entry uses the dedicated `.client-venv` interpreter and explicit process
identity/credential reference. Credentials and separate launchers live under
`%APPDATA%/KTOOLMCP/identities/<ROLE>/`. Existing credential files are retained.
Existing equivalent entries are left unchanged; conflicting entries fail unless
the operator explicitly supplies `-ReplaceExisting`. JSON updates preserve other
entries and first create a backup. Dependencies are installed only into the
dedicated venv. The installer does not copy or delete the legacy credential.

This provides process configuration separation and backend RBAC on one OS user.
It does not prevent that Windows user from reading another identity's credential
or modifying source. Strong adversarial isolation still requires separate OS/ACL
or sandbox boundaries. MCP test success does not establish Antigravity Teamwork,
separate Google authentication, quota availability or Revit runtime acceptance.

Regression suite: `python -m unittest discover -s tests -p test_client_identity.py -v`.
It uses disposable tokens, a temporary SQLite coordinator and real concurrent
stdio adapter subprocesses. It does not connect to Antigravity.
