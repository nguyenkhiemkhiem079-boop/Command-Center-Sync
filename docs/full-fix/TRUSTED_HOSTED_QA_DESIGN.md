# Trusted Hosted QA: design and live activation state

## Purpose

This adds an independent hosted build/test path for an exact pull-request head. It is deliberately separate from the existing `Trusted base scope policy` check. The scope gate decides whether changed paths are permitted; it does not certify a build or test result.

## Trust flow

1. An owner manually dispatches `.github/workflows/trusted-independent-qa.yml` with a PR number, exact base SHA, and exact candidate SHA.
2. A preflight job checks that the run came from the configured workflow branch and owner, checks the PR is still open at those exact SHAs, checks the protected integration branch has not moved, and validates the candidate using the scope policy and checker from the selected base commit. It reads Git objects only.
3. A separate ephemeral `windows-2022` job creates a candidate overlay from tracked Git blobs. It rejects links, submodules, path aliases and traversal. It removes candidate tests and copies in the test files pinned by the trusted workflow revision. It installs dependencies from trusted workflow files into a disposable virtual environment, allows binary wheels only, records the pip download report and installed package inventory, compiles the overlay, and runs the pinned regression suite.
4. The candidate execution job has `contents: read` only, receives no `GITHUB_TOKEN` environment variable or repository secrets, and gets a filtered child-process environment. The workflow records the actual runner-step outcome separately from the child-written exit value.
5. A fresh attestor job rechecks the PR, base, candidate, tree, paths, policy, profile and suite. It obtains the diagnostic-log artifact ID and server-reported digest, creates a report whose result is derived from the GitHub job and step outcomes, signs that report with GitHub artifact provenance, then creates `Trusted Independent QA` against the exact candidate SHA. The attestor job does not execute candidate code.
6. The report always leaves owner review pending. A passing independent QA check is not an approval, merge, release, production QA result, or Antigravity session claim.

GitHub documents that artifact signatures, timestamps, and signer identity must be verified, and recommends `gh attestation verify`; see [artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations) and the [attestations API](https://docs.github.com/en/rest/repos/attestations). The repository is public, so GitHub's public-repository plan requirement for artifact attestations is met. The official workflow guidance warns that `pull_request_target` is elevated trust and should not execute untrusted code; this design uses owner-triggered `workflow_dispatch` from a separately protected branch instead. See [securely using pull_request_target](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target).

## Immutable action pins

| Action | Pinned commit |
|---|---|
| `actions/checkout` | `11bd71901bbe5b1630ceea73d27597364c9af683` |
| `actions/setup-python` | `ece7cb06caefa5fff74198d8649806c4678c61a1` |
| `actions/upload-artifact` | `ea165f8d65b6e75b540449e92b4886f43607fa02` |
| `actions/attest` | `1e69f48acb82d1966a394da916b4c1698aa569d6` |

The pins were resolved from the corresponding official GitHub Action tags during this change. They still require owner review as source changes before they become trusted production policy.

## Current status and exact limits

- `ci/trusted_qa_runner.py`, `ci/trusted_qa_attestor.py`, and the workflow are source implementations on the development branch. They have not run in GitHub Actions.
- The only ruleset currently returned by the repository API is ruleset `25346465` for `integration/command-center-qa`. It requires `Trusted base scope policy`, not `Trusted Independent QA`.
- The repository default branch is `feature/command-center-four-wave-oms`. No ruleset currently protects that branch. Until it is protected and the workflow source has an independent review, its workflow code cannot be a trusted verifier.
- The approved integration scope assignment currently permits only `CI-PILOT`. The verifier rejects all other assignments. This is intentionally fail-closed; it cannot certify the current feature branch's out-of-scope application changes.
- The runner captures the exact SHA-256 values reported by pip for downloaded wheels, plus the constraints/profile digests. Those wheel hashes are measured at installation time, not preapproved by a hash-locked requirements file; they do not protect against a compromised package index.
- The static `CI-PILOT` ownership epoch in the QA profile is verifier-assignment metadata. It is not a live ownership epoch read from the Windows Task Registry.
- A local run is `CLAIMED_LOCAL`; `trust_vault.py` remains fail-closed for production-trusted acceptance until the hosted workflow is protected, actually run, its GitHub attestation is independently verified, and the trust adapter is connected to a separately protected principal.

## Required owner activation sequence

1. Protect `feature/command-center-four-wave-oms`, the actual default branch, with PR-only changes, one approval from a different write-capable reviewer, stale-review dismissal, last-push approval, and no bypass. Verify the settings through GitHub's API/UI.
2. Review and merge the verifier source into that protected default branch. This review must come from a person other than the PR author.
3. Run the workflow against an approved `CI-PILOT` PR and verify the uploaded signed report with `gh attestation verify --repo nguyenkhiemkhiem079-boop/Command-Center-Sync <report>`. Do not treat a successful signature alone as QA pass; inspect the signed predicate and report bindings.
4. Confirm that the check is attached to the exact tested PR head and the integration base has not moved. Then add the exact `Trusted Independent QA` GitHub Actions check to ruleset `25346465`, preserving the current scope check and one-review/no-bypass rules.
5. Separately approve a new protected-base policy revision for additional task scopes. The current `CI-PILOT`-only policy intentionally rejects every broader source change.
6. Only after an independent reviewer approves the specific source PR and both required checks pass may GitHub permit a merge. Production deployment remains a separate owner decision.

