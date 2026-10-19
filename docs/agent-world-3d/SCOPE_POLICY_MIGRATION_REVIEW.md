# Trusted scope-policy migration for PR #4 — independent owner review

Status: **PROPOSAL ONLY — NOT TRUSTED, NOT ACTIVE, NOT A CI PASS**  
Prepared from source at `7a87fccbd474d2663cc66f390abc1b80f80e4aa0`; target remains PR #4 on `feature/agent-world-3d`.

## Observed gate and why it fails

The PR check uses `ci_scope_gate.py` and `.github/scope-policy.json` from the pull request's base commit. The current policy parser accepts schema 1 only, requires `approval_state: OWNER_APPROVED`, and the trusted workflow always selects assignment `CI-PILOT`. The policy on the reviewed development base is still `PENDING_OWNER_APPROVAL`; its only assignment is `CI-PILOT`, whose scope is `ci-pilot/`. The hosted failure `OWNER_APPROVED_BASE_POLICY_REQUIRED` is therefore the intended fail-closed result. Merely changing the policy in PR #4 cannot satisfy the check because the candidate copy is untrusted.

After approval is addressed, the current `CI-PILOT` assignment still cannot authorize PR #4. Its change set spans `frontend/`, `web/`, `server.py`, `cockpit.py`, `tests/`, and documentation. `server.py` and all `tests/` paths are explicitly protected, and schema 1 permits only one parent scope per assignment. Do not repurpose CI-PILOT, unprotect those paths globally, or add a policy file to PR #4 and call it trusted.

## Proposed migration sequence

1. An independent owner reviews the exact PR #4 diff and this proposal, including the protected-file exceptions below. No code from PR #4 is executed by the scope workflow.
2. On a trusted base through the repository's normal owner-reviewed process, publish a new versioned scope-gate policy/checker pair. The migration must bind the assignment to repository, PR number `4`, exact head repository, and exact head branch `feature/agent-world-3d`; it must reject any mismatch. Policy and checker must be loaded from the immutable PR base, never from the candidate.
3. Keep `CI-PILOT` unchanged (`ci-pilot/` only). Add a separate `AGENT-WORLD-PR4` assignment with a finite path allowlist derived from the reviewed PR diff. Preserve the existing protected-path list. If the owner explicitly approves the protected-file changes, encode only the exact paths `server.py`, `tests/browser_agent_world.mjs`, `tests/run_agent_world_browser_staging.py`, and `tests/test_agent_world.py` as assignment-bound, PR-bound review exceptions. The checker must reject all other protected paths and all rename, symlink, junction, traversal, ancestry, or repository mismatches.
4. Keep the required GitHub PR review and `Trusted base scope policy` check. Do not add bypass actors, `pull_request_target`, privileged secrets, force-push permission, or an auto-merge path. The policy exception only grants a path check for this exact reviewed assignment; the existing human review remains a separate merge gate.
5. Validate the migrated checker with isolated fixtures for the exact allowed files, each protected-path exception, an unlisted protected file, a different PR number/ref, modified candidate policy, fake/nonexistent SHA, wrong ancestry, symlink, rename escape, and path traversal. The migration is not usable until a hosted run executes the trusted base revision and the owner independently confirms the policy/check source SHA.
6. After that base is installed, rerun PR #4 checks against the exact current head. A green scope check certifies only source-path policy; it is not hosted build/test provenance. Do not merge PR #4 until all required checks and the independent human review pass.

## Proposed assignment shape (illustrative, not accepted schema)

This shape is intentionally **not** placed in `.github/scope-policy.json`: the current trusted checker rejects schema 2 and does not implement these bindings. The owner-reviewed migration must settle an exact finite path list from the candidate tree at review time; the categories below are explanatory only.

```json
{
  "schema_version": 2,
  "approval_state": "PENDING_OWNER_APPROVAL",
  "repository": "nguyenkhiemkhiem079-boop/Command-Center-Sync",
  "assignments": {
    "CI-PILOT": "preserve existing schema-1 semantics and ci-pilot-only scope",
    "AGENT-WORLD-PR4": {
      "pull_request_number": 4,
      "head_repository": "nguyenkhiemkhiem079-boop/Command-Center-Sync",
      "head_ref": "feature/agent-world-3d",
      "allowed_paths": "exact owner-reviewed paths from PR #4 diff",
      "protected_path_exceptions": [
        "server.py",
        "tests/browser_agent_world.mjs",
        "tests/run_agent_world_browser_staging.py",
        "tests/test_agent_world.py"
      ]
    }
  }
}
```

The illustration is not a usable policy and must never produce a passing check. A separate review must verify the actual source changes, exact path list, trusted-base revision, GitHub required-check identity, and human-review rules before activation.

## Current decision and next action

No trusted-base policy, workflow, branch rule, or live installation was changed for this proposal. The present outcome remains **BLOCKED** at the policy prerequisite; PR #4 must remain unmerged. The project owner or an independent authorized reviewer must review the exact exception set and approve a concrete migration commit on the trusted base. Until then, preserve the fail-closed check.
