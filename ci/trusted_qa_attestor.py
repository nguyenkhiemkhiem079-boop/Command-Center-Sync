"""GitHub API binding and result attestation for the trusted hosted QA workflow."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

try:  # Package import in tests; direct-script import in GitHub Actions.
    from .trusted_qa_runner import canonical_json, sha256_file, validate_candidate
except ImportError:
    from trusted_qa_runner import canonical_json, sha256_file, validate_candidate


class GitHubApiError(RuntimeError):
    pass


HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _api(token: str, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = Request(
        "https://api.github.com/" + path.lstrip("/"),
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "KTool-Trusted-QA-Attestor",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
    except (HTTPError, URLError, TimeoutError) as error:
        # Never include request headers or the token in diagnostic output.
        raise GitHubApiError("GITHUB_API_REQUEST_FAILED:" + method + ":" + path.split("?")[0]) from error
    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeError, json.JSONDecodeError) as error:
        raise GitHubApiError("GITHUB_API_RESPONSE_INVALID") from error
    if not isinstance(parsed, dict):
        raise GitHubApiError("GITHUB_API_RESPONSE_SCHEMA")
    return parsed


def validate_dispatch_identity(profile: dict[str, Any], repository: str, env: dict[str, str]) -> None:
    expected_ref = "refs/heads/" + profile["trusted_workflow_branch"]
    expected_workflow_ref = repository + "/.github/workflows/trusted-independent-qa.yml@" + expected_ref
    if env.get("GITHUB_ACTOR") != profile["owner_login"]:
        raise GitHubApiError("DISPATCH_ACTOR_NOT_APPROVED_OWNER")
    if env.get("GITHUB_REF") != expected_ref:
        raise GitHubApiError("WORKFLOW_NOT_RUNNING_FROM_TRUSTED_BRANCH")
    if env.get("GITHUB_WORKFLOW_REF") != expected_workflow_ref:
        raise GitHubApiError("WORKFLOW_REF_MISMATCH")
    workflow_sha = env.get("GITHUB_WORKFLOW_SHA", "")
    if not HEX40.fullmatch(workflow_sha) or not HEX40.fullmatch(env.get("GITHUB_SHA", "")):
        raise GitHubApiError("TRUSTED_WORKFLOW_SHA_MISMATCH")
    if env.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        raise GitHubApiError("UNSUPPORTED_TRIGGER")


def verify_pr_binding(
    token: str,
    repository: str,
    pr_number: int,
    expected_base_sha: str,
    expected_candidate_sha: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    if not HEX40.fullmatch(expected_base_sha) or not HEX40.fullmatch(expected_candidate_sha):
        raise GitHubApiError("IMMUTABLE_SHA_REQUIRED")
    repo_path = quote(repository, safe="/")
    pr = _api(token, "GET", f"repos/{repo_path}/pulls/{pr_number}")
    base = pr.get("base", {})
    head = pr.get("head", {})
    base_repo = base.get("repo") or {}
    head_repo = head.get("repo") or {}
    if pr.get("state") != "open":
        raise GitHubApiError("PULL_REQUEST_NOT_OPEN")
    if base.get("ref") != profile["protected_base_branch"]:
        raise GitHubApiError("PULL_REQUEST_BASE_BRANCH_MISMATCH")
    if base.get("sha") != expected_base_sha:
        raise GitHubApiError("PULL_REQUEST_BASE_SHA_MISMATCH")
    if head.get("sha") != expected_candidate_sha:
        raise GitHubApiError("PULL_REQUEST_CANDIDATE_SHA_MISMATCH")
    if base_repo.get("full_name", "").casefold() != repository.casefold():
        raise GitHubApiError("PULL_REQUEST_BASE_REPOSITORY_MISMATCH")
    if head_repo.get("full_name", "").casefold() != repository.casefold():
        raise GitHubApiError("FORK_CANDIDATE_NOT_SUPPORTED")
    if base_repo.get("id") != head_repo.get("id"):
        raise GitHubApiError("CROSS_REPOSITORY_CANDIDATE_NOT_SUPPORTED")
    branch = _api(token, "GET", f"repos/{repo_path}/branches/{quote(profile['protected_base_branch'], safe='')}")
    if (branch.get("commit") or {}).get("sha") != expected_base_sha:
        raise GitHubApiError("PROTECTED_BASE_MOVED_RESTART_QA")
    owner = (head.get("user") or {}).get("login")
    return {
        "pr_number": pr_number,
        "pr_url": pr.get("html_url"),
        "pr_author": owner,
        "base_branch": base.get("ref"),
        "base_sha": expected_base_sha,
        "candidate_sha": expected_candidate_sha,
        "repository_id": base_repo.get("id"),
        "head_repository_id": head_repo.get("id"),
    }


def list_run_artifacts(token: str, repository: str, run_id: str) -> list[dict[str, Any]]:
    if not run_id.isdigit():
        raise GitHubApiError("INVALID_WORKFLOW_RUN_ID")
    data = _api(token, "GET", f"repos/{quote(repository, safe='/')}/actions/runs/{run_id}/artifacts?per_page=100")
    items = data.get("artifacts")
    if not isinstance(items, list):
        raise GitHubApiError("ARTIFACT_RESPONSE_SCHEMA")
    result = []
    for item in items:
        if item.get("name") != "ktool-trusted-qa-log":
            continue
        digest = item.get("digest", "")
        if not isinstance(digest, str) or not digest.startswith("sha256:") or not HEX64.fullmatch(digest[7:]):
            raise GitHubApiError("ARTIFACT_DIGEST_UNAVAILABLE")
        if item.get("expired") is True:
            raise GitHubApiError("QA_LOG_ARTIFACT_EXPIRED")
        result.append({"name": item["name"], "artifact_id": item.get("id"), "sha256": digest[7:],
                       "size_in_bytes": item.get("size_in_bytes"), "expired": item.get("expired")})
    if not result:
        raise GitHubApiError("QA_LOG_ARTIFACT_MISSING")
    return result


def _load_outputs(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        raise GitHubApiError("QA_COMMAND_OUTPUT_INVALID")
    if not isinstance(value, list):
        raise GitHubApiError("QA_COMMAND_OUTPUT_SCHEMA")
    allowed = {"VENV", "DEPENDENCIES", "DEPENDENCY_INVENTORY", "BUILD", "REGRESSION_TESTS"}
    commands = []
    for item in value:
        if not isinstance(item, dict) or item.get("phase") not in allowed:
            raise GitHubApiError("QA_COMMAND_RECORD_INVALID")
        argv = item.get("argv")
        code = item.get("exit")
        if not isinstance(argv, list) or not argv or any(not isinstance(arg, str) for arg in argv):
            raise GitHubApiError("QA_COMMAND_VECTOR_INVALID")
        if type(code) is not int or code < 0:
            raise GitHubApiError("QA_COMMAND_EXIT_INVALID")
        commands.append({"phase": item["phase"], "argv": argv, "exit_code": code,
                         "elapsed": item.get("elapsed")})
    if len({command["phase"] for command in commands}) != len(commands):
        raise GitHubApiError("QA_COMMAND_DUPLICATE_PHASE")
    required_order = ["VENV", "DEPENDENCIES", "DEPENDENCY_INVENTORY", "BUILD", "REGRESSION_TESTS"]
    full_profile = [command["phase"] for command in commands] == required_order
    return {"commands": commands, "full_profile": full_profile,
            "all_zero": full_profile and all(command["exit_code"] == 0 for command in commands)}


def create_report(
    output_path: str | Path,
    trusted_workflow: str | Path,
    trusted_base: str | Path,
    candidate_repo: str | Path,
    repository: str,
    token: str,
    pr_number: int,
    base_sha: str,
    candidate_sha: str,
    workflow_run_id: str,
    workflow_run_attempt: str,
    test_job_result: str,
    test_step_outcome: str,
    test_exit_code: str,
    command_output: str,
    dependency_evidence_output: str,
    actor: str,
    workflow_ref: str,
    workflow_sha: str,
) -> dict[str, Any]:
    workflow_root = Path(trusted_workflow).resolve(strict=True)
    base_root = Path(trusted_base).resolve(strict=True)
    profile = json.loads((workflow_root / "ci" / "trusted-qa-profile.json").read_text(encoding="utf-8"))
    if not HEX40.fullmatch(workflow_sha):
        raise GitHubApiError("TRUSTED_WORKFLOW_SHA_INVALID")
    binding = verify_pr_binding(token, repository, pr_number, base_sha, candidate_sha, profile)
    inspected = validate_candidate(candidate_repo, base_root, base_sha, candidate_sha,
                                   profile["scope_assignment"], repository, workflow_root)
    commands = _load_outputs(command_output)
    try:
        dependency_evidence = json.loads(dependency_evidence_output)
    except (TypeError, json.JSONDecodeError):
        dependency_evidence = {}
    dependency_valid = (
        isinstance(dependency_evidence, dict) and
        bool(HEX64.fullmatch(str(dependency_evidence.get("pip_report_sha256", "")))) and
        bool(HEX64.fullmatch(str(dependency_evidence.get("freeze_sha256", "")))) and
        isinstance(dependency_evidence.get("installed_packages"), list) and
        isinstance(dependency_evidence.get("artifacts"), list) and bool(dependency_evidence["artifacts"]) and
        any(isinstance(item, str) and item.casefold().startswith("mcp==")
            for item in dependency_evidence.get("installed_packages", [])) and
        any(isinstance(item, dict) and str(item.get("name", "")).casefold() == "mcp"
            for item in dependency_evidence.get("artifacts", [])) and
        all(isinstance(item, dict) and isinstance(item.get("name"), str) and isinstance(item.get("version"), str)
            and bool(HEX64.fullmatch(str(item.get("sha256", ""))))
            and item.get("source_host") in ("pypi.org", "files.pythonhosted.org")
            for item in dependency_evidence["artifacts"])
    )
    try:
        qa_exit = int(test_exit_code)
    except (TypeError, ValueError):
        qa_exit = 2
    workflow_file = workflow_root / ".github" / "workflows" / "trusted-independent-qa.yml"
    if not workflow_file.is_file() or not workflow_ref.endswith("@refs/heads/" + profile["trusted_workflow_branch"]):
        raise GitHubApiError("WORKFLOW_SOURCE_NOT_TRUSTED")
    artifacts = list_run_artifacts(token, repository, workflow_run_id)
    passed = (test_job_result == "success" and test_step_outcome == "success" and qa_exit == 0
              and commands["all_zero"] and dependency_valid)
    for expected_key, output_key in (("tree_sha", "tree_sha"), ("profile_digest", "profile_digest"),
                                     ("suite_digest", "suite_digest")):
        supplied = os.environ.get("QA_" + output_key.upper(), "")
        if supplied != inspected[expected_key]:
            raise GitHubApiError("PRECHECK_OUTPUT_BINDING_MISMATCH:" + output_key)
    output_paths = json.loads(os.environ.get("QA_PATHS_JSON", "[]"))
    if output_paths != inspected["paths"]:
        raise GitHubApiError("PRECHECK_OUTPUT_BINDING_MISMATCH:paths")
    report = {
        "schema_version": 1,
        "mission_id": inspected["mission_id"],
        "task_id": inspected["task_id"],
        "owner": inspected["task_owner"],
        "worker_identity": "UNKNOWN",
        "worker_identity_verification": "NOT_AVAILABLE_FROM_GITHUB_PR",
        "source_submitter": "GITHUB_PR_AUTHOR:" + str(binding["pr_author"] or "UNKNOWN"),
        "workflow_actor": actor,
        "ownership_epoch": inspected["ownership_epoch"],
        "contract_revision": inspected["contract_revision"],
        "contract_hash": inspected["contract_hash"],
        "repository": repository,
        "repository_id": binding["repository_id"],
        "pull_request": binding["pr_number"],
        "base_branch": binding["base_branch"],
        "base_sha": inspected["base_sha"],
        "candidate_sha": inspected["candidate_sha"],
        "tree_sha": inspected["tree_sha"],
        "changed_paths": inspected["paths"],
        "scope_assignment": inspected["scope_assignment"],
        "scope_policy_sha256": inspected["scope_policy_sha256"],
        "qa_profile": profile["profile_id"],
        "profile_digest": inspected["profile_digest"],
        "suite_digest": inspected["suite_digest"],
        "dependency_hashes": inspected["dependency_hashes"],
        "trusted_test_hashes": inspected["test_hashes"],
        "commands": commands["commands"],
        "dependency_evidence": dependency_evidence,
        "test_job_result": test_job_result,
        "test_step_outcome": test_step_outcome,
        "test_exit_code": qa_exit,
        "artifacts": artifacts,
        "workflow_path": ".github/workflows/trusted-independent-qa.yml",
        "workflow_ref": workflow_ref,
        "workflow_sha": workflow_sha,
        "workflow_file_sha256": sha256_file(workflow_file),
        "run_id": workflow_run_id,
        "run_attempt": workflow_run_attempt,
        "runner_identity": "GitHub-hosted windows-2022",
        "verifier_identity": "GitHub Actions separate attestor job",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "verification_result": "VERIFIED_PASS" if passed else (
            "BLOCKED" if test_job_result in ("cancelled", "skipped") or qa_exit == 2 else "VERIFIED_FAIL"
        ),
        "task_acceptance_state": "PENDING_OWNER_REVIEW",
        "approval_status": "PENDING_OWNER_REVIEW",
        "production_trusted": False,
        "notes": [
            "The signed GitHub artifact attestation authenticates this report's provenance; it does not imply owner approval or merge permission.",
            "The fixed CI-PILOT contract and static ownership epoch are verifier assignment metadata, not a live Task Registry ownership claim.",
            "Dependency versions are pinned by the trusted constraints file; package artifact hashes are recorded as a separate supply-chain limitation.",
        ],
    }
    Path(output_path).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def create_check(token: str, repository: str, candidate_sha: str, run_id: str, passed: bool, summary: str) -> dict[str, Any]:
    if not HEX40.fullmatch(candidate_sha) or not run_id.isdigit():
        raise GitHubApiError("CHECK_BINDING_INVALID")
    repo_path = quote(repository, safe="/")
    check_name = "Trusted Independent QA"
    existing = _api(token, "GET", f"repos/{repo_path}/commits/{candidate_sha}/check-runs?check_name={quote(check_name)}&per_page=100")
    matching = [item for item in existing.get("check_runs", [])
                if item.get("name") == check_name and str(item.get("external_id")) == run_id
                and (item.get("app") or {}).get("slug") == "github-actions"]
    conclusion = "success" if passed else "failure"
    payload = {
        "name": check_name,
        "head_sha": candidate_sha,
        "status": "completed",
        "conclusion": conclusion,
        "external_id": run_id,
        "details_url": f"https://github.com/{repository}/actions/runs/{run_id}",
        "output": {"title": "Independent hosted QA " + conclusion.upper(), "summary": summary[:60000]},
    }
    if matching:
        run = _api(token, "PATCH", f"repos/{repo_path}/check-runs/{matching[0]['id']}", payload)
    else:
        run = _api(token, "POST", f"repos/{repo_path}/check-runs", payload)
    if run.get("head_sha") != candidate_sha or run.get("name") != check_name or run.get("conclusion") != conclusion:
        raise GitHubApiError("CREATED_CHECK_RUN_MISMATCH")
    return run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    binding = sub.add_parser("verify-pr")
    binding.add_argument("--workflow-source", required=True)
    binding.add_argument("--repository", required=True)
    binding.add_argument("--pr-number", required=True, type=int)
    binding.add_argument("--base-sha", required=True)
    binding.add_argument("--candidate-sha", required=True)
    attestation = sub.add_parser("create-report")
    for name in ("workflow-source", "trusted-base", "candidate-repo", "repository", "pr-number", "base-sha", "candidate-sha",
                 "run-id", "run-attempt", "test-job-result", "test-step-outcome", "test-exit-code", "commands-json", "dependency-evidence-json", "actor", "workflow-ref", "workflow-sha", "output"):
        attestation.add_argument("--" + name, required=name not in ("commands-json", "dependency-evidence-json"))
    attestation.add_argument("--github-output")
    check = sub.add_parser("create-check")
    check.add_argument("--repository", required=True)
    check.add_argument("--candidate-sha", required=True)
    check.add_argument("--run-id", required=True)
    check.add_argument("--passed", choices=("true", "false"), required=True)
    check.add_argument("--summary", required=True)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("GITHUB_TOKEN_REQUIRED", file=sys.stderr)
        return 2
    try:
        if args.command == "verify-pr":
            workflow = Path(args.workflow_source).resolve(strict=True)
            profile = json.loads((workflow / "ci" / "trusted-qa-profile.json").read_text(encoding="utf-8"))
            validate_dispatch_identity(profile, args.repository, os.environ)
            result = verify_pr_binding(token, args.repository, args.pr_number, args.base_sha, args.candidate_sha, profile)
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "create-report":
            profile = json.loads((Path(args.workflow_source) / "ci" / "trusted-qa-profile.json").read_text(encoding="utf-8"))
            validate_dispatch_identity(profile, args.repository, os.environ)
            report = create_report(args.output, args.workflow_source, args.trusted_base, args.candidate_repo, args.repository, token,
                                   args.pr_number, args.base_sha, args.candidate_sha, args.run_id, args.run_attempt,
                                   args.test_job_result, args.test_step_outcome, args.test_exit_code,
                                   args.commands_json or os.environ.get("QA_COMMANDS_JSON", ""),
                                   args.dependency_evidence_json or os.environ.get("QA_DEPENDENCY_EVIDENCE_JSON", ""),
                                   args.actor, args.workflow_ref, args.workflow_sha)
            report_hash = sha256_file(Path(args.output))
            if args.github_output:
                with Path(args.github_output).open("a", encoding="utf-8") as stream:
                    stream.write("report_sha256=" + report_hash + "\n")
                    stream.write("verification_result=" + report["verification_result"] + "\n")
            print(json.dumps({"verification_result": report["verification_result"], "report_sha256": report_hash,
                              "candidate_sha": report["candidate_sha"], "run_id": report["run_id"]}, indent=2))
            return 0
        created = create_check(token, args.repository, args.candidate_sha, args.run_id,
                               args.passed == "true", args.summary)
        print(json.dumps({"check_run_id": created["id"], "name": created["name"],
                          "head_sha": created["head_sha"], "conclusion": created["conclusion"]}, indent=2))
        return 0
    except Exception as error:
        print(f"ATTESTOR_ERROR:{type(error).__name__}:{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
