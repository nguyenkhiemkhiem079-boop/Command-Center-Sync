# Trusted Hosted QA — validation evidence

## Candidate validation

- Source branch: `feature/full-fix-e2e-acceptance`.
- Starting commit: `eb87bbed0f435585c035807fda320b9a4087095e`.
- Full Windows regression: `python -m unittest discover -s tests -p 'test_*.py' -v` — **210 passed**, 191.949 seconds, exit 0. Captured at `%TEMP%\ktool-final-regression-20261018.txt`.
- Focused verifier tests: `python -m unittest discover -s tests -p 'test_trusted_qa_runner.py' -v` — **14 passed**, 15.539 seconds, exit 0.
- Python bytecode compilation: `python -m compileall -q ci tests/test_trusted_qa_runner.py` — exit 0.
- Workflow syntax: parsed with `yaml@2.8.1`; jobs `preflight`, `qa`, and `attest` recognized.
- Whitespace check: `git diff --check` — exit 0.
- 42 partial-feature rows individually reviewed in `docs/master-v1/42_PARTIAL_AUDIT.md`.

The full regression and the focused test are local execution under the same Windows principal. They are not protected hosted CI, independent production QA, Antigravity Self-QA, or Revit-host evidence.

## GitHub controls separately verified

Owner-confirmed evidence: Ruleset `25346465` protects `integration/command-center-qa`; PR #1 passed the scope pilot and PR #2 was rejected for `OUT_OF_SCOPE` and `PROTECTED_PATH`. Existing required check, review, no-bypass, deletion and non-fast-forward controls are preserved. This verifies path scope and branch protection only; it does not verify build/test provenance.

## Hosted verifier status

`trusted-independent-qa.yml` and its runner/attestor are implemented and locally adversarial-tested, but no GitHub Actions execution or signed report exists. `Trusted Independent QA` is not a required integration check. The actual default branch remains unprotected, and the current integration policy intentionally permits only `CI-PILOT` while protecting verifier/workflow paths. Enabling this workflow therefore requires an independently reviewed protected trust root and an approved versioned policy migration. No rule was bypassed to bootstrap it.

The hosted runner report leaves task acceptance and owner approval pending. `trust_vault.py` remains fail-closed for production trust. The report records provider identity as `UNKNOWN`; it cannot certify actual worker identity from PR metadata.

## Runtime / deployment boundary

No source was deployed to the live `127.0.0.1:8876` service, and no production Registry or credential store was changed. No live Antigravity session was launched or fabricated. Two real Teamwork sessions remain **BLOCKED** pending permitted, supervised operator evidence. Production QA, protected merge, release and Revit 2025 runtime remain **NOT_EXECUTED**.
