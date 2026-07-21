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


GITHUB_HOSTED_RUNNERS = frozenset({
    "ubuntu-latest", "ubuntu-22.04", "ubuntu-24.04", "ubuntu-20.04",
    "macos-latest", "macos-13", "macos-14", "macos-15",
    "windows-latest", "windows-2022", "windows-2019",
})


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
        overlap = labels & GITHUB_HOSTED_RUNNERS
        assert not overlap, (
            f"ci.yml 'test' job must not target GitHub-hosted runners; found {overlap}. "
            "GitHub Actions does not support OR between GitHub-hosted and self-hosted labels."
        )

    def test_all_ci_jobs_target_required_labels(self):
        """Every job in ci.yml must use the required self-hosted labels.

        Catches regressions where a newly added job accidentally uses ubuntu-latest.
        """
        wf = _load_workflow(CI_WORKFLOW)
        failures = []
        for job_name, job in wf["jobs"].items():
            labels = set(_get_runs_on(job))
            missing = REQUIRED_LABELS - labels
            if missing:
                failures.append(
                    f"Job '{job_name}' is missing labels {missing} (has {labels})"
                )
        assert not failures, (
            "All ci.yml jobs must target the self-hosted oompah runner:\n"
            + "\n".join(failures)
        )

    def test_no_ci_job_uses_github_hosted_runner(self):
        """No job in ci.yml may use a GitHub-hosted runner name.

        GitHub Actions has no OR between GitHub-hosted and self-hosted labels;
        any job with ubuntu-latest/macos-latest/etc. would silently bypass the
        self-hosted runner and fail when GitHub-hosted capacity is unavailable.
        """
        wf = _load_workflow(CI_WORKFLOW)
        violations = []
        for job_name, job in wf["jobs"].items():
            labels = set(_get_runs_on(job))
            overlap = labels & GITHUB_HOSTED_RUNNERS
            if overlap:
                violations.append(f"Job '{job_name}' uses GitHub-hosted label(s): {overlap}")
        assert not violations, (
            "ci.yml must not use GitHub-hosted runners:\n" + "\n".join(violations)
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
        overlap = labels & GITHUB_HOSTED_RUNNERS
        assert not overlap, (
            f"cli-release.yml 'build-release' job must not target GitHub-hosted runners; "
            f"found {overlap}."
        )

    def test_all_release_jobs_target_required_labels(self):
        """Every job in cli-release.yml must use the required self-hosted labels.

        Catches regressions where a newly added job accidentally uses ubuntu-latest.
        """
        wf = _load_workflow(RELEASE_WORKFLOW)
        failures = []
        for job_name, job in wf["jobs"].items():
            labels = set(_get_runs_on(job))
            missing = REQUIRED_LABELS - labels
            if missing:
                failures.append(
                    f"Job '{job_name}' is missing labels {missing} (has {labels})"
                )
        assert not failures, (
            "All cli-release.yml jobs must target the self-hosted oompah runner:\n"
            + "\n".join(failures)
        )

    def test_no_release_job_uses_github_hosted_runner(self):
        """No job in cli-release.yml may use a GitHub-hosted runner name."""
        wf = _load_workflow(RELEASE_WORKFLOW)
        violations = []
        for job_name, job in wf["jobs"].items():
            labels = set(_get_runs_on(job))
            overlap = labels & GITHUB_HOSTED_RUNNERS
            if overlap:
                violations.append(f"Job '{job_name}' uses GitHub-hosted label(s): {overlap}")
        assert not violations, (
            "cli-release.yml must not use GitHub-hosted runners:\n" + "\n".join(violations)
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
        # The token should only appear as a variable reference, not a literal value.
        # Check for common PAT prefix patterns that would indicate a hardcoded secret.
        for forbidden in ("ghp_", "ghs_", "github_pat_"):
            assert forbidden not in text, (
                f"scripts/runner.sh must not contain a hardcoded GitHub token (found '{forbidden}')"
            )

    def test_runner_script_deletes_registration_token_after_use(self):
        """Token file must be deleted on the same statement that references its path.

        This test is stricter than checking `rm -f` and `registration-token` appear
        anywhere in the file — it verifies they co-occur on a single logical line so
        that a partial edit cannot inadvertently drop the cleanup while leaving the
        write intact.
        """
        import re
        text = self._script_text()
        assert re.search(r"rm -f[^\n]*registration-token", text), (
            "scripts/runner.sh must delete the token file with 'rm -f .../registration-token' "
            "on one line — both must appear together to avoid partial-edit regressions"
        )

    def test_runner_script_secures_token_file_with_chmod_600(self):
        """The short-lived registration token file must be mode 600 (owner-read only)."""
        text = self._script_text()
        assert "chmod 600" in text, (
            "scripts/runner.sh should chmod 600 the registration-token file so it is "
            "not world-readable while the configure step runs"
        )

    def test_runner_script_starts_container_in_detached_mode(self):
        """The start command must use -d so the container runs in the background.

        Without -d the `make runner-start` command would block the terminal and
        the runner would stop when the shell exits.
        """
        import re
        text = self._script_text()
        # Match `<cmd> run -d` or `<cmd> run ... -d` inside cmd_start block
        assert re.search(r'"\$_CONTAINER_CMD"\s+run\s+-d', text), (
            "cmd_start must launch the container with 'run -d' (detached mode). "
            "Without -d the runner blocks the calling process."
        )

    def test_runner_script_uses_restart_unless_stopped(self):
        """The container must use --restart unless-stopped for resilience across reboots."""
        text = self._script_text()
        assert "--restart unless-stopped" in text, (
            "scripts/runner.sh must pass '--restart unless-stopped' so the container "
            "auto-restarts after a host reboot (requires the Podman/Docker daemon to start)."
        )

    def test_runner_script_has_bash_shebang(self):
        """The script must start with a valid bash shebang."""
        text = self._script_text()
        first_line = text.splitlines()[0]
        assert first_line == "#!/usr/bin/env bash", (
            f"scripts/runner.sh must begin with '#!/usr/bin/env bash'; got '{first_line}'"
        )

    def test_runner_script_default_labels_match_required_labels(self):
        """The script's default OOMPAH_RUNNER_LABELS must contain all four required labels."""
        # The default is hard-coded in the variable assignment inside the script.
        # Verify the literal default value string is present so that a change to
        # the default is immediately caught.
        text = self._script_text()
        assert "self-hosted,linux,x64,oompah" in text, (
            "scripts/runner.sh default for OOMPAH_RUNNER_LABELS must be "
            "'self-hosted,linux,x64,oompah' to match the CI workflow configuration"
        )

    def test_runner_script_has_usage_message_for_unknown_commands(self):
        """An invalid sub-command must print usage rather than silently succeed."""
        text = self._script_text()
        # The script should have a catch-all (*) case with usage/help output
        assert "Usage:" in text or "usage:" in text, (
            "scripts/runner.sh should print a Usage message for unrecognised commands"
        )
        # And it should exit non-zero (exit 1)
        assert "exit 1" in text, (
            "scripts/runner.sh should exit 1 when an unrecognised command is given"
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

    def test_runner_doc_config_table_has_all_env_vars(self):
        """Every OOMPAH_RUNNER_* variable must appear in the config reference table."""
        text = self._doc_text()
        runner_vars = [
            "OOMPAH_RUNNER_REPO",
            "OOMPAH_RUNNER_NAME",
            "OOMPAH_RUNNER_LABELS",
            "OOMPAH_RUNNER_IMAGE",
            "OOMPAH_RUNNER_WORKDIR",
            "OOMPAH_RUNNER_CONTAINER",
        ]
        missing = [v for v in runner_vars if v not in text]
        assert not missing, (
            f"docs/self-hosted-runner.md config table is missing entries for: {missing}"
        )

    def test_runner_doc_references_correct_github_repo(self):
        """Docs must link to the correct repository (lesserevil/oompah)."""
        text = self._doc_text()
        assert "lesserevil/oompah" in text, (
            "docs/self-hosted-runner.md must reference the target repo 'lesserevil/oompah'"
        )

    def test_runner_doc_covers_runner_stop_command(self):
        """Docs must cover how to stop the runner (not just start/status)."""
        text = self._doc_text()
        assert "runner-stop" in text, (
            "docs/self-hosted-runner.md must document the 'make runner-stop' command"
        )

    def test_runner_doc_documents_container_runtime_options(self):
        """Docs must mention Podman (and preferably Docker) as supported runtimes."""
        text = self._doc_text()
        assert "Podman" in text or "podman" in text, (
            "docs/self-hosted-runner.md must mention Podman as the container runtime"
        )
