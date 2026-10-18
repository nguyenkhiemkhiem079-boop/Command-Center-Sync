# Protected integration and independent reviewer strategy

## Verified controls

GitHub API read of Ruleset `25346465` on 2026-10-18 returned:

- Active target: `refs/heads/integration/command-center-qa`.
- No bypass actors; current user bypass is `never`.
- Required check: `Trusted base scope policy` from GitHub Actions integration `15368`, with strict up-to-date policy.
- Pull requests required, one approving review, stale reviews dismissed on push, and approval required from someone other than the last pusher.
- Deletion and non-fast-forward updates are blocked.

The repository ruleset listing contains only this one ruleset. The default branch `feature/command-center-four-wave-oms` is not protected by a ruleset. Do not store trusted verifier configuration there until a distinct reviewer and branch protection are in place.

## Reviewer separation

The PR author cannot satisfy the one-approval rule. Assign a second person with repository write access (not necessarily administrator) as the independent reviewer. That person reviews the actual diff, workflow/profile changes, test provenance, scope, and report. A new commit dismisses the prior approval and requires that reviewer to approve the current head again. Codex and Antigravity workers do not count as the owner reviewer and cannot approve their own work.

If there is no second qualified write-capable collaborator, the PR remains blocked. Do not lower the review count, disable stale-review dismissal, grant a bypass role, use auto-merge, or count an owner self-review.

## QA check ordering

Keep `Trusted base scope policy` as the narrow source boundary gate. Add `Trusted Independent QA` as a second required check only after the workflow is present on the protected default branch and a real signed run against the exact candidate SHA has been independently verified. The required QA check must be emitted by the GitHub Actions app and attached to the exact current PR head. If the protected base advances during QA, discard that result and rerun.

## Protected-scope bootstrap deadlock

The existing integration policy permits only `CI-PILOT` and protects `.github` and core verifier files. The required scope workflow hard-codes `CI-PILOT`. A PR that adds the hosted verifier, changes the policy, or broadens allowed paths fails the existing trusted scope gate by design. Therefore the current ruleset cannot be used to merge its own scope-policy/verifier update. The correct next architecture decision is a reviewed migration to a new versioned protected integration baseline, with its owner-approved policy and required checks installed before it becomes the integration target. Keep the current branch and ruleset intact until the new target has been reviewed and validated. Do not solve this by temporarily disabling the ruleset or adding a bypass actor.

## Exact owner actions still required

1. Add an independent qualified reviewer with write permission if one is not already available.
2. Protect the repository's actual default branch before using it as a workflow trust root.
3. Approve a versioned protected-base migration that can add the verifier and new task scopes without weakening the current active integration branch.
4. After a real attested run, add `Trusted Independent QA` to the integration ruleset and retain all existing required controls.

No merge or release is authorized by this strategy.

