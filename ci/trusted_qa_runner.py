"""Run the immutable QA profile against a candidate as untrusted source data.

The trusted script and test suite must be checked out from the protected workflow
and base revisions. Candidate-controlled test files and scripts are never run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.parse import urlparse


class VerificationError(ValueError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _clean_env() -> dict[str, str]:
    """Keep only ordinary Windows runtime variables; never pass GitHub credentials to tests."""
    allowed = {
        "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP",
        "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
        "NUMBER_OF_PROCESSORS",
    }
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}


def _run_git(repo: Path, *args: str) -> bytes:
    env = _clean_env()
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE", "GIT_EXTERNAL_DIFF"):
        env.pop(key, None)
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=False,
        timeout=60, env=env,
    )
    if result.returncode:
        raise VerificationError("GIT_COMMAND_FAILED:" + " ".join(args[:2]))
    return result.stdout


def _validate_git_path(raw: str) -> str:
    if not raw or "\\" in raw or ":" in raw or raw.startswith("/"):
        raise VerificationError("NONCANONICAL_GIT_PATH")
    pure = PurePosixPath(raw)
    if pure.as_posix() != raw:
        raise VerificationError("NONCANONICAL_GIT_PATH")
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise VerificationError("PATH_TRAVERSAL")
    for part in pure.parts:
        if PureWindowsPath(part).is_reserved() or part.endswith((" ", ".")):
            raise VerificationError("WINDOWS_PATH_ALIAS")
        if any(char in part for char in '<>:"|?*'):
            raise VerificationError("WINDOWS_INVALID_PATH")
    if pure.parts[0].casefold() == ".git":
        raise VerificationError("GIT_METADATA_IN_TREE")
    return pure.as_posix()


def _tree_entries(repo: Path, commit: str) -> list[tuple[str, str]]:
    raw = _run_git(repo, "ls-tree", "-r", "-z", commit)
    entries: list[tuple[str, str]] = []
    seen_casefold: set[str] = set()
    original_prefixes: dict[str, str] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, path_raw = record.split(b"\t", 1)
        mode, kind, object_sha = metadata.decode("ascii").split()
        path = _validate_git_path(path_raw.decode("utf-8", "strict"))
        if mode not in ("100644", "100755") or kind != "blob":
            raise VerificationError("UNSUPPORTED_GIT_ENTRY:" + path)
        folded = path.casefold()
        if folded in seen_casefold:
            raise VerificationError("CASE_INSENSITIVE_PATH_COLLISION")
        seen_casefold.add(folded)
        prefix_parts: list[str] = []
        for part in PurePosixPath(path).parts:
            prefix_parts.append(part)
            prefix = "/".join(prefix_parts)
            previous = original_prefixes.get(prefix.casefold())
            if previous is not None and previous != prefix:
                raise VerificationError("CASE_INSENSITIVE_DIRECTORY_ALIAS")
            original_prefixes[prefix.casefold()] = prefix
        entries.append((path, object_sha))
    return entries


def _git_path_list(repo: Path, base_sha: str, candidate_sha: str) -> list[str]:
    raw = _run_git(repo, "diff", "--no-ext-diff", "--no-textconv", "--name-only", "--no-renames", "-z", base_sha, candidate_sha, "--")
    return sorted(_validate_git_path(item.decode("utf-8", "strict")) for item in raw.split(b"\0") if item)


def _tree_sha(repo: Path, commit: str) -> str:
    value = _run_git(repo, "rev-parse", "--verify", commit + "^{tree}").decode("ascii").strip()
    if len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
        raise VerificationError("INVALID_TREE_SHA")
    return value


def validate_candidate(
    repo_path: str | Path,
    trusted_base_path: str | Path,
    base_sha: str,
    candidate_sha: str,
    assignment: str,
    repository: str,
    trusted_workflow_path: str | Path | None = None,
) -> dict[str, Any]:
    repo = Path(repo_path).resolve(strict=True)
    trusted_base = Path(trusted_base_path).resolve(strict=True)
    trusted_workflow = Path(trusted_workflow_path or trusted_base).resolve(strict=True)
    if not (repo / ".git").exists() and not (repo / ".git").is_file():
        raise VerificationError("CANDIDATE_GIT_CHECKOUT_REQUIRED")
    if not (trusted_base / ".git").exists() and not (trusted_base / ".git").is_file():
        raise VerificationError("TRUSTED_BASE_GIT_CHECKOUT_REQUIRED")
    for value in (base_sha, candidate_sha):
        if len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
            raise VerificationError("IMMUTABLE_COMMIT_SHA_REQUIRED")
        resolved = _run_git(repo, "rev-parse", "--verify", value + "^{commit}").decode("ascii").strip()
        if resolved != value:
            raise VerificationError("COMMIT_IDENTITY_MISMATCH")
    head = _run_git(repo, "rev-parse", "HEAD").decode("ascii").strip()
    if head != candidate_sha:
        raise VerificationError("CHECKOUT_NOT_AT_CANDIDATE")
    if _run_git(repo, "merge-base", "--is-ancestor", base_sha, candidate_sha) is None:
        raise VerificationError("BASE_ANCESTRY_FAILED")
    # Git exits nonzero for false ancestry; _run_git already enforces that.
    base_entries = _tree_entries(repo, base_sha)
    candidate_entries = _tree_entries(repo, candidate_sha)
    paths = _git_path_list(repo, base_sha, candidate_sha)
    if not paths:
        raise VerificationError("EMPTY_CANDIDATE_DIFF")

    policy_path = trusted_base / ".github" / "scope-policy.json"
    profile_path = trusted_workflow / "ci" / "trusted-qa-profile.json"
    if not policy_path.is_file() or not profile_path.is_file():
        raise VerificationError("TRUSTED_POLICY_OR_PROFILE_MISSING")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    required_profile_keys = {
        "schema_version", "profile_id", "python_version", "runner", "owner_login", "protected_base_branch",
        "trusted_workflow_branch", "trusted_check_name", "scope_assignment", "mission_id", "task_id",
        "task_owner", "ownership_epoch", "contract_revision", "acceptance_criteria", "dependency_files",
        "test_files", "timeouts_seconds",
    }
    if set(profile) != required_profile_keys or profile.get("schema_version") != 1:
        raise VerificationError("TRUSTED_PROFILE_SCHEMA_INVALID")
    if profile.get("scope_assignment") != assignment:
        raise VerificationError("PROFILE_ASSIGNMENT_MISMATCH")
    if (not isinstance(profile.get("ownership_epoch"), int) or profile["ownership_epoch"] < 1 or
            not isinstance(profile.get("acceptance_criteria"), list) or not profile["acceptance_criteria"]):
        raise VerificationError("TRUSTED_PROFILE_BINDINGS_INVALID")
    if profile["dependency_files"] != ["requirements.txt", "constraints-windows-py312.txt"]:
        raise VerificationError("DEPENDENCY_FILE_SET_NOT_APPROVED")
    if not isinstance(profile.get("test_files"), list) or len(profile["test_files"]) != len(set(profile["test_files"])):
        raise VerificationError("TRUSTED_TEST_LIST_INVALID")
    for rel in profile["test_files"]:
        normalized = _validate_git_path(rel)
        if normalized != rel or len(PurePosixPath(rel).parts) != 2 or not PurePosixPath(rel).name.startswith("test_") or not rel.endswith(".py"):
            raise VerificationError("TRUSTED_TEST_PATH_INVALID")
    # This checker and its policy are loaded only from the trusted base checkout.
    trusted_scope_checker = trusted_base / "ci_scope_gate.py"
    trusted_registry = trusted_base / "registry.py"
    if not trusted_scope_checker.is_file() or not trusted_registry.is_file():
        raise VerificationError("TRUSTED_SCOPE_CHECKER_MISSING")
    bootstrap = (
        "import runpy,sys; base=sys.argv.pop(1); script=sys.argv.pop(1); "
        "sys.path.insert(0,base); sys.argv=[script,*sys.argv[1:]]; "
        "runpy.run_path(script,run_name='__main__')"
    )
    checker_run = subprocess.run(
        [sys.executable, "-I", "-c", bootstrap, str(trusted_base), str(trusted_scope_checker),
         "--repo", str(repo), "--base", base_sha, "--commit", candidate_sha,
         "--policy", str(policy_path), "--assignment", assignment, "--repository", repository],
        cwd=str(trusted_base), capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False, timeout=90, env=_clean_env(),
    )
    if checker_run.returncode:
        raise VerificationError("TRUSTED_SCOPE_POLICY_REJECTED:" + checker_run.stderr[:400])
    try:
        scope = json.loads(checker_run.stdout)
    except json.JSONDecodeError as error:
        raise VerificationError("TRUSTED_SCOPE_CHECKER_OUTPUT_INVALID") from error
    if not scope.get("pass"):
        raise VerificationError("TRUSTED_SCOPE_POLICY_REJECTED")

    profile_bytes = profile_path.read_bytes()
    policy_bytes = policy_path.read_bytes()
    dependency_hashes = {
        rel: sha256_file(trusted_workflow / rel)
        for rel in profile["dependency_files"]
    }
    test_hashes = {}
    for rel in profile["test_files"]:
        test_path = trusted_workflow / rel
        if not test_path.is_file() or test_path.is_symlink():
            raise VerificationError("TRUSTED_TEST_FILE_MISSING_OR_LINK:" + rel)
        test_hashes[rel] = sha256_file(test_path)
    suite_payload = {
        "test_files": test_hashes,
        "dependency_files": dependency_hashes,
        "entrypoint_sha256": sha256_file(trusted_workflow / "ci" / "trusted_qa_suite_entry.py"),
        "runner_sha256": sha256_file(trusted_workflow / "ci" / "trusted_qa_runner.py"),
        "attestor_sha256": sha256_file(trusted_workflow / "ci" / "trusted_qa_attestor.py"),
        "trusted_scope_checker_sha256": sha256_file(trusted_base / "ci_scope_gate.py"),
        "trusted_registry_sha256": sha256_file(trusted_base / "registry.py"),
        "workflow_file_sha256": sha256_file(trusted_workflow / ".github" / "workflows" / "trusted-independent-qa.yml")
        if (trusted_workflow / ".github" / "workflows" / "trusted-independent-qa.yml").is_file() else None,
        "profile_schema_version": profile["schema_version"],
    }
    assignment_policy = policy["assignments"][assignment]
    contract_hash = sha256_bytes(canonical_json({
        "mission_id": profile["mission_id"],
        "task_id": profile["task_id"],
        "owner": profile["task_owner"],
        "ownership_epoch": profile["ownership_epoch"],
        "contract_revision": profile["contract_revision"],
        "acceptance_criteria": profile["acceptance_criteria"],
        "assignment_policy": assignment_policy,
        "protected_paths": policy["protected_paths"],
    }))
    return {
        "repository": repository,
        "base_sha": base_sha,
        "candidate_sha": candidate_sha,
        "tree_sha": _tree_sha(repo, candidate_sha),
        "paths": paths,
        "scope_assignment": assignment,
        "scope_policy_sha256": sha256_bytes(policy_bytes),
        "profile_digest": sha256_bytes(profile_bytes),
        "suite_digest": sha256_bytes(canonical_json(suite_payload)),
        "dependency_hashes": dependency_hashes,
        "test_hashes": test_hashes,
        "mission_id": profile["mission_id"],
        "task_id": profile["task_id"],
        "task_owner": profile["task_owner"],
        "ownership_epoch": profile["ownership_epoch"],
        "contract_revision": profile["contract_revision"],
        "contract_hash": contract_hash,
        "workflow_revision": sha256_file(trusted_workflow / ".github" / "workflows" / "trusted-independent-qa.yml")
        if (trusted_workflow / ".github" / "workflows" / "trusted-independent-qa.yml").is_file() else None,
        "scope": scope,
        "_profile": profile,
        "_trusted_workflow": trusted_workflow,
        "_base_entries": base_entries,
        "_candidate_entries": candidate_entries,
    }


def materialize_overlay(repo_path: str | Path, candidate_sha: str, trusted_workflow_path: str | Path, test_hashes: dict[str, str], target: str | Path) -> Path:
    repo = Path(repo_path).resolve(strict=True)
    trusted_workflow = Path(trusted_workflow_path).resolve(strict=True)
    overlay = Path(target).resolve()
    overlay.mkdir(parents=True, exist_ok=False)
    for rel, object_sha in _tree_entries(repo, candidate_sha):
        relative = Path(*PurePosixPath(rel).parts)
        destination = overlay / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.resolve(strict=False).is_relative_to(overlay):
            raise VerificationError("MATERIALIZATION_ESCAPED_ROOT")
        blob = _run_git(repo, "cat-file", "blob", object_sha)
        destination.write_bytes(blob)
    # Remove all candidate-provided test inputs and install only the pinned base suite.
    candidate_tests = overlay / "tests"
    if candidate_tests.exists():
        shutil.rmtree(candidate_tests)
    candidate_tests.mkdir(parents=True)
    for rel, expected_hash in test_hashes.items():
        source = trusted_workflow / rel
        if sha256_file(source) != expected_hash:
            raise VerificationError("TRUSTED_TEST_CHANGED_DURING_RUN")
        destination = overlay / Path(*PurePosixPath(rel).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    (candidate_tests / "__init__.py").write_text('"""Protected test suite package overlay."""\n', encoding="utf-8")
    return overlay


def _run_command(argv: list[str], cwd: Path, timeout: int, log_file) -> tuple[int, str, str]:
    start = time.time()
    log_file.write("$ " + json.dumps(argv, ensure_ascii=False) + "\n")
    result = subprocess.run(
        argv, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, check=False, env=_clean_env(),
    )
    log_file.write(result.stdout)
    log_file.write(result.stderr)
    log_file.flush()
    return result.returncode, f"{time.time() - start:.3f}s", result.stdout


def _pip_artifact_evidence(report_path: Path, freeze_output: str) -> dict[str, Any]:
    if not report_path.is_file():
        raise VerificationError("PIP_INSTALL_REPORT_MISSING")
    raw = report_path.read_bytes()
    report = json.loads(raw.decode("utf-8"))
    installs = report.get("install")
    if not isinstance(installs, list) or not installs:
        raise VerificationError("PIP_INSTALL_REPORT_EMPTY")
    artifacts = []
    for item in installs:
        metadata = item.get("metadata") or {}
        download = item.get("download_info") or {}
        archive = download.get("archive_info") or {}
        hashes = archive.get("hashes") or {}
        digest = hashes.get("sha256")
        url = download.get("url", "")
        host = urlparse(url).hostname or ""
        if (not isinstance(metadata.get("name"), str) or not isinstance(metadata.get("version"), str) or
                not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest) or
                urlparse(url).scheme != "https" or host not in ("pypi.org", "files.pythonhosted.org")):
            raise VerificationError("UNVERIFIED_PIP_ARTIFACT")
        artifacts.append({"name": metadata["name"], "version": metadata["version"], "sha256": digest, "source_host": host})
    artifacts.sort(key=lambda item: item["name"].casefold())
    installed_packages = sorted(line.strip() for line in freeze_output.splitlines() if line.strip())
    return {"pip_report_sha256": sha256_bytes(raw), "freeze_sha256": sha256_bytes(freeze_output.encode("utf-8")),
            "installed_packages": installed_packages, "artifacts": artifacts}


def run_profile(
    candidate_repo: str | Path,
    trusted_base: str | Path,
    base_sha: str,
    candidate_sha: str,
    assignment: str,
    repository: str,
    report_path: str | Path,
    log_path: str | Path,
    install_dependencies: bool = False,
    trusted_workflow_path: str | Path | None = None,
) -> dict[str, Any]:
    candidate_repo = Path(candidate_repo).resolve(strict=True)
    trusted_base = Path(trusted_base).resolve(strict=True)
    trusted_workflow = Path(trusted_workflow_path or trusted_base).resolve(strict=True)
    verified = validate_candidate(candidate_repo, trusted_base, base_sha, candidate_sha, assignment, repository, trusted_workflow)
    profile = verified.pop("_profile")
    trusted_workflow = verified.pop("_trusted_workflow")
    verified.pop("_base_entries")
    verified.pop("_candidate_entries")
    output = Path(report_path).resolve()
    log = Path(log_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    commands: list[dict[str, Any]] = []
    test_exit = 2
    started = time.time()
    dependency_evidence: dict[str, Any] = {"pip_report_sha256": None, "freeze_sha256": None, "artifacts": []}
    if f"{sys.version_info.major}.{sys.version_info.minor}" != profile["python_version"]:
        raise VerificationError("TRUSTED_PYTHON_VERSION_MISMATCH")
    with tempfile.TemporaryDirectory(prefix="ktool-trusted-qa-") as temporary, log.open("w", encoding="utf-8") as log_file:
        overlay = Path(temporary) / "candidate-overlay"
        materialize_overlay(candidate_repo, candidate_sha, trusted_workflow, verified["test_hashes"], overlay)
        python_for_tests = Path(sys.executable)
        dependencies_ready = not install_dependencies
        if install_dependencies:
            venv_dir = Path(temporary) / "qa-venv"
            venv_argv = [sys.executable, "-m", "venv", str(venv_dir)]
            venv_exit, elapsed, _ = _run_command(venv_argv, trusted_base, profile["timeouts_seconds"]["venv_create"], log_file)
            commands.append({"phase": "VENV", "argv": venv_argv, "exit": venv_exit, "elapsed": elapsed})
            python_for_tests = venv_dir / "Scripts" / "python.exe" if not venv_exit else Path(sys.executable)
            install_exit = 1
            if not venv_exit:
                report_file = Path(temporary) / "pip-install-report.json"
                install_argv = [
                    str(python_for_tests), "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
                    "--only-binary=:all:", "--report", str(report_file),
                    "--requirement", str(trusted_workflow / "requirements.txt"),
                    "--constraint", str(trusted_workflow / "constraints-windows-py312.txt"),
                ]
                install_exit, elapsed, _ = _run_command(install_argv, trusted_base, profile["timeouts_seconds"]["dependency_install"], log_file)
                commands.append({"phase": "DEPENDENCIES", "argv": install_argv, "exit": install_exit, "elapsed": elapsed})
            if not venv_exit and not install_exit:
                freeze_argv = [str(python_for_tests), "-m", "pip", "freeze", "--all"]
                freeze_exit, elapsed, freeze_output = _run_command(freeze_argv, trusted_base, 60, log_file)
                commands.append({"phase": "DEPENDENCY_INVENTORY", "argv": freeze_argv, "exit": freeze_exit, "elapsed": elapsed})
                if freeze_exit == 0:
                    dependency_evidence = _pip_artifact_evidence(report_file, freeze_output)
                dependencies_ready = freeze_exit == 0 and bool(dependency_evidence["artifacts"])
            if not dependencies_ready:
                test_exit = install_exit or venv_exit or 1
        build_argv = [str(python_for_tests), "-m", "compileall", "-q", str(overlay)]
        build_exit, elapsed, _ = _run_command(build_argv, overlay, profile["timeouts_seconds"]["build"], log_file)
        commands.append({"phase": "BUILD", "argv": build_argv, "exit": build_exit, "elapsed": elapsed})
        if build_exit == 0 and dependencies_ready:
            test_list_path = Path(temporary) / "trusted-test-files.json"
            test_list_path.write_text(json.dumps(profile["test_files"], ensure_ascii=False), encoding="utf-8")
            entrypoint = trusted_workflow / "ci" / "trusted_qa_suite_entry.py"
            test_argv = [str(python_for_tests), "-I", str(entrypoint), "--overlay", str(overlay), "--test-files-json", str(test_list_path)]
            test_exit, elapsed, _ = _run_command(test_argv, overlay, profile["timeouts_seconds"]["tests"], log_file)
            commands.append({"phase": "REGRESSION_TESTS", "argv": test_argv, "exit": test_exit, "elapsed": elapsed})
        result = {
            "schema_version": 1,
            **verified,
            "status": "PASS" if test_exit == 0 and all(command["exit"] == 0 for command in commands) else "FAIL",
            "commands": commands,
            "dependency_evidence": dependency_evidence,
            "runner_identity": "GITHUB_HOSTED_WINDOWS_2022" if os.environ.get("GITHUB_ACTIONS") == "true" else "LOCAL_UNTRUSTED_RUNNER",
            "runner_python": sys.version,
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
            "duration_seconds": round(time.time() - started, 3),
            "evidence_class": "CLAIMED_LOCAL" if os.environ.get("GITHUB_ACTIONS") != "true" else "HOSTED_RUN_PENDING_SEPARATE_ATTESTOR",
            "production_trusted": False,
        }
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def _write_outputs(path: str | None, values: dict[str, Any]) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8", newline="\n") as stream:
        for key, value in values.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
            stream.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-repo", required=True)
    parser.add_argument("--trusted-base", required=True)
    parser.add_argument("--trusted-workflow")
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--assignment", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--report")
    parser.add_argument("--log")
    parser.add_argument("--install-dependencies", action="store_true")
    parser.add_argument("--github-output")
    parser.add_argument("--inspect-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.inspect_only:
            workflow_root = Path(args.trusted_workflow or args.trusted_base).resolve(strict=True)
            inspected = validate_candidate(args.candidate_repo, args.trusted_base, args.base_sha, args.candidate_sha,
                                           args.assignment, args.repository, workflow_root)
            for key in ("_profile", "_trusted_workflow", "_base_entries", "_candidate_entries", "scope"):
                inspected.pop(key, None)
            _write_outputs(args.github_output, {"tree_sha": inspected["tree_sha"], "paths": inspected["paths"],
                                                "profile_digest": inspected["profile_digest"],
                                                "suite_digest": inspected["suite_digest"]})
            print(json.dumps(inspected, indent=2))
            return 0
        if not args.report or not args.log:
            raise VerificationError("REPORT_AND_LOG_PATHS_REQUIRED")
        result = run_profile(args.candidate_repo, args.trusted_base, args.base_sha, args.candidate_sha,
                             args.assignment, args.repository, args.report, args.log, args.install_dependencies,
                             args.trusted_workflow)
        _write_outputs(args.github_output, {"qa_exit_code": 0 if result["status"] == "PASS" else 1,
                                            "tree_sha": result["tree_sha"], "paths": result["paths"],
                                            "profile_digest": result["profile_digest"], "suite_digest": result["suite_digest"],
                                            "status": result["status"], "commands_json": json.dumps(result["commands"], separators=(",", ":")),
                                            "dependency_evidence_json": json.dumps(result["dependency_evidence"], separators=(",", ":"))})
        print(json.dumps({"status": result["status"], "tree_sha": result["tree_sha"], "paths": result["paths"],
                          "profile_digest": result["profile_digest"], "suite_digest": result["suite_digest"]}, indent=2))
        return 0 if result["status"] == "PASS" else 1
    except Exception as error:
        message = f"VERIFIER_ERROR:{type(error).__name__}:{error}"
        _write_outputs(args.github_output, {"qa_exit_code": 2, "status": "BLOCKED", "commands_json": "[]",
                                            "dependency_evidence_json": "{}"})
        if args.report:
            Path(args.report).write_text(json.dumps({"status": "BLOCKED", "production_trusted": False, "error": message}, indent=2) + "\n", encoding="utf-8")
        print(message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
