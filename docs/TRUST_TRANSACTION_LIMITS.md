# Trust and transaction limits

`trust_vault.verify_evidence` validates controller-pinned task, identity, epoch, immutable Git IDs,
paths, profile/suite hashes, command manifest, artifact hashes and timestamp. The controller must
obtain expected bindings independently. Reading local files or SQLite cannot authenticate a worker.
`LOCAL_VERIFIED` means local evidence consistency; it does not establish production acceptance.

Production acceptance requires a controller-installed read-only hosted CI adapter. Its response must
bind repository, immutable workflow commit, workflow identity, run ID, candidate SHA, completed
successful checks, policy digest, exact evidence digest and artifact hashes. Missing adapters/policy
produce BLOCKED. Synthetic adapters produce BLOCKED even when their fixture response matches.
No genuine hosted adapter or protected principal is installed by these modules. A Python attribute
cannot authenticate an adapter: the controller and adapter supply chain must be independently
protected. Shared-user processes can tamper with local code, policy, credentials and files.

`TransactionSync` rehearses PREPARE, VALIDATE, INTEGRATION_QA, APPROVAL_PENDING and COMMIT.
Scope checks inspect real immutable Git diffs. Separate temporary integration branches cherry-pick
candidate histories and execute the exact controller QA manifest. Tests must leave integration HEAD
and worktree unchanged. Failures ABORT and return ownership/checkpoint without changing worker
branches or Central. Temporary integration worktrees remain for investigation; caller controls cleanup.

Only `refs/ktool-disposable/*` can be updated, using atomic `git update-ref new expected-old`.
Even these require an explicit controller owner test fixture verifier with the exact approval binding.
No protected production Central write backend exists: production mutation remains BLOCKED.
No network push, deployment, auto-merge or release is performed. A real deployment must replace
the disposable backend with owner-authorized protected execution and independently enforce locks,
provenance and branch protections. These local modules cannot provide OS isolation or eliminate
same-user time-of-check/time-of-use races.

Tests use synthetic CI responses and owner fixtures explicitly; they prove fail-closed behavior and
actual disposable Git operations, not live CI trust or real owner authentication. The conflict test
introduces a conflicting integration commit then executes an actual failing Git cherry-pick.
