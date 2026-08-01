"""Regression tests for project-scoped credentials on managed Git calls."""

from __future__ import annotations

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from oompah.git_credentials import (
    git_authentication_failure,
    git_credential_environment,
    redact_git_output,
)
from oompah.integration_executor import (
    _PROJECT_CREDENTIALS,
    _git,
    _git_failure_message,
)
from oompah.models import Project
from oompah.projects import ProjectStore


def _project(tmp_path: Path, *, token: str | None, forge: str) -> Project:
    repo = tmp_path / forge
    repo.mkdir(exist_ok=True)
    return Project(
        id=forge,
        name=forge,
        repo_url=f"https://forge.example/{forge}/repo.git",
        repo_path=str(repo),
        access_token=token,
        forge_kind=forge,
    )


def test_credential_environment_is_ephemeral_and_forge_aware(tmp_path: Path) -> None:
    with git_credential_environment(
        forge_kind="gitlab",
        access_token="fixture-token",
        base_env={"PATH": os.environ["PATH"]},
    ) as env:
        assert env["GIT_TERMINAL_PROMPT"] == "0"
        assert env["GIT_ASKPASS_REQUIRE"] == "force"
        assert env["OOMPAH_GIT_USERNAME"] == "oauth2"
        assert env["OOMPAH_GIT_PASSWORD"] == "fixture-token"
        assert env["GIT_CONFIG_VALUE_0"] == ""
        askpass = Path(env["GIT_ASKPASS"])
        assert askpass.exists()
        assert "fixture-token" not in askpass.read_text()
    assert not askpass.exists()

    with git_credential_environment(
        forge_kind="github", access_token="fixture-token"
    ) as env:
        assert env["OOMPAH_GIT_USERNAME"] == "x-access-token"


def test_redaction_covers_url_userinfo_and_encoded_token() -> None:
    token = "p@ss/word?"
    encoded = "p%40ss%2Fword%3F"
    output = (
        f"fatal: https://oauth2:{token}@gitlab.example/repo.git\n"
        f"retry https://oauth2:{encoded}@gitlab.example/repo.git"
    )
    redacted = redact_git_output(output, (token,))
    assert token not in redacted
    assert encoded not in redacted
    assert "[REDACTED]@gitlab.example" in redacted


def test_authentication_diagnostics_distinguish_missing_and_rejected_tokens() -> None:
    missing = git_authentication_failure(
        forge_kind="gitlab",
        access_token=None,
        output="fatal: could not read Username: terminal prompts disabled",
        operation="integration fetch",
    )
    rejected = git_authentication_failure(
        forge_kind="gitlab",
        access_token="fixture-token",
        output="remote: HTTP Basic: Access denied",
        operation="task branch push",
    )

    assert missing is not None
    assert "GitLab" in missing
    assert "missing" in missing
    assert "access_token" in missing
    assert rejected is not None
    assert "rejected" in rejected
    assert "fixture-token" not in rejected


def test_executor_failure_classification_is_actionable_and_safe() -> None:
    missing_marker = _PROJECT_CREDENTIALS.set((None, "gitlab"))
    try:
        missing_message, missing_status = _git_failure_message(
            "integration fetch",
            subprocess.CompletedProcess(
                ["git", "fetch"],
                128,
                "",
                "fatal: could not read Username: terminal prompts disabled",
            ),
        )
    finally:
        _PROJECT_CREDENTIALS.reset(missing_marker)

    rejected_marker = _PROJECT_CREDENTIALS.set(("fixture-token", "gitlab"))
    try:
        rejected_message, rejected_status = _git_failure_message(
            "task branch push",
            subprocess.CompletedProcess(
                ["git", "push"],
                128,
                "",
                "remote: HTTP Basic: Access denied",
            ),
        )
    finally:
        _PROJECT_CREDENTIALS.reset(rejected_marker)

    assert missing_status == "credential_missing"
    assert "configure" in missing_message
    assert rejected_status == "authentication_failed"
    assert "rejected" in rejected_message
    assert "fixture-token" not in rejected_message


def test_project_network_runner_uses_only_its_gitlab_token(tmp_path: Path) -> None:
    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    project = _project(tmp_path, token="project-token", forge="gitlab")
    observed: dict[str, object] = {}

    def fake_run(args, **kwargs):
        observed["args"] = args
        observed["env"] = kwargs["env"]
        return subprocess.CompletedProcess(args, 0, "", "")

    with patch("oompah.projects.subprocess.run", side_effect=fake_run):
        result = store._run_network_git(
            project,
            ["git", "push", "origin", "HEAD:epic-E-1"],
        )

    assert result.returncode == 0
    assert "project-token" not in observed["args"]
    env = observed["env"]
    assert env["OOMPAH_GIT_USERNAME"] == "oauth2"
    assert env["OOMPAH_GIT_PASSWORD"] == "project-token"
    config_count = int(env["GIT_CONFIG_COUNT"])
    assert any(
        env[f"GIT_CONFIG_KEY_{index}"] == "credential.helper"
        and env[f"GIT_CONFIG_VALUE_{index}"] == ""
        for index in range(config_count)
    )
    assert "project-token" not in result.stderr


def test_integration_git_subprocess_inherits_ephemeral_project_credentials(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    captured: dict[str, object] = {}
    real_run = subprocess.run

    def capture_run(args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs["env"]
        return real_run(args, **kwargs)

    marker = _PROJECT_CREDENTIALS.set(("integration-token", "gitlab"))
    try:
        with patch(
            "oompah.integration_executor.subprocess.run",
            side_effect=capture_run,
        ):
            result = _git(str(repo), "rev-parse", "--git-dir")
    finally:
        _PROJECT_CREDENTIALS.reset(marker)

    assert result.returncode != 0
    assert captured["env"]["OOMPAH_GIT_PASSWORD"] == "integration-token"
    assert "integration-token" not in captured["args"]
    assert "integration-token" not in result.stderr


def test_failed_authenticated_clone_removes_partial_checkout(tmp_path: Path) -> None:
    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    with patch.object(
        store,
        "_run_network_git",
        return_value=subprocess.CompletedProcess(
            ["git", "clone"],
            128,
            "",
            "fatal: authentication failed",
        ),
    ):
        try:
            store.create(
                "https://gitlab.example/acme/repo.git",
                name="repo",
                access_token="fixture-token",
                forge_kind="gitlab",
                git_user_name="Agent",
                git_user_email="agent@example.test",
            )
        except Exception as exc:
            assert "fixture-token" not in str(exc)
        else:  # pragma: no cover - the failed clone must raise
            raise AssertionError("failed clone unexpectedly succeeded")
    assert not (tmp_path / "repos" / "repo").exists()


def test_project_credentials_do_not_cross_concurrent_network_calls(
    tmp_path: Path,
) -> None:
    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    projects = [
        _project(tmp_path, token="token-a", forge="gitlab"),
        _project(tmp_path, token="token-b", forge="github"),
    ]
    seen: list[tuple[str, str]] = []

    def fake_run(args, **kwargs):
        env = kwargs["env"]
        seen.append((env["OOMPAH_GIT_PASSWORD"], env["OOMPAH_GIT_USERNAME"]))
        return subprocess.CompletedProcess(args, 0, "", "")

    with patch("oompah.projects.subprocess.run", side_effect=fake_run):
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(
                pool.map(
                    lambda project: store._run_network_git(
                        project, ["git", "fetch", "origin"]
                    ),
                    projects,
                )
            )

    assert sorted(seen) == [("token-a", "oauth2"), ("token-b", "x-access-token")]
