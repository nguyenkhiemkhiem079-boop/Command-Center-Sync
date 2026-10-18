# SECURITY_QA_EVIDENCE_REPORT — Full Fix delta

Source `552197b91b09c955d0fb48f96e329eba20b98f64`; evidence date18/10/2026. Supersedes earlier progress claims; full acceptance remains false.

Actual adversarial regressions cover role spoofing, cross-store principals, wrong-owner operations, expired/replayed approvals, fabricated Git SHA, incorrect ancestry/tree, tampered profiles/artifacts, stale ownership, symlink/junction paths and fabricated hosted verifier callback. Local matches remain non-production evidence. A malicious process under the same Windows principal can modify local files; SHA256 binds integrity, not independent trust.

New evidence bindings include contract hash, workflow revision, verifier identity and NOT_APPROVED status; worker cannot rebind local evidence APPROVED. Windows ACL fixture removed explicit Everyone access and rejected junction ancestors; live credentials were observed preserved, never copied into Git/logs. New SQLite backup test creates real invalid CHECK data and rejects certification.

Hosted scope pilot now exists: PR1 success/run39133452978, PR2 expected rejection/run39133453324. This is not full protected build provenance. Branch protection awaits GitHub Confirm access; pull_request workflow mutability remains a separate trust limitation. Production QA acceptance stays BLOCKED.
