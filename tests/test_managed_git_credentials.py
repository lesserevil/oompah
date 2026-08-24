"""Regression tests for project-scoped credentials on managed Git calls."""

from __future__ import annotations

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

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
from oompah.projects import ProjectError, ProjectStore


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
    assert project.repo_url in observed["args"]
    assert "origin" not in observed["args"]
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


def test_project_network_runner_rejects_embedded_remote_credentials(
    tmp_path: Path,
) -> None:
    secret = "embedded-secret"
    project = _project(tmp_path, token="project-token", forge="gitlab")
    project.repo_url = f"https://actor:{secret}@forge.example/group/repo.git"

    with pytest.raises(ProjectError) as exc_info:
        ProjectStore._run_network_git(project, ["git", "fetch", "origin"])

    assert secret not in str(exc_info.value)
    assert "must not contain credentials" in str(exc_info.value)


def test_project_network_runner_strips_legacy_remote_username(tmp_path: Path) -> None:
    project = _project(tmp_path, token="project-token", forge="gitlab")
    project.repo_url = "https://legacy-actor@forge.example/group/repo.git"

    with patch(
        "oompah.projects.subprocess.run",
        return_value=subprocess.CompletedProcess(["git", "fetch"], 0, "", ""),
    ) as run:
        ProjectStore._run_network_git(project, ["git", "fetch", "origin"])

    command = run.call_args.args[0]
    assert "https://forge.example/group/repo.git" in command
    assert all("legacy-actor" not in argument for argument in command)


def test_project_network_runner_uses_canonical_remote_over_stale_origin(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Managed fetch/push ignore stale checkout and ambient URL authority."""

    canonical = tmp_path / "canonical.git"
    stale = tmp_path / "stale.git"
    seed = tmp_path / "seed"
    checkout = tmp_path / "checkout"
    for remote in (canonical, stale):
        subprocess.run(
            ["git", "init", "--bare", str(remote)],
            check=True,
            capture_output=True,
            text=True,
        )
    subprocess.run(
        ["git", "init", "-b", "main", str(seed)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(seed), "config", "user.name", "Test Agent"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(seed), "config", "user.email", "test@example.test"],
        check=True,
    )
    (seed / "seed.txt").write_text("canonical\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(seed), "add", "seed.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(seed), "commit", "-m", "seed"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(seed), "push", canonical.as_uri(), "HEAD:main"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "clone", stale.as_uri(), str(checkout)],
        check=True,
        capture_output=True,
        text=True,
    )

    ambient_config = tmp_path / "ambient.gitconfig"
    ambient_config.write_text(
        "[url \"ssh://stale.invalid/\"]\n"
        f"\tinsteadOf = {canonical.as_uri()}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(ambient_config))

    project = Project(
        id="managed",
        name="managed",
        repo_url=canonical.as_uri(),
        repo_path=str(checkout),
        forge_kind="gitlab",
    )
    fetched = ProjectStore._run_network_git(
        project,
        ["git", "fetch", "origin"],
    )

    assert fetched.returncode == 0, fetched.stderr
    canonical_head = subprocess.run(
        ["git", f"--git-dir={canonical}", "rev-parse", "refs/heads/main"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tracking_head = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "refs/remotes/origin/main"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    configured_origin = subprocess.run(
        ["git", "-C", str(checkout), "remote", "get-url", "origin"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert tracking_head == canonical_head
    assert configured_origin == stale.as_uri()

    pushed = ProjectStore._run_network_git(
        project,
        ["git", "push", "origin", f"{canonical_head}:refs/heads/canonical-only"],
    )
    assert pushed.returncode == 0, pushed.stderr
    assert (
        subprocess.run(
            [
                "git",
                f"--git-dir={canonical}",
                "rev-parse",
                "refs/heads/canonical-only",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        == canonical_head
    )
    assert subprocess.run(
        [
            "git",
            f"--git-dir={stale}",
            "rev-parse",
            "--verify",
            "refs/heads/canonical-only",
        ],
        check=False,
        capture_output=True,
        text=True,
    ).returncode != 0

    deleted = ProjectStore._run_network_git(
        project,
        ["git", "push", "origin", ":refs/heads/canonical-only"],
    )
    assert deleted.returncode == 0, deleted.stderr
    assert subprocess.run(
        [
            "git",
            f"--git-dir={canonical}",
            "rev-parse",
            "--verify",
            "refs/heads/canonical-only",
        ],
        check=False,
        capture_output=True,
        text=True,
    ).returncode != 0


def test_private_epic_dispatch_refreshes_through_canonical_remote(
    tmp_path: Path,
) -> None:
    """The production epic refresh path cannot inherit a stale SSH origin."""

    canonical = tmp_path / "canonical.git"
    stale = tmp_path / "stale.git"
    seed = tmp_path / "seed"
    checkout = tmp_path / "checkout"
    subprocess.run(
        ["git", "init", "--bare", str(canonical)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "init", "--bare", str(stale)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "init", "-b", "main", str(seed)],
        check=True,
        capture_output=True,
        text=True,
    )
    for key, value in (
        ("user.name", "Test Agent"),
        ("user.email", "test@example.test"),
    ):
        subprocess.run(
            ["git", "-C", str(seed), "config", key, value],
            check=True,
        )
    (seed / "seed.txt").write_text("epic\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(seed), "add", "seed.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(seed), "commit", "-m", "seed"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(seed),
            "push",
            canonical.as_uri(),
            "HEAD:main",
            "HEAD:epic-TRICKLE-127",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "clone", "--branch", "main", canonical.as_uri(), str(checkout)],
        check=True,
        capture_output=True,
        text=True,
    )

    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    project = Project(
        id="trickle",
        name="trickle",
        repo_url=canonical.as_uri(),
        repo_path=str(checkout),
        default_branch="main",
        forge_kind="gitlab",
    )
    store._projects[project.id] = project
    epic_path = store.create_epic_worktree(project.id, "TRICKLE-127")
    subprocess.run(
        ["git", "-C", str(checkout), "remote", "set-url", "origin", stale.as_uri()],
        check=True,
    )

    prepared_path, prepared_head = store.prepare_epic_branch_for_private_dispatch(
        project.id,
        "TRICKLE-127",
    )

    canonical_head = subprocess.run(
        [
            "git",
            f"--git-dir={canonical}",
            "rev-parse",
            "refs/heads/epic-TRICKLE-127",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert prepared_path == epic_path
    assert prepared_head == canonical_head
    assert (
        subprocess.run(
            [
                "git",
                "-C",
                epic_path,
                "config",
                "--get",
                "branch.epic-TRICKLE-127.remote",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        == "origin"
    )


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


def test_sanitize_managed_clone_removes_http_userinfo(tmp_path: Path) -> None:
    """Sanitization must strip HTTP(S) userinfo from remote URLs."""
    from oompah.git_credentials import sanitize_managed_clone_credentials

    # Create a test repo with embedded userinfo in remote URL
    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.test"],
        check=True,
    )

    # Manually set a remote URL with embedded credentials (bypass git remote add
    # which may validate the URL)
    subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "remote.origin.url",
         "https://user:password@github.com/org/repo.git"],
        check=True,
    )

    # Sanitize the clone
    sanitize_managed_clone_credentials(str(repo))

    # Verify userinfo was removed (use git config directly to avoid barrier interference)
    result = subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "remote.origin.url"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "https://github.com/org/repo.git"
    assert "user" not in result.stdout
    assert "password" not in result.stdout


def test_sanitize_managed_clone_removes_credential_helper(tmp_path: Path) -> None:
    """Sanitization must remove credential.helper entries."""
    from oompah.git_credentials import sanitize_managed_clone_credentials

    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "credential.helper", "cache"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "--local",
            "credential.https://github.com.helper",
            "osxkeychain",
        ],
        check=True,
    )

    # Sanitize the clone
    sanitize_managed_clone_credentials(str(repo))

    # Verify credential helpers were removed
    result = subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "--get-regexp", "credential"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1  # No matches
    assert result.stdout.strip() == ""


def test_sanitize_managed_clone_removes_http_extraheader(tmp_path: Path) -> None:
    """Sanitization must remove http.*.extraheader entries."""
    from oompah.git_credentials import sanitize_managed_clone_credentials

    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.test"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "--local",
            "http.https://github.com/.extraheader",
            "Authorization: Bearer token123",
        ],
        check=True,
    )

    # Sanitize the clone
    sanitize_managed_clone_credentials(str(repo))

    # Verify extraheader was removed
    result = subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "--get-regexp", "http"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1  # No matches
    assert result.stdout.strip() == ""


def test_sanitize_managed_clone_normalizes_to_canonical_url(tmp_path: Path) -> None:
    """Sanitization must normalize origin to canonical URL if provided."""
    from oompah.git_credentials import sanitize_managed_clone_credentials

    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.test"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "--local",
            "remote.origin.url",
            "https://stale-url.example/repo.git",
        ],
        check=True,
    )

    canonical = "https://canonical.example/repo.git"

    # Sanitize with canonical URL
    sanitize_managed_clone_credentials(str(repo), canonical_url=canonical)

    # Verify origin was updated to canonical URL (use git config directly)
    result = subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "remote.origin.url"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == canonical


def test_sanitize_managed_clone_removes_canonical_url_rewrite(tmp_path: Path) -> None:
    """A local insteadOf rule must not rewrite canonical HTTPS back to SSH."""
    from oompah.git_credentials import sanitize_managed_clone_credentials

    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
    )
    canonical = "https://gitlab.example/org/repo.git"
    rewrite_key = "url.git@gitlab.example:.insteadof"
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "--local",
            "remote.origin.url",
            canonical,
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "--local",
            rewrite_key,
            "https://gitlab.example/",
        ],
        check=True,
    )

    before = subprocess.run(
        ["git", "-C", str(repo), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert before.stdout.strip() == "git@gitlab.example:org/repo.git"

    sanitize_managed_clone_credentials(str(repo), canonical_url=canonical)

    rewrite = subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "--get-all", rewrite_key],
        capture_output=True,
        text=True,
        check=False,
    )
    assert rewrite.returncode == 1
    after = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "--local",
            "remote.origin.url",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert after.stdout.strip() == canonical


def test_sanitize_managed_clone_preserves_unrelated_url_rewrite(
    tmp_path: Path,
) -> None:
    """Sanitization only removes rewrite prefixes affecting canonical origin."""
    from oompah.git_credentials import sanitize_managed_clone_credentials

    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
    )
    canonical = "https://gitlab.example/org/repo.git"
    unrelated_key = "url.https://mirror.example/.insteadof"
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "--local",
            "remote.origin.url",
            canonical,
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "--local",
            unrelated_key,
            "https://unrelated.example/",
        ],
        check=True,
    )

    sanitize_managed_clone_credentials(str(repo), canonical_url=canonical)

    rewrite = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "--local",
            "--get-all",
            unrelated_key,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert rewrite.stdout.strip() == "https://unrelated.example/"


def test_sanitize_managed_clone_is_idempotent(tmp_path: Path) -> None:
    """Sanitization must be idempotent and not fail on already-clean repos."""
    from oompah.git_credentials import sanitize_managed_clone_credentials

    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.test"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "--local",
            "remote.origin.url",
            "https://github.com/org/repo.git",
        ],
        check=True,
    )

    # First sanitization on clean repo should succeed
    sanitize_managed_clone_credentials(str(repo))

    # Second sanitization should also succeed (idempotent)
    sanitize_managed_clone_credentials(str(repo))

    # Verify repo is still in good state (use git config directly)
    result = subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "remote.origin.url"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "https://github.com/org/repo.git"


def test_direct_rebase_preflight_passes_after_sanitization(
    tmp_path: Path,
) -> None:
    """Direct rebase preflight must pass after sanitization removes credentials."""
    from oompah.orchestrator import Orchestrator
    from oompah.git_credentials import sanitize_managed_clone_credentials

    # Create a test repo with stale credential routes
    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.test"],
        check=True,
    )

    # Add various credential routes that would fail preflight
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "--local",
            "remote.origin.url",
            "https://user:password@github.com/org/repo.git",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "credential.helper", "cache"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "--local",
            "http.https://github.com/.extraheader",
            "Authorization: Bearer token123",
        ],
        check=True,
    )

    # Before sanitization, preflight should fail
    has_credentials = Orchestrator._epic_rebase_workspace_has_remote_write_route(str(repo))
    assert has_credentials, "Preflight should detect credentials before sanitization"

    # Sanitize the repo
    sanitize_managed_clone_credentials(
        str(repo),
        canonical_url="https://canonical.github.com/org/repo.git",
    )

    # After sanitization, preflight should pass
    has_credentials = Orchestrator._epic_rebase_workspace_has_remote_write_route(str(repo))
    assert not has_credentials, "Preflight should pass after sanitization"


def test_sanitize_managed_clone_does_not_affect_other_remotes(
    tmp_path: Path,
) -> None:
    """Sanitization of origin should not affect other remotes."""
    from oompah.git_credentials import sanitize_managed_clone_credentials

    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.test"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "--local",
            "remote.origin.url",
            "https://user:pass@github.com/org/repo.git",
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "--local",
            "remote.upstream.url",
            "https://other-user:other-pass@github.com/upstream/repo.git",
        ],
        check=True,
    )

    # Sanitize with canonical URL for origin
    sanitize_managed_clone_credentials(
        str(repo),
        canonical_url="https://canonical.example/repo.git",
    )

    # Origin should be updated to canonical (use git config directly)
    origin_result = subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "remote.origin.url"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert origin_result.stdout.strip() == "https://canonical.example/repo.git"

    # Upstream should have userinfo stripped but not replaced (use git config directly)
    upstream_result = subprocess.run(
        ["git", "-C", str(repo), "config", "--local", "remote.upstream.url"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert upstream_result.stdout.strip() == "https://github.com/upstream/repo.git"
    assert "other-user" not in upstream_result.stdout
    assert "other-pass" not in upstream_result.stdout
