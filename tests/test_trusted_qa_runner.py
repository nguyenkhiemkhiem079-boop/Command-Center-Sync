from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ci.trusted_qa_runner import (
    VerificationError,
    _clean_env,
    _validate_git_path,
    materialize_overlay,
    run_profile,
    validate_candidate,
    _pip_artifact_evidence,
)
from ci.trusted_qa_attestor import GitHubApiError, create_report, validate_dispatch_identity


ROOT = Path(__file__).resolve().parents[1]


class TrustedQaRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="trusted-qa-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.trusted = self.repo
        self.workflow = self.root / "workflow-source"
        self.workflow.mkdir()
        (self.repo / ".github").mkdir()
        (self.repo / "tests").mkdir()
        (self.repo / "ci").mkdir()
        (self.repo / "ci_scope_gate.py").write_bytes((ROOT / "ci_scope_gate.py").read_bytes())
        (self.repo / "registry.py").write_bytes((ROOT / "registry.py").read_bytes())
        (self.repo / "ci" / "trusted-qa-profile.json").write_text("{}", encoding="utf-8")
        (self.repo / ".github" / "scope-policy.json").write_text(json.dumps({
            "schema_version": 1,
            "repository": "owner/repo",
            "approval_state": "OWNER_APPROVED",
            "protected_paths": [".github", "tests", "registry.py", "ci_scope_gate.py"],
            "assignments": {"CI-PILOT": {
                "scope": "ci-pilot", "allowed_paths": ["ci-pilot"],
                "resource_locks": [], "required_resource_locks": []
            }},
        }), encoding="utf-8")
        (self.repo / "tests" / "test_base.py").write_text("VALUE = 'trusted-base'\n", encoding="utf-8")
        self.git("init", "-q")
        self.git("config", "user.name", "Trusted QA Test")
        self.git("config", "user.email", "qa@example.test")
        self.git("add", "--all")
        self.git("commit", "-qm", "trusted base")
        self.base_sha = self.git("rev-parse", "HEAD")
        self.candidate = self.root / "candidate"
        self.git("worktree", "add", "--detach", str(self.candidate), self.base_sha)
        (self.candidate / "ci-pilot").mkdir()
        (self.candidate / "ci-pilot" / "allowed.txt").write_text("candidate\n", encoding="utf-8")
        self.candidate_git("add", "--all")
        self.candidate_git("commit", "-qm", "allowed pilot file")
        self.candidate_sha = self.candidate_git("rev-parse", "HEAD")
        (self.workflow / "ci").mkdir()
        (self.workflow / "tests").mkdir()
        (self.workflow / ".github" / "workflows").mkdir(parents=True)
        for filename in ("trusted_qa_runner.py", "trusted_qa_attestor.py"):
            (self.workflow / "ci" / filename).write_bytes((ROOT / "ci" / filename).read_bytes())
        profile = {
            "schema_version": 1, "profile_id": "fixture", "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}",
            "runner": "fixture", "scope_assignment": "CI-PILOT", "mission_id": "M", "task_id": "T",
            "task_owner": "CODEX_LEAD", "ownership_epoch": 1, "contract_revision": "v1",
            "owner_login": "owner", "protected_base_branch": "integration/command-center-qa",
            "trusted_workflow_branch": "secure-default", "trusted_check_name": "Trusted Independent QA",
            "acceptance_criteria": ["test"], "dependency_files": ["requirements.txt", "constraints-windows-py312.txt"],
            "test_files": ["tests/test_base.py"], "timeouts_seconds": {"dependency_install": 1, "build": 1, "tests": 1},
        }
        (self.workflow / "ci" / "trusted-qa-profile.json").write_text(json.dumps(profile), encoding="utf-8")
        (self.workflow / "ci" / "trusted_qa_suite_entry.py").write_bytes((ROOT / "ci" / "trusted_qa_suite_entry.py").read_bytes())
        (self.workflow / ".github" / "workflows" / "trusted-independent-qa.yml").write_text("name: trusted\n", encoding="utf-8")
        for name in profile["dependency_files"]:
            (self.workflow / name).write_text("", encoding="utf-8")
        (self.workflow / "tests" / "test_base.py").write_text(
            "import unittest\nclass FixedTest(unittest.TestCase):\n def test_trusted_fixture(self): self.assertEqual(2 + 2, 4)\n",
            encoding="utf-8")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True, stderr=subprocess.PIPE).strip()

    def candidate_git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.candidate), *args], text=True, stderr=subprocess.PIPE).strip()

    def validate(self, **overrides):
        args = dict(repo_path=self.candidate, trusted_base_path=self.trusted, base_sha=self.base_sha,
                    candidate_sha=self.candidate_sha, assignment="CI-PILOT", repository="owner/repo",
                    trusted_workflow_path=self.workflow)
        args.update(overrides)
        return validate_candidate(**args)

    def test_real_candidate_commit_scope_and_profile_are_bound(self):
        result = self.validate()
        self.assertEqual(result["candidate_sha"], self.candidate_sha)
        self.assertEqual(result["paths"], ["ci-pilot/allowed.txt"])
        self.assertEqual(result["scope_assignment"], "CI-PILOT")
        self.assertEqual(len(result["profile_digest"]), 64)
        self.assertEqual(len(result["suite_digest"]), 64)
        self.assertEqual(len(result["contract_hash"]), 64)

    def test_fabricated_or_nonexistent_sha_is_rejected(self):
        with self.assertRaises(VerificationError):
            self.validate(candidate_sha="a" * 40)

    def test_checkout_must_equal_candidate_sha(self):
        with self.assertRaisesRegex(VerificationError, "CHECKOUT_NOT_AT_CANDIDATE"):
            self.validate(candidate_sha=self.base_sha)

    def test_wrong_scope_assignment_is_rejected(self):
        with self.assertRaises(VerificationError):
            self.validate(assignment="UNAPPROVED")

    def test_out_of_scope_candidate_is_rejected_by_trusted_base_policy(self):
        (self.candidate / "docs").mkdir()
        (self.candidate / "docs" / "escape.md").write_text("outside\n", encoding="utf-8")
        self.candidate_git("add", "--all")
        self.candidate_git("commit", "-qm", "out of scope")
        self.candidate_sha = self.candidate_git("rev-parse", "HEAD")
        with self.assertRaises(VerificationError):
            self.validate()

    def test_candidate_symlink_is_rejected_before_materialization(self):
        blob = subprocess.run(["git", "-C", str(self.candidate), "hash-object", "-w", "--stdin"],
                              input=b"../outside.txt", capture_output=True, check=True).stdout.decode().strip()
        self.candidate_git("update-index", "--add", "--cacheinfo", f"120000,{blob},ci-pilot/escape.txt")
        self.candidate_git("commit", "-qm", "symlink candidate")
        self.candidate_sha = self.candidate_git("rev-parse", "HEAD")
        with self.assertRaisesRegex(VerificationError, "UNSUPPORTED_GIT_ENTRY"):
            self.validate()

    def test_trusted_test_sources_replace_candidate_test_files(self):
        overlay = self.root / "overlay"
        trusted_hash = {"tests/test_base.py": __import__("hashlib").sha256(
            (self.workflow / "tests" / "test_base.py").read_bytes()).hexdigest()}
        result = materialize_overlay(self.candidate, self.candidate_sha, self.workflow, trusted_hash, overlay)
        self.assertIn("test_trusted_fixture", (result / "tests" / "test_base.py").read_text(encoding="utf-8"))
        self.assertTrue((result / "tests" / "__init__.py").is_file())

    def test_full_local_runner_executes_actual_build_and_trusted_test(self):
        report, log = self.root / "report.json", self.root / "qa.log"
        result = run_profile(self.candidate, self.trusted, self.base_sha, self.candidate_sha,
                             "CI-PILOT", "owner/repo", report, log,
                             install_dependencies=False, trusted_workflow_path=self.workflow)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["evidence_class"], "CLAIMED_LOCAL")
        self.assertEqual([item["phase"] for item in result["commands"]], ["BUILD", "REGRESSION_TESTS"])
        self.assertTrue(all(item["exit"] == 0 for item in result["commands"]))
        self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["production_trusted"], False)
        self.assertIn("test_trusted_fixture", log.read_text(encoding="utf-8"))

    def test_traversal_and_windows_alias_paths_are_rejected(self):
        for path in ("../outside.txt", "C:/temp/file", "folder\\file", "NUL.txt", "ends-with-dot."):
            with self.subTest(path=path), self.assertRaises(VerificationError):
                _validate_git_path(path)

    def test_child_environment_omits_github_and_action_credentials(self):
        original = dict(os.environ)
        try:
            os.environ["GITHUB_TOKEN"] = "sensitive-fixture"
            os.environ["ACTIONS_RUNTIME_TOKEN"] = "runtime-fixture"
            os.environ["GITHUB_OUTPUT"] = "output-fixture"
            os.environ["PATH"] = original.get("PATH", "")
            environment = _clean_env()
            self.assertNotIn("GITHUB_TOKEN", environment)
            self.assertNotIn("ACTIONS_RUNTIME_TOKEN", environment)
            self.assertNotIn("GITHUB_OUTPUT", environment)
            self.assertEqual(environment.get("PATH"), original.get("PATH", ""))
        finally:
            os.environ.clear()
            os.environ.update(original)

    def test_pip_download_report_requires_hashed_official_https_wheels(self):
        import hashlib
        report = self.root / "pip-report.json"
        report.write_text(json.dumps({"install": [{
            "metadata": {"name": "mcp", "version": "1.30.0"},
            "download_info": {"url": "https://files.pythonhosted.org/packages/mcp.whl",
                              "archive_info": {"hashes": {"sha256": "a" * 64}}},
        }]}), encoding="utf-8")
        result = _pip_artifact_evidence(report, "mcp==1.30.0\n")
        self.assertEqual(result["artifacts"][0]["sha256"], "a" * 64)
        self.assertEqual(result["freeze_sha256"], hashlib.sha256(b"mcp==1.30.0\n").hexdigest())
        report.write_text(json.dumps({"install": [{
            "metadata": {"name": "mcp", "version": "1.30.0"},
            "download_info": {"url": "http://attacker.example/mcp.whl",
                              "archive_info": {"hashes": {"sha256": "a" * 64}}},
        }]}), encoding="utf-8")
        with self.assertRaisesRegex(VerificationError, "UNVERIFIED_PIP_ARTIFACT"):
            _pip_artifact_evidence(report, "mcp==1.30.0\n")

    def test_dispatch_requires_exact_trusted_actor_branch_and_event(self):
        profile = json.loads((self.workflow / "ci" / "trusted-qa-profile.json").read_text(encoding="utf-8"))
        profile.update({"owner_login": "owner", "trusted_workflow_branch": "secure-default"})
        repository = "owner/repo"
        good = {
            "GITHUB_ACTOR": "owner", "GITHUB_REF": "refs/heads/secure-default",
            "GITHUB_WORKFLOW_REF": repository + "/.github/workflows/trusted-independent-qa.yml@refs/heads/secure-default",
            "GITHUB_WORKFLOW_SHA": "a" * 40, "GITHUB_SHA": "b" * 40,
            "GITHUB_EVENT_NAME": "workflow_dispatch",
        }
        validate_dispatch_identity(profile, repository, good)
        for field, value in (("GITHUB_ACTOR", "worker"), ("GITHUB_REF", "refs/heads/worker"),
                             ("GITHUB_EVENT_NAME", "pull_request")):
            invalid = dict(good, **{field: value})
            with self.subTest(field=field), self.assertRaises(GitHubApiError):
                validate_dispatch_identity(profile, repository, invalid)

    def test_attestor_binds_controller_test_result_and_never_approves(self):
        inspected = validate_candidate(self.candidate, self.trusted, self.base_sha, self.candidate_sha,
                                       "CI-PILOT", "owner/repo", self.workflow)
        environment = {
            "QA_TREE_SHA": inspected["tree_sha"],
            "QA_PROFILE_DIGEST": inspected["profile_digest"],
            "QA_SUITE_DIGEST": inspected["suite_digest"],
            "QA_PATHS_JSON": json.dumps(inspected["paths"]),
        }
        pr_binding = {"pr_number": 3, "pr_url": "https://github.com/owner/repo/pull/3", "pr_author": "worker",
                      "base_branch": "integration/command-center-qa", "base_sha": self.base_sha,
                      "candidate_sha": self.candidate_sha, "repository_id": 12, "head_repository_id": 12}
        artifacts = [{"name": "ktool-trusted-qa-log", "artifact_id": 77, "sha256": "a" * 64,
                      "size_in_bytes": 123, "expired": False}]
        commands = [{"phase": "VENV", "argv": ["python", "-m", "venv"], "exit": 0},
                    {"phase": "DEPENDENCIES", "argv": ["python", "-m", "pip", "install"], "exit": 0},
                    {"phase": "DEPENDENCY_INVENTORY", "argv": ["python", "-m", "pip", "freeze"], "exit": 0},
                    {"phase": "BUILD", "argv": ["python", "-m", "compileall"], "exit": 0},
                    {"phase": "REGRESSION_TESTS", "argv": ["python", "-I", "trusted-suite"], "exit": 0}]
        dependency_evidence = {"pip_report_sha256": "a" * 64, "freeze_sha256": "b" * 64,
                               "installed_packages": ["mcp==1.30.0"], "artifacts": [
                                   {"name": "mcp", "version": "1.30.0", "sha256": "c" * 64,
                                    "source_host": "files.pythonhosted.org"}]}
        with patch.dict(os.environ, environment, clear=False), \
             patch("ci.trusted_qa_attestor.verify_pr_binding", return_value=pr_binding), \
             patch("ci.trusted_qa_attestor.list_run_artifacts", return_value=artifacts):
            report = create_report(self.root / "attested-report.json", self.workflow, self.trusted, self.candidate,
                                   "owner/repo", "not-used-fixture", 3, self.base_sha, self.candidate_sha,
                                   "1001", "1", "success", "success", "0", json.dumps(commands), json.dumps(dependency_evidence), "owner",
                                   "owner/repo/.github/workflows/trusted-independent-qa.yml@refs/heads/secure-default",
                                   "b" * 40)
        self.assertEqual(report["verification_result"], "VERIFIED_PASS")
        self.assertEqual(report["worker_identity"], "UNKNOWN")
        self.assertEqual(report["source_submitter"], "GITHUB_PR_AUTHOR:worker")
        self.assertEqual(report["worker_identity_verification"], "NOT_AVAILABLE_FROM_GITHUB_PR")
        self.assertEqual(report["artifacts"][0]["sha256"], "a" * 64)
        self.assertEqual(report["approval_status"], "PENDING_OWNER_REVIEW")
        self.assertEqual(report["task_acceptance_state"], "PENDING_OWNER_REVIEW")
        self.assertFalse(report["production_trusted"])
        with patch.dict(os.environ, environment, clear=False), \
             patch("ci.trusted_qa_attestor.verify_pr_binding", return_value=pr_binding), \
             patch("ci.trusted_qa_attestor.list_run_artifacts", return_value=artifacts):
            falsified = create_report(self.root / "falsified-report.json", self.workflow, self.trusted, self.candidate,
                                      "owner/repo", "not-used-fixture", 3, self.base_sha, self.candidate_sha,
                                      "1002", "1", "success", "failure", "0", json.dumps(commands), json.dumps(dependency_evidence), "owner",
                                      "owner/repo/.github/workflows/trusted-independent-qa.yml@refs/heads/secure-default",
                                      "b" * 40)
        self.assertEqual(falsified["verification_result"], "VERIFIED_FAIL")

    def test_workflow_keeps_untrusted_code_job_secret_and_write_free(self):
        workflow = (ROOT / ".github" / "workflows" / "trusted-independent-qa.yml").read_text(encoding="utf-8")
        qa_job = workflow.split("\n  qa:\n", 1)[1].split("\n  attest:\n", 1)[0]
        self.assertIn("permissions:\n      contents: read", qa_job)
        self.assertNotIn("GITHUB_TOKEN", qa_job)
        self.assertNotIn("secrets.", qa_job)
        self.assertNotIn("pull_request_target", workflow)
        self.assertIn("actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6", workflow)
        self.assertIn("actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683", workflow)


if __name__ == "__main__":
    unittest.main()
