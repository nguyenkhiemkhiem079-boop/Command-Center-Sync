from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

from ci.verify_trusted_qa_attestation import (
    AttestationVerificationError,
    verify_hosted_report,
)


class TrustedHostedAttestationVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hosted-attestation-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workflow_bytes = b"name: Trusted Independent QA\n"
        self.workflow_sha = "a" * 40
        self.base_sha = "b" * 40
        self.candidate_sha = "c" * 40
        self.report = {
            "repository": "owner/repo", "run_id": "100", "run_attempt": "1",
            "base_sha": self.base_sha, "candidate_sha": self.candidate_sha,
            "workflow_sha": self.workflow_sha,
            "workflow_ref": "owner/repo/.github/workflows/trusted-independent-qa.yml@refs/heads/secure-default",
            "workflow_path": ".github/workflows/trusted-independent-qa.yml",
            "verification_result": "VERIFIED_PASS", "production_trusted": False,
            "approval_status": "PENDING_OWNER_REVIEW", "task_acceptance_state": "PENDING_OWNER_REVIEW",
            "tree_sha": "d" * 40, "profile_digest": "e" * 64, "suite_digest": "f" * 64,
            "workflow_file_sha256": hashlib.sha256(self.workflow_bytes).hexdigest(),
            "repository_id": 123,
            "artifacts": [{"name": "ktool-trusted-qa-log-100-1", "artifact_id": 202,
                           "sha256": "1" * 64, "expired": False}],
        }
        self.archive_path = self.root / "report.zip"
        with zipfile.ZipFile(self.archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("trusted-qa-result.json", json.dumps(self.report).encode("utf-8"))
        self.zip_sha = hashlib.sha256(self.archive_path.read_bytes()).hexdigest()

    def runner(self, *, bad_attestation=False, bad_run=False, bad_ancestry=False):
        calls = []

        def run(argv, **kwargs):
            calls.append(argv)
            if argv[1] == "api" and argv[2] == "repos/owner/repo/actions/runs/100":
                data = {"event": "workflow_dispatch", "run_attempt": 1, "head_branch": "secure-default",
                        "head_sha": self.workflow_sha, "path": ".github/workflows/trusted-independent-qa.yml@refs/heads/secure-default",
                        "status": "completed", "conclusion": "success", "repository": {"id": 123},
                        "html_url": "https://github.com/owner/repo/actions/runs/100"}
                if bad_run:
                    data["head_sha"] = "9" * 40
            elif argv[1] == "api" and "artifacts?per_page=100" in argv[2]:
                data = {"artifacts": [
                    {"id": 201, "name": "trusted-qa-result-100-1", "digest": "sha256:" + self.zip_sha,
                     "expired": False, "workflow_run": {"id": 100}},
                    {"id": 202, "name": "ktool-trusted-qa-log-100-1", "digest": "sha256:" + "1" * 64,
                     "expired": False, "workflow_run": {"id": 100}},
                ]}
            elif argv[1] == "api" and argv[2] == f"repos/owner/repo/git/commits/{self.candidate_sha}":
                data = {"sha": self.candidate_sha, "tree": {"sha": "d" * 40}}
            elif argv[1] == "api" and "compare/" in argv[2]:
                data = {"status": "ahead", "merge_base_commit": {"sha": "9" * 40 if bad_ancestry else self.base_sha}}
            elif argv[1] == "api" and "contents/.github/workflows/trusted-independent-qa.yml" in argv[2]:
                data = {"encoding": "base64", "content": base64.b64encode(self.workflow_bytes).decode("ascii")}
            elif argv[1] == "attestation":
                data = {"returncode": 0, "stdout": "[]" if bad_attestation else '[{"verificationResult":{}}]', "stderr": ""}
                return subprocess.CompletedProcess(argv, **data)
            else:
                raise AssertionError(argv)
            return subprocess.CompletedProcess(argv, 0, json.dumps(data), "")

        return run, calls

    def verify(self, run, **overrides):
        args = {
            "archive_path": self.archive_path, "repository": "owner/repo", "run_id": "100", "attempt": 1,
            "base_sha": self.base_sha, "candidate_sha": self.candidate_sha,
            "workflow_branch": "secure-default", "workflow_sha": self.workflow_sha,
            "expected_result": "VERIFIED_PASS", "run": run,
        }
        args.update(overrides)
        return verify_hosted_report(**args)

    def test_verifies_run_artifact_workflow_bytes_and_signer_constraints(self):
        run, calls = self.runner()
        result = self.verify(run)
        self.assertEqual(result["verification"], "VERIFIED_HOSTED_ATTESTATION")
        self.assertEqual(result["candidate_sha"], self.candidate_sha)
        self.assertEqual(result["report_archive_sha256"], self.zip_sha)
        self.assertEqual(result["report_artifact_id"], 201)
        self.assertFalse(result["production_trusted"])
        attestation_args = next(args for args in calls if args[1] == "attestation")
        self.assertIn("owner/repo/.github/workflows/trusted-independent-qa.yml", attestation_args)
        self.assertIn("--source-digest", attestation_args)
        self.assertIn(self.workflow_sha, attestation_args)

    def test_rejects_wrong_candidate_binding_before_calling_github(self):
        run, calls = self.runner()
        with self.assertRaisesRegex(AttestationVerificationError, "REPORT_BINDING_MISMATCH:candidate_sha"):
            self.verify(run, candidate_sha="9" * 40)
        self.assertEqual(calls, [])

    def test_rejects_run_sha_mismatch(self):
        run, _ = self.runner(bad_run=True)
        with self.assertRaisesRegex(AttestationVerificationError, "WORKFLOW_RUN_IDENTITY_MISMATCH"):
            self.verify(run)

    def test_rejects_candidate_that_does_not_descend_from_expected_base(self):
        run, _ = self.runner(bad_ancestry=True)
        with self.assertRaisesRegex(AttestationVerificationError, "CANDIDATE_BASE_ANCESTRY_MISMATCH"):
            self.verify(run)

    def test_rejects_empty_attestation_verification_result(self):
        run, _ = self.runner(bad_attestation=True)
        with self.assertRaisesRegex(AttestationVerificationError, "ATTESTATION_VERIFICATION_EMPTY"):
            self.verify(run)

    def test_rejects_tampered_archive_bytes(self):
        self.archive_path.write_bytes(self.archive_path.read_bytes() + b"tampered")
        run, _ = self.runner()
        with self.assertRaisesRegex(AttestationVerificationError, "REPORT_ARCHIVE_DIGEST_MISMATCH"):
            self.verify(run)


if __name__ == "__main__":
    unittest.main()
