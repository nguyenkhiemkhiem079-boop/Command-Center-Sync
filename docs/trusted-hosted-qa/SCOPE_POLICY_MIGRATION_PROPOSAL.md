# Scope policy migration proposal

Status: **PROPOSED — owner approval required before activation**

## Baseline and invariants

The current candidate-side `.github/scope-policy.json` uses schema version 1 and sets `approval_state` to `PENDING_OWNER_APPROVAL`. It allows only the non-production `CI-PILOT` assignment to write under `ci-pilot/`; `.github`, tests, coordinator code, configuration, scripts, and shared-core paths are protected. The trusted verifier reads policy from the selected protected base, never from the candidate.

Do not convert the policy to `OWNER_APPROVED` or broaden its path list as part of this code change. Approval must name the exact reviewed policy bytes/hash and target branch. No worker self-approval is valid. The existing integration ruleset `25346465` remains unchanged.

## Versioned migration

1. Keep schema v1 parsing enabled for immutable older tasks and records.
2. Propose schema v2 only after review, with required fields `schema_version`, `policy_id`, `policy_revision`, `repository`, `approval_state`, `approver`, `approved_at`, `content_sha256`, `protected_paths`, `assignments`, and `migration_from`.
3. Define the v2 digest over canonical JSON with `content_sha256` omitted; reject a digest mismatch, unknown schema version, duplicate/case-colliding paths, and a broader assignment than the approved v1 source.
4. Migrate only the CI-PILOT assignment and carry forward all protected paths. Preserve the old policy file and its digest in the migration record. Do not delete or rewrite historical approvals.
5. Require a separate owner review to set `approval_state=OWNER_APPROVED`; the approver must differ from the policy proposer and the approval must name the v2 digest and destination branch.
6. Enable protected checks only after the owner-approved policy is present on the protected base and the required positive/negative hosted checks are reproducible.

## Current deployment limit

The GitHub default branch currently does not contain `.github/scope-policy.json`; its existing scope workflow therefore cannot be treated as a functioning policy gate until a reviewed bootstrap PR adds the versioned policy and matching workflow behavior. The current default-branch Ruleset is being configured separately. The integration branch policy and Ruleset are not to be changed by this migration proposal.

No migration, approval, Ruleset update, hosted run, or required-check activation is claimed by this document.
