"""Independently bind a downloaded hosted-QA report to its GitHub run and attestation.

This verifier does not confer approval or change a check/ruleset. It requires the
GitHub CLI authenticated by the operator and verifies only an already completed
workflow run and the report artifact belonging to that run attempt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable


class AttestationVerificationError(ValueError):
    pass


HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
WORKFLOW_PATH = ".github/workflows/trusted-independent-qa.yml"
REPORT_NAME = "trusted-qa-result.json"


def _gh_json(args: list[str], run: Callable[..., Any]) -> Any:
    result = run(["gh", *args], capture_output=True, text=True, check=False, timeout=60)
    if result.returncode:
        raise AttestationVerificationError("GITHUB_CLI_REQUEST_FAILED:" + args[0])
    try:
        return json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as error:
        raise AttestationVerificationError("GITHUB_CLI_JSON_INVALID:" + args[0]) from error


def _safe_archive_report(archive_path: Path) -> tuple[bytes, str]:
    raw = archive_path.read_bytes()
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            if len(names) != 1 or names[0] != REPORT_NAME:
                raise AttestationVerificationError("REPORT_ARCHIVE_CONTENTS_INVALID")
            info = archive.getinfo(REPORT_NAME)
            if info.is_dir() or info.file_size > 2_000_000:
                raise AttestationVerificationError("REPORT_ARCHIVE_SIZE_INVALID")
            report_bytes = archive.read(REPORT_NAME)
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise AttestationVerificationError("REPORT_ARCHIVE_INVALID") from error
    return report_bytes, hashlib.sha256(raw).hexdigest()


def _validate_report_bindings(
    report: dict[str, Any], *, repository: str, run_id: str, attempt: int,
    base_sha: str, candidate_sha: str, workflow_branch: str, workflow_sha: str,
    expected_result: str,
) -> None:
    expected = {
        "repository": repository,
        "run_id": run_id,
        "run_attempt": str(attempt),
        "base_sha": base_sha,
        "candidate_sha": candidate_sha,
        "workflow_sha": workflow_sha,
        "workflow_ref": f"{repository}/{WORKFLOW_PATH}@refs/heads/{workflow_branch}",
        "workflow_path": WORKFLOW_PATH,
        "verification_result": expected_result,
        "production_trusted": False,
        "approval_status": "PENDING_OWNER_REVIEW",
        "task_acceptance_state": "PENDING_OWNER_REVIEW",
    }
    for key, value in expected.items():
        if report.get(key) != value:
            raise AttestationVerificationError("REPORT_BINDING_MISMATCH:" + key)
    if not HEX40.fullmatch(base_sha) or not HEX40.fullmatch(candidate_sha) or not HEX40.fullmatch(workflow_sha):
        raise AttestationVerificationError("INVALID_IMMUTABLE_SHA")
    if not HEX40.fullmatch(str(report.get("tree_sha", ""))):
        raise AttestationVerificationError("REPORT_TREE_SHA_INVALID")
    for key in ("profile_digest", "suite_digest", "workflow_file_sha256"):
        if not HEX64.fullmatch(str(report.get(key, ""))):
            raise AttestationVerificationError("REPORT_DIGEST_INVALID:" + key)


def verify_hosted_report(
    archive_path: str | Path, *, repository: str, run_id: str, attempt: int,
    base_sha: str, candidate_sha: str, workflow_branch: str, workflow_sha: str,
    expected_result: str, run: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise AttestationVerificationError("REPOSITORY_ID_INVALID")
    if not run_id.isdigit() or attempt < 1 or expected_result not in ("VERIFIED_PASS", "VERIFIED_FAIL"):
        raise AttestationVerificationError("RUN_BINDING_INVALID")
    path = Path(archive_path).resolve(strict=True)
    report_bytes, archive_sha256 = _safe_archive_report(path)
    try:
        report = json.loads(report_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise AttestationVerificationError("REPORT_JSON_INVALID") from error
    if not isinstance(report, dict):
        raise AttestationVerificationError("REPORT_JSON_SCHEMA_INVALID")
    _validate_report_bindings(
        report, repository=repository, run_id=run_id, attempt=attempt,
        base_sha=base_sha, candidate_sha=candidate_sha, workflow_branch=workflow_branch,
        workflow_sha=workflow_sha, expected_result=expected_result,
    )

    run_data = _gh_json(["api", f"repos/{repository}/actions/runs/{run_id}"], run)
    if not isinstance(run_data, dict):
        raise AttestationVerificationError("WORKFLOW_RUN_SCHEMA_INVALID")
    if (run_data.get("event") != "workflow_dispatch" or run_data.get("run_attempt") != attempt
            or run_data.get("head_branch") != workflow_branch or run_data.get("head_sha") != workflow_sha
            or not str(run_data.get("path", "")).startswith(WORKFLOW_PATH)):
        raise AttestationVerificationError("WORKFLOW_RUN_IDENTITY_MISMATCH")
    expected_conclusion = "success" if expected_result == "VERIFIED_PASS" else "failure"
    if run_data.get("status") != "completed" or run_data.get("conclusion") != expected_conclusion:
        raise AttestationVerificationError("WORKFLOW_RUN_CONCLUSION_MISMATCH")
    run_repo = run_data.get("repository") or {}
    if not isinstance(run_repo, dict) or (report.get("repository_id") and run_repo.get("id") != report["repository_id"]):
        raise AttestationVerificationError("WORKFLOW_RUN_REPOSITORY_MISMATCH")

    candidate_commit = _gh_json(["api", f"repos/{repository}/git/commits/{candidate_sha}"], run)
    candidate_tree = ((candidate_commit.get("tree") or {}).get("sha")
                      if isinstance(candidate_commit, dict) else None)
    if (not isinstance(candidate_commit, dict) or candidate_commit.get("sha") != candidate_sha
            or candidate_tree != report["tree_sha"]):
        raise AttestationVerificationError("CANDIDATE_COMMIT_OR_TREE_MISMATCH")
    comparison = _gh_json([
        "api", f"repos/{repository}/compare/{base_sha}...{candidate_sha}"
    ], run)
    if (not isinstance(comparison, dict) or comparison.get("status") != "ahead"
            or (comparison.get("merge_base_commit") or {}).get("sha") != base_sha):
        raise AttestationVerificationError("CANDIDATE_BASE_ANCESTRY_MISMATCH")

    artifacts_data = _gh_json(["api", f"repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100"], run)
    artifacts = artifacts_data.get("artifacts") if isinstance(artifacts_data, dict) else None
    if not isinstance(artifacts, list):
        raise AttestationVerificationError("ARTIFACT_LIST_SCHEMA_INVALID")
    report_artifact_name = f"trusted-qa-result-{run_id}-{attempt}"
    report_artifacts = [item for item in artifacts if isinstance(item, dict) and item.get("name") == report_artifact_name]
    if len(report_artifacts) != 1:
        raise AttestationVerificationError("REPORT_ARTIFACT_NOT_UNIQUE")
    artifact = report_artifacts[0]
    api_digest = str(artifact.get("digest", ""))
    if artifact.get("expired") is True or not api_digest.startswith("sha256:") or not HEX64.fullmatch(api_digest[7:]):
        raise AttestationVerificationError("REPORT_ARTIFACT_DIGEST_UNAVAILABLE")
    if archive_sha256 != api_digest[7:]:
        raise AttestationVerificationError("REPORT_ARCHIVE_DIGEST_MISMATCH")
    artifact_run = artifact.get("workflow_run") or {}
    if not isinstance(artifact_run, dict) or artifact_run.get("id", int(run_id)) != int(run_id):
        raise AttestationVerificationError("REPORT_ARTIFACT_RUN_MISMATCH")

    api_workflow = _gh_json([
        "api", f"repos/{repository}/contents/{WORKFLOW_PATH}?ref={workflow_sha}"
    ], run)
    if not isinstance(api_workflow, dict) or api_workflow.get("encoding") != "base64":
        raise AttestationVerificationError("WORKFLOW_SOURCE_UNAVAILABLE")
    import base64
    try:
        workflow_bytes = base64.b64decode(api_workflow.get("content", ""), validate=False)
    except (ValueError, TypeError) as error:
        raise AttestationVerificationError("WORKFLOW_SOURCE_INVALID") from error
    workflow_digest = hashlib.sha256(workflow_bytes).hexdigest()
    if workflow_digest != report["workflow_file_sha256"]:
        raise AttestationVerificationError("WORKFLOW_FILE_DIGEST_MISMATCH")

    signer = f"{repository}/{WORKFLOW_PATH}"
    with tempfile.TemporaryDirectory(prefix="ktool-attestation-verify-") as temporary:
        extracted_report = Path(temporary) / REPORT_NAME
        extracted_report.write_bytes(report_bytes)
        attestation_args = [
            "attestation", "verify", str(extracted_report), "--repo", repository,
            "--signer-workflow", signer,
            "--source-ref", f"refs/heads/{workflow_branch}",
            "--source-digest", workflow_sha, "--format", "json",
        ]
        result = run(["gh", *attestation_args], capture_output=True, text=True, check=False, timeout=120)
    if result.returncode:
        raise AttestationVerificationError("GITHUB_ATTESTATION_VERIFY_FAILED")
    try:
        verified = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as error:
        raise AttestationVerificationError("ATTESTATION_VERIFICATION_OUTPUT_INVALID") from error
    if not isinstance(verified, list) or not verified:
        raise AttestationVerificationError("ATTESTATION_VERIFICATION_EMPTY")

    log_name = f"ktool-trusted-qa-log-{run_id}-{attempt}"
    log_artifacts = [item for item in artifacts if isinstance(item, dict) and item.get("name") == log_name]
    if len(log_artifacts) != 1 or log_artifacts[0].get("expired") is True:
        raise AttestationVerificationError("QA_LOG_ARTIFACT_NOT_UNIQUE")
    log_digest = str(log_artifacts[0].get("digest", ""))
    if not log_digest.startswith("sha256:") or not HEX64.fullmatch(log_digest[7:]):
        raise AttestationVerificationError("QA_LOG_ARTIFACT_DIGEST_UNAVAILABLE")
    report_artifacts_binding = report.get("artifacts")
    if not isinstance(report_artifacts_binding, list) or not any(
        isinstance(item, dict) and item.get("name") == log_name
        and item.get("artifact_id") == log_artifacts[0].get("id")
        and item.get("sha256") == log_digest[7:]
        for item in report_artifacts_binding
    ):
        raise AttestationVerificationError("QA_LOG_ARTIFACT_BINDING_MISMATCH")
    return {
        "verification": "VERIFIED_HOSTED_ATTESTATION",
        "repository": repository,
        "run_id": run_id,
        "run_attempt": attempt,
        "run_url": run_data.get("html_url"),
        "workflow_sha": workflow_sha,
        "workflow_file_sha256": workflow_digest,
        "candidate_sha": candidate_sha,
        "base_sha": base_sha,
        "report_artifact_id": artifact.get("id"),
        "report_archive_sha256": archive_sha256,
        "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "qa_log_artifact_id": log_artifacts[0].get("id"),
        "qa_log_artifact_sha256": log_digest[7:],
        "attestation_entries_verified": len(verified),
        "qa_result": expected_result,
        "approval_status": report["approval_status"],
        "production_trusted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, help="Downloaded report artifact ZIP")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--attempt", required=True, type=int)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--workflow-branch", required=True)
    parser.add_argument("--workflow-sha", required=True)
    parser.add_argument("--expected-result", choices=("VERIFIED_PASS", "VERIFIED_FAIL"), required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify_hosted_report(
            args.archive, repository=args.repository, run_id=args.run_id, attempt=args.attempt,
            base_sha=args.base_sha, candidate_sha=args.candidate_sha,
            workflow_branch=args.workflow_branch, workflow_sha=args.workflow_sha,
            expected_result=args.expected_result,
        ), indent=2))
        return 0
    except Exception as error:
        print(f"ATTESTATION_VERIFY_ERROR:{type(error).__name__}:{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
