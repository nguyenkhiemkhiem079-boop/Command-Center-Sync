# Local hardening 2026-10-18

- Preserve supplied v0.6 architecture and baseline.
- Reject Windows path aliases and non-boolean stop assertions.
- Independent QA checks baseline ancestry, complete immutable SHA diff, and checkout after commands.
- Close SQLite migration test connection on Windows.
- Add meaningful regression tests, safe local start/stop helpers, and secret exclusions.
- Installation uses a dedicated Python virtual environment; no global pip install.

Deployment is a local pilot. Registry locking does not provide filesystem isolation for two agents sharing the supervisor Windows account.
