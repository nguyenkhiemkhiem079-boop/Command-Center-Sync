# Pilot Security Notes

This package is an original prototype, separate from the existing K-TOOL source. It does not use or incorporate ATool, BIMSpeed or PMH binaries.

- Do not upload `private/`, API tokens, Google OAuth data, Windows credential files, or logged-in browser profiles.
- The `server.py` endpoint is an authenticated REST registry on `127.0.0.1`, **not** an MCP HTTP server.
- `client_mcp.py` is a real per-profile **MCP stdio server**. It must run under the identity assigned to its Windows profile.
- Client local role keys are bearer secrets, stored in per-user `APPDATA`. API token is hashed in the central roles JSON. Any process running with the same Windows user privileges can potentially read that user's token.
- Strict Write Access to source paths is NOT yet enforced; the lock currently guards registry assignment only. Do not let untrusted worker accounts write to one common worktree.
- No transfer of Gemini/Antigravity account sessions, no automation for quota circumvention.
- Admin must maintain NTFS ACLs on `private/` for the supervisor account only; current bootstrap does not configure directory ACLs automatically.
- Future: 1. GitHub Apps auth and branch protection, 2. isolated NTFS ACL/worktrees, 3. provider-supported Teamwork session hooks, 4. Windows Service, 5. QA/evidence hashing, 6. monitored recovery, 7. release approval.
- A frozen task needs manual intervention to release and/or reassign after verifying the original process has stopped. This v0.2 has **no unlock/reassign tool by design**. Reset pilot DB only when no real work depends on it.
