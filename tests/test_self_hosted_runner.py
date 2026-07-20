"""Tests for the self-hosted GitHub Actions runner configuration.

Validates:
- CI workflows target the required self-hosted runner labels.
- .env.example documents the required runner environment variables.
- scripts/runner.sh exists, is executable, and contains expected logic.
- Makefile exposes the runner lifecycle targets.
- docs/self-hosted-runner.md covers the key user-facing guidance.

All tests run without exposing secrets or making network calls.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "cli-release.yml"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
RUNNER_SCRIPT = REPO_ROOT / "scripts" / "runner.sh"
MAKEFILE = REPO_ROOT / "Makefile"
RUNNER_DOC = REPO_ROOT / "docs" / "self-hosted-runner.md"

# Expected labels that identify the self-hosted oompah runner
REQUIRED_LABELS = {"self-hosted", "linux", "x64", "oompah"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_workflow(path: Path) -> dict:
    """Load and return a GitHub Actions workflow YAML."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _get_runs_on(job: dict) -> list[str]:
    """Return the runs-on value normalised to a list of strings."""
    val = job.get("runs-on", [])
    if isinstance(val, str):
        return [val]
    return list(val)


# ---------------------------------------------------------------------------
# Workflow label tests
# ---------------------------------------------------------------------------


class TestCiWorkflowRunsOnLabels:
    """CI workflow must target the self-hosted oompah runner."""

    def test_ci_workflow_has_test_job(self):
        wf = _load_workflow(CI_WORKFLOW)
        assert "test" in wf["jobs"], "Expected a 'test' job in ci.yml"

    def test_ci_test_job_targets_self_hosted(self):
        wf = _load_workflow(CI_WORKFLOW)
        labels = set(_get_runs_on(wf["jobs"]["test"]))
        assert "self-hosted" in labels, (
            f"ci.yml 'test' job must include 'self-hosted' in runs-on; got {labels}"
        )

    def test_ci_test_job_targets_oompah_label(self):
        wf = _load_workflow(CI_WORKFLOW)
        labels = set(_get_runs_on(wf["jobs"]["test"]))
        assert "oompah" in labels, (
            f"ci.yml 'test' job must include 'oompah' in runs-on; got {labels}"
        )

    def test_ci_test_job_includes_all_required_labels(self):
        wf = _load_workflow(CI_WORKFLOW)
        labels = set(_get_runs_on(wf["jobs"]["test"]))
        missing = REQUIRED_LABELS - labels
        assert not missing, (
            f"ci.yml 'test' job missing labels: {missing}. Current runs-on: {labels}"
        )

    def test_ci_test_job_does_not_use_github_hosted_runner(self):
        wf = _load_workflow(CI_WORKFLOW)
        labels = set(_get_runs_on(wf["jobs"]["test"]))
        github_hosted = {"ubuntu-latest", "ubuntu-22.04", "ubuntu-24.04",
                         "macos-latest", "windows-latest"}
        overlap = labels & github_hosted
        assert not overlap, (
            f"ci.yml 'test' job must not target GitHub-hosted runners; found {overlap}. "
            "GitHub Actions does not support OR between GitHub-hosted and self-hosted labels."
        )


class TestReleaseWorkflowRunsOnLabels:
    """CLI Release workflow must target the self-hosted oompah runner."""

    def test_release_workflow_has_build_release_job(self):
        wf = _load_workflow(RELEASE_WORKFLOW)
        assert "build-release" in wf["jobs"], (
            "Expected a 'build-release' job in cli-release.yml"
        )

    def test_release_build_job_targets_self_hosted(self):
        wf = _load_workflow(RELEASE_WORKFLOW)
        labels = set(_get_runs_on(wf["jobs"]["build-release"]))
        assert "self-hosted" in labels, (
            f"cli-release.yml 'build-release' job must include 'self-hosted'; got {labels}"
        )

    def test_release_build_job_targets_oompah_label(self):
        wf = _load_workflow(RELEASE_WORKFLOW)
        labels = set(_get_runs_on(wf["jobs"]["build-release"]))
        assert "oompah" in labels, (
            f"cli-release.yml 'build-release' job must include 'oompah'; got {labels}"
        )

    def test_release_build_job_includes_all_required_labels(self):
        wf = _load_workflow(RELEASE_WORKFLOW)
        labels = set(_get_runs_on(wf["jobs"]["build-release"]))
        missing = REQUIRED_LABELS - labels
        assert not missing, (
            f"cli-release.yml 'build-release' job missing labels: {missing}. "
            f"Current runs-on: {labels}"
        )

    def test_release_build_job_does_not_use_github_hosted_runner(self):
        wf = _load_workflow(RELEASE_WORKFLOW)
        labels = set(_get_runs_on(wf["jobs"]["build-release"]))
        github_hosted = {"ubuntu-latest", "ubuntu-22.04", "ubuntu-24.04",
                         "macos-latest", "windows-latest"}
        overlap = labels & github_hosted
        assert not overlap, (
            f"cli-release.yml 'build-release' job must not target GitHub-hosted runners; "
            f"found {overlap}."
        )


# ---------------------------------------------------------------------------
# .env.example documentation tests
# ---------------------------------------------------------------------------


class TestEnvExampleRunnerVars:
    """All runner configuration variables must be documented in .env.example."""

    def _env_text(self) -> str:
        return ENV_EXAMPLE.read_text(encoding="utf-8")

    def test_env_example_documents_runner_repo(self):
        assert "OOMPAH_RUNNER_REPO" in self._env_text()

    def test_env_example_documents_runner_name(self):
        assert "OOMPAH_RUNNER_NAME" in self._env_text()

    def test_env_example_documents_runner_labels(self):
        assert "OOMPAH_RUNNER_LABELS" in self._env_text()

    def test_env_example_documents_runner_image(self):
        assert "OOMPAH_RUNNER_IMAGE" in self._env_text()

    def test_env_example_documents_runner_workdir(self):
        assert "OOMPAH_RUNNER_WORKDIR" in self._env_text()

    def test_env_example_documents_runner_container(self):
        assert "OOMPAH_RUNNER_CONTAINER" in self._env_text()

    def test_env_example_documents_pat_permission(self):
        text = self._env_text()
        assert "Self-hosted runners" in text, (
            ".env.example should document the required PAT permission: "
            "'Self-hosted runners: Read and write'"
        )

    def test_env_example_documents_or_expression_limitation(self):
        text = self._env_text()
        assert "OR" in text or "or expression" in text.lower(), (
            ".env.example should note that GitHub Actions has no OR expression "
            "between GitHub-hosted and self-hosted labels"
        )

    def test_runner_image_is_pinned_not_latest(self):
        text = self._env_text()
        # The image reference must not use ':latest'
        import re
        image_refs = re.findall(r"ghcr\.io/actions/actions-runner:[^\s]+", text)
        assert image_refs, "No runner image reference found in .env.example"
        for ref in image_refs:
            assert not ref.endswith(":latest"), (
                f"Runner image must be pinned to a specific version, not ':latest': {ref}"
            )


# ---------------------------------------------------------------------------
# scripts/runner.sh tests
# ---------------------------------------------------------------------------


class TestRunnerScript:
    """scripts/runner.sh must exist, be executable, and contain required logic."""

    def test_runner_script_exists(self):
        assert RUNNER_SCRIPT.exists(), f"Expected {RUNNER_SCRIPT} to exist"

    def test_runner_script_is_executable(self):
        mode = RUNNER_SCRIPT.stat().st_mode
        assert mode & stat.S_IXUSR, f"{RUNNER_SCRIPT} is not user-executable"

    def _script_text(self) -> str:
        return RUNNER_SCRIPT.read_text(encoding="utf-8")

    def test_runner_script_has_setup_command(self):
        assert "cmd_setup" in self._script_text()

    def test_runner_script_has_start_command(self):
        assert "cmd_start" in self._script_text()

    def test_runner_script_has_stop_command(self):
        assert "cmd_stop" in self._script_text()

    def test_runner_script_has_status_command(self):
        assert "cmd_status" in self._script_text()

    def test_runner_script_targets_lesserevil_oompah(self):
        assert "lesserevil/oompah" in self._script_text()

    def test_runner_script_uses_pinned_image(self):
        import re
        text = self._script_text()
        image_refs = re.findall(r"ghcr\.io/actions/actions-runner:[^\s\"']+", text)
        assert image_refs, "No runner image reference found in runner.sh"
        for ref in image_refs:
            assert not ref.endswith(":latest"), (
                f"Runner image must be pinned to a specific version, not ':latest': {ref}"
            )

    def test_runner_script_registers_required_labels(self):
        text = self._script_text()
        for label in REQUIRED_LABELS:
            assert label in text, (
                f"Runner script must reference label '{label}'"
            )

    def test_runner_script_does_not_hardcode_token(self):
        text = self._script_text()
        # The token should only appear as a variable reference, not a literal value
        assert "ghp_" not in text, (
            "scripts/runner.sh must not contain a hardcoded GitHub token"
        )
        assert "ghs_" not in text, (
            "scripts/runner.sh must not contain a hardcoded GitHub token"
        )

    def test_runner_script_deletes_registration_token_after_use(self):
        text = self._script_text()
        assert "registration-token" in text
        # The script must clean up the token file
        assert 'rm -f' in text and 'registration-token' in text, (
            "Runner script should remove the registration token file after use"
        )

    def test_runner_script_supports_podman_and_docker(self):
        text = self._script_text()
        assert "podman" in text
        assert "docker" in text

    def test_runner_script_error_message_references_pat_permission(self):
        text = self._script_text()
        assert "Self-hosted runners" in text, (
            "Error message should mention required PAT permission"
        )

    def test_runner_script_has_set_euo_pipefail(self):
        text = self._script_text()
        assert "set -euo pipefail" in text, (
            "Runner script should use 'set -euo pipefail' for safety"
        )


# ---------------------------------------------------------------------------
# Makefile runner target tests
# ---------------------------------------------------------------------------


class TestMakefileRunnerTargets:
    """Makefile must expose runner lifecycle targets."""

    def _makefile_text(self) -> str:
        return MAKEFILE.read_text(encoding="utf-8")

    def test_makefile_has_runner_setup_target(self):
        assert "runner-setup:" in self._makefile_text()

    def test_makefile_has_runner_start_target(self):
        assert "runner-start:" in self._makefile_text()

    def test_makefile_has_runner_stop_target(self):
        assert "runner-stop:" in self._makefile_text()

    def test_makefile_has_runner_status_target(self):
        assert "runner-status:" in self._makefile_text()

    def test_makefile_runner_targets_invoke_runner_script(self):
        text = self._makefile_text()
        assert "scripts/runner.sh" in text

    def test_makefile_runner_targets_in_phony(self):
        text = self._makefile_text()
        assert "runner-setup" in text
        assert "runner-start" in text
        assert "runner-stop" in text
        assert "runner-status" in text
        # All four must appear on a .PHONY line
        phony_lines = [line for line in text.splitlines() if ".PHONY:" in line]
        phony_text = " ".join(phony_lines)
        for target in ("runner-setup", "runner-start", "runner-stop", "runner-status"):
            assert target in phony_text, (
                f"'{target}' must be listed in a .PHONY declaration"
            )

    def test_makefile_help_mentions_runner_targets(self):
        text = self._makefile_text()
        assert "runner-setup" in text
        assert "runner-start" in text
        assert "runner-stop" in text
        assert "runner-status" in text


# ---------------------------------------------------------------------------
# Documentation tests
# ---------------------------------------------------------------------------


class TestRunnerDocumentation:
    """docs/self-hosted-runner.md must cover key user-facing guidance."""

    def _doc_text(self) -> str:
        return RUNNER_DOC.read_text(encoding="utf-8")

    def test_runner_doc_exists(self):
        assert RUNNER_DOC.exists(), f"Expected {RUNNER_DOC} to exist"

    def test_runner_doc_covers_or_expression_limitation(self):
        text = self._doc_text()
        assert "OR" in text or "or expression" in text.lower(), (
            "Docs must note that GitHub Actions has no OR between GitHub-hosted "
            "and self-hosted runner labels"
        )

    def test_runner_doc_covers_required_pat_permission(self):
        text = self._doc_text()
        assert "Self-hosted runners" in text and "Read and write" in text, (
            "Docs must state the required PAT permission: "
            "'Self-hosted runners: Read and write'"
        )

    def test_runner_doc_covers_runner_labels(self):
        text = self._doc_text()
        for label in REQUIRED_LABELS:
            assert label in text, f"Docs must mention runner label '{label}'"

    def test_runner_doc_covers_setup_commands(self):
        text = self._doc_text()
        assert "runner-setup" in text
        assert "runner-start" in text
        assert "runner-status" in text

    def test_runner_doc_covers_troubleshooting(self):
        text = self._doc_text()
        assert "Troubleshoot" in text or "troubleshoot" in text

    def test_runner_doc_covers_upgrade_path(self):
        text = self._doc_text()
        assert "Upgrad" in text or "upgrad" in text, (
            "Docs should cover how to upgrade the runner image"
        )

    def test_runner_doc_has_mermaid_diagram(self):
        text = self._doc_text()
        assert "```mermaid" in text, (
            "Docs should include a Mermaid diagram per project conventions"
        )

    def test_runner_doc_references_env_example(self):
        text = self._doc_text()
        assert ".env" in text, (
            "Docs should reference .env for configuration"
        )
