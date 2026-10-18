# Hosted QA provenance verification

## What the current workflow proves

`Trusted Independent QA` is a manually dispatched hosted Windows workflow with separate preflight, test, and attestor jobs. The candidate job checks out candidate Git objects but does not run candidate-owned test files, build scripts, dependency configuration, or workflow code. It materializes candidate files into a temporary overlay, replaces its tests with the test suite pinned from the trusted workflow revision, and runs without repository write credentials or secrets. The attestor runs in a separate job, recomputes candidate identity and scope, binds the pull request and protected base SHA, then publishes a check on the exact candidate SHA.

The dependency input is a Windows CPython 3.12 wheel lock. Every package has one exact version and one SHA-256 hash. Installation uses binary wheels only, `--require-hashes`, `--no-deps`, `--no-cache-dir`, and `--force-reinstall`; the runner records the pip install report, installed package inventory, and their digests. Python is pinned to the 3.12 minor line and the hosted `windows-2022` image remains a moving provider image; those are residual reproducibility limits.

The attestor report is signed before upload. The report artifact name includes both run ID and attempt. The independent post-run verifier compares the downloaded ZIP digest with the GitHub artifact API, checks exact run/attempt/event/branch/workflow SHA and conclusion, retrieves and hashes the workflow file at that immutable SHA, compares candidate/base/report bindings, verifies the exact report subject using `gh attestation verify` with repository, signer workflow, source ref and source digest constraints, and binds the run-specific log artifact ID and digest.

## Operator verification procedure

After a hosted run is available, download the `trusted-qa-result-<run-id>-<attempt>` ZIP from that exact run. Keep the original ZIP unchanged. Run:

```powershell
python ci/verify_trusted_qa_attestation.py `
  --archive C:\path\to\trusted-qa-result-<run-id>-<attempt>.zip `
  --repository nguyenkhiemkhiem079-boop/Command-Center-Sync `
  --run-id <run-id> --attempt <attempt> `
  --base-sha <protected-base-sha> --candidate-sha <candidate-sha> `
  --workflow-branch feature/command-center-four-wave-oms `
  --workflow-sha <workflow-sha> --expected-result VERIFIED_PASS
```

The verifier requires an authenticated GitHub CLI and fails closed on mismatch, missing API data, expired/ambiguous artifacts, wrong report binding, wrong workflow bytes, failed attestation verification, or an empty verification result. It does not change repository settings, create approvals, or mark a task accepted. A `VERIFIED_FAIL` report is valid provenance for a negative test only when the exact run concludes failure and the report itself records `VERIFIED_FAIL`.

## Current verification state

- Local runner/attestor tests and synthetic API/CLI response tests are local regression evidence only.
- Hash-lock installation was tested against the locally downloaded Windows wheelhouse; this is not GitHub-hosted execution evidence.
- The repository currently has no live hosted QA run for this verifier and no artifact attestation to validate.
- Do not make `Trusted Independent QA` a required integration check until an owner-reviewed workflow and policy revision has produced one positive hosted result, one intentional rejected negative result, and independently verified reports for their exact inputs.
- A verified artifact establishes provenance for that artifact and workflow identity. It does not establish source trust for a same-user process, task acceptance, merge authorization, or production readiness.
