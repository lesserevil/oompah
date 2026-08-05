"""Tests for project storage and git worktree helpers."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from oompah.models import Project
from oompah.projects import (
    DEFAULT_SOURCE_SYNC_TIMEOUT_S,
    ProjectError,
    ProjectStore,
    _bootstrap_lfs,
    _branch_name_from_worktree_cmd,
    _git_worktree_add_with_recovery,
    github_owner_repo_from_url,
    _is_github_backed,
    _is_ref_namespace_conflict_error,
    _is_stale_worktree_remove_error,
    _is_transient_git_config_lock_error,
    _is_worktree_branch_already_used_error,
    _repo_name_from_url,
    _resolve_ref_namespace_conflict,
    _sanitize_identifier,
    _worktree_consumed_recovery_ref,
    _worktree_recovery_ref,
    github_work_branch_name,
)


def _make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    return repo


def _store(tmp_path) -> ProjectStore:
    return ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "wt"),
    )


def _store_with_one_project(tmp_path):
    repo = _make_repo(tmp_path)
    store = _store(tmp_path)
    project = Project(
        id="proj-sync1",
        name="syncrepo",
        repo_url="https://example.com/x.git",
        repo_path=str(repo),
        branch="main",
        default_branch="main",
    )
    store._projects[project.id] = project
    return store, repo


def _submission_authority_store(tmp_path):
    """Create a managed clone with published epic and plain child branches."""

    origin = tmp_path / "origin.git"
    source = tmp_path / "source"
    managed = tmp_path / "managed"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True)
    subprocess.run(["git", "init", "-b", "main", str(source)], check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=source,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=source,
        check=True,
    )
    (source / "base.txt").write_text("main\n", encoding="utf-8")
    subprocess.run(["git", "add", "base.txt"], cwd=source, check=True)
    subprocess.run(["git", "commit", "-m", "main"], cwd=source, check=True)
    subprocess.run(["git", "remote", "add", "origin", str(origin)], cwd=source, check=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=source, check=True)
    subprocess.run(
        ["git", "symbolic-ref", "HEAD", "refs/heads/main"],
        cwd=origin,
        check=True,
    )

    subprocess.run(["git", "checkout", "-b", "epic-OOMPAH-763"], cwd=source, check=True)
    (source / "epic.txt").write_text("epic\n", encoding="utf-8")
    subprocess.run(["git", "add", "epic.txt"], cwd=source, check=True)
    subprocess.run(["git", "commit", "-m", "epic"], cwd=source, check=True)
    epic_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "push", "-u", "origin", "epic-OOMPAH-763"],
        cwd=source,
        check=True,
    )

    subprocess.run(["git", "checkout", "-b", "OOMPAH-814"], cwd=source, check=True)
    (source / "task.txt").write_text("task\n", encoding="utf-8")
    subprocess.run(["git", "add", "task.txt"], cwd=source, check=True)
    subprocess.run(["git", "commit", "-m", "task"], cwd=source, check=True)
    task_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run(["git", "push", "-u", "origin", "OOMPAH-814"], cwd=source, check=True)

    subprocess.run(["git", "clone", str(origin), str(managed)], check=True)
    store = _store(tmp_path)
    project = Project(
        id="proj-authority",
        name="authority",
        repo_url=str(origin),
        repo_path=str(managed),
        branch="main",
        default_branch="main",
    )
    store._projects[project.id] = project
    return store, source, managed, epic_sha, task_sha


def test_submission_git_authority_proves_exact_plain_branch_and_parent_base(
    tmp_path,
):
    store, _source, _managed, epic_sha, task_sha = _submission_authority_store(
        tmp_path
    )

    authority = store.verify_submission_git_authority(
        "proj-authority",
        task_branch="OOMPAH-814",
        head_sha=task_sha,
        base_branch="epic-OOMPAH-763",
    )

    assert authority.task_branch == "OOMPAH-814"
    assert authority.head_sha == task_sha
    assert authority.base_branch == "epic-OOMPAH-763"
    assert authority.base_sha == epic_sha


def test_submission_git_authority_rejects_remote_head_and_base_mismatch(tmp_path):
    store, _source, _managed, _epic_sha, task_sha = _submission_authority_store(
        tmp_path
    )

    with pytest.raises(ProjectError, match="not submitted head"):
        store.verify_submission_git_authority(
            "proj-authority",
            task_branch="OOMPAH-814",
            head_sha="f" * 40,
            base_branch="epic-OOMPAH-763",
        )
    with pytest.raises(ProjectError, match="not contained"):
        store.verify_submission_git_authority(
            "proj-authority",
            task_branch="OOMPAH-814",
            head_sha=task_sha,
            base_branch="epic-OOMPAH-763",
            base_sha=task_sha,
        )


def test_submission_git_authority_rechecks_task_after_parent_proof(tmp_path):
    store, source, _managed, _epic_sha, task_sha = (
        _submission_authority_store(tmp_path)
    )
    original_run_network_git = store._run_network_git
    parent_reads = 0
    replaced = False

    def run_network_git(project, args, **kwargs):
        nonlocal parent_reads, replaced
        result = original_run_network_git(project, args, **kwargs)
        if (
            args[1:4] == ["ls-remote", "--heads", "origin"]
            and args[4:] == ["refs/heads/epic-OOMPAH-763"]
        ):
            parent_reads += 1
            if parent_reads == 2:
                # Replace the task authority after its first fetch/re-read and
                # after the parent fetch, but before the verifier returns.
                subprocess.run(
                    [
                        "git",
                        "push",
                        "--force",
                        "origin",
                        "epic-OOMPAH-763:OOMPAH-814",
                    ],
                    cwd=source,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                replaced = True
        return result

    with patch.object(
        store,
        "_run_network_git",
        side_effect=run_network_git,
    ):
        with pytest.raises(
            ProjectError,
            match="origin/OOMPAH-814 moved while submission was being verified",
        ):
            store.verify_submission_git_authority(
                "proj-authority",
                task_branch="OOMPAH-814",
                head_sha=task_sha,
                base_branch="epic-OOMPAH-763",
            )

    assert replaced is True


def test_fresh_dispatch_ignores_stale_same_named_remote_branch(tmp_path):
    store, _source, _managed, epic_sha, task_sha = _submission_authority_store(
        tmp_path
    )

    workspace = Path(
        store.create_worktree(
            "proj-authority",
            "OOMPAH-814",
            base_branch="epic-OOMPAH-763",
            branch_name="OOMPAH-814",
        )
    )
    actual = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    assert actual == epic_sha
    assert actual != task_sha


def test_accepted_remote_branch_materializes_exact_head_and_preserves_dirty_worktree(
    tmp_path,
):
    store, _source, _managed, _epic_sha, task_sha = _submission_authority_store(
        tmp_path
    )
    store.verify_submission_git_authority(
        "proj-authority",
        task_branch="OOMPAH-814",
        head_sha=task_sha,
        base_branch="epic-OOMPAH-763",
    )

    workspace = Path(
        store.create_worktree(
            "proj-authority",
            "OOMPAH-814",
            base_branch="epic-OOMPAH-763",
            branch_name="OOMPAH-814",
            prefer_remote_branch=True,
            expected_head_sha=task_sha,
        )
    )
    assert subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip() == task_sha

    dirty = workspace / "repair-notes.txt"
    dirty.write_text("preserve me\n", encoding="utf-8")
    reused = store.create_worktree(
        "proj-authority",
        "OOMPAH-814",
        base_branch="epic-OOMPAH-763",
        branch_name="OOMPAH-814",
        prefer_remote_branch=True,
        expected_head_sha=task_sha,
    )
    assert reused == str(workspace)
    assert dirty.read_text(encoding="utf-8") == "preserve me\n"


def test_accepted_branch_refuses_same_branch_at_a_different_local_head(tmp_path):
    store, _source, _managed, _epic_sha, task_sha = _submission_authority_store(
        tmp_path
    )
    workspace = Path(
        store.create_worktree(
            "proj-authority",
            "OOMPAH-814",
            base_branch="epic-OOMPAH-763",
            branch_name="OOMPAH-814",
            prefer_remote_branch=True,
            expected_head_sha=task_sha,
        )
    )
    (workspace / "late.txt").write_text("late\n", encoding="utf-8")
    subprocess.run(["git", "add", "late.txt"], cwd=workspace, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test User",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "late local commit",
        ],
        cwd=workspace,
        check=True,
    )
    late_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    with pytest.raises(ProjectError, match="not accepted head.*refusing to reset"):
        store.create_worktree(
            "proj-authority",
            "OOMPAH-814",
            base_branch="epic-OOMPAH-763",
            branch_name="OOMPAH-814",
            prefer_remote_branch=True,
            expected_head_sha=task_sha,
        )

    assert subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip() == late_head


def test_accepted_branch_repair_refuses_divergent_registered_worktree(tmp_path):
    store, _source, _managed, _epic_sha, task_sha = _submission_authority_store(
        tmp_path
    )
    store.verify_submission_git_authority(
        "proj-authority",
        task_branch="OOMPAH-814",
        head_sha=task_sha,
        base_branch="epic-OOMPAH-763",
    )
    workspace = Path(
        store.create_worktree(
            "proj-authority",
            "OOMPAH-814",
            base_branch="epic-OOMPAH-763",
            branch_name="OOMPAH-814",
            prefer_remote_branch=True,
            expected_head_sha=task_sha,
        )
    )
    subprocess.run(
        ["git", "checkout", "-b", "operator-divergence"],
        cwd=workspace,
        check=True,
    )

    with pytest.raises(ProjectError, match="refusing to reset it"):
        store.create_worktree(
            "proj-authority",
            "OOMPAH-814",
            base_branch="epic-OOMPAH-763",
            branch_name="OOMPAH-814",
            prefer_remote_branch=True,
            expected_head_sha=task_sha,
        )

    assert subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip() == "operator-divergence"


class TestDetachedAuditWorktree:
    def test_creates_branchless_worktree_at_resolved_commit(self, tmp_path):
        store, _repo = _store_with_one_project(tmp_path)
        sha = "a" * 40
        fetch = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        resolved = subprocess.CompletedProcess([], 0, stdout=f"{sha}\n", stderr="")

        with (
            patch("oompah.projects.subprocess.run", side_effect=[fetch, resolved]),
            patch("oompah.projects._git_worktree_add_with_recovery") as add,
            patch.object(store, "_disable_worktree_hooks") as disable_hooks,
        ):
            path, actual = store.create_detached_audit_worktree(
                "proj-sync1",
                "TASK-1--terminal-audit-attempt-1",
                "origin/main",
            )

        assert actual == sha
        assert path == str(
            tmp_path / "wt" / "syncrepo" / "TASK-1--terminal-audit-attempt-1"
        )
        add.assert_called_once_with(
            ["git", "worktree", "add", "--detach", path, sha],
            cwd=str(_repo),
            wt_path=path,
        )
        disable_hooks.assert_called_once_with(path)

    def test_missing_revision_fails_before_creating_workspace(self, tmp_path):
        store, _repo = _store_with_one_project(tmp_path)
        fetch = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        missing = subprocess.CompletedProcess([], 128, stdout="", stderr="missing")

        with (
            patch("oompah.projects.subprocess.run", side_effect=[fetch, missing]),
            patch("oompah.projects._git_worktree_add_with_recovery") as add,
        ):
            with pytest.raises(ProjectError, match="revision is unavailable"):
                store.create_detached_audit_worktree(
                    "proj-sync1",
                    "TASK-1--terminal-audit-attempt-1",
                    "origin/deleted-branch",
                )

        add.assert_not_called()


class TestRepoNameFromUrl:
    def test_https_with_git(self):
        assert _repo_name_from_url("https://github.com/org/repo.git") == "repo"

    def test_https_without_git(self):
        assert _repo_name_from_url("https://github.com/org/repo") == "repo"

    def test_ssh(self):
        assert _repo_name_from_url("git@github.com:org/repo.git") == "repo"

    def test_local_path(self):
        assert _repo_name_from_url("/home/user/projects/myrepo") == "myrepo"

    def test_empty_returns_unnamed(self):
        assert _repo_name_from_url("") == "unnamed"


class TestGitHubOwnerRepoFromUrl:
    def test_https_github_url(self):
        assert github_owner_repo_from_url("https://github.com/org/repo.git") == (
            "org",
            "repo",
        )

    def test_https_github_url_with_username(self):
        assert github_owner_repo_from_url(
            "https://actor@github.com/example-org/example-repo.git"
        ) == ("example-org", "example-repo")

    def test_ssh_github_url(self):
        assert github_owner_repo_from_url("git@github.com:org/repo.git") == (
            "org",
            "repo",
        )


class TestForgeConfiguration:
    """Persisted-project migration and cross-field forge validation."""

    def test_legacy_project_defaults_to_github_and_serializes_new_fields(self):
        project = Project.from_dict(
            {
                "id": "legacy",
                "name": "legacy-project",
                "repo_url": "https://github.com/acme/legacy.git",
                "repo_path": "/tmp/legacy-project",
                "branch": "main",
                "tracker_kind": "github_issues",
                "tracker_owner": "acme",
                "tracker_repo": "legacy",
                "github_issue_intake_enabled": True,
            }
        )

        assert project.forge_kind == "github"
        assert project.forge_base_url == "https://github.com"
        assert project.tracker_owner == "acme"
        assert project.tracker_repo == "legacy"
        assert project.to_dict()["github_issue_intake_enabled"] is True
        assert project.to_dict()["external_issue_intake_enabled"] is True
        assert project.to_dict()["forge_kind"] == "github"

    def test_gitlab_com_and_nested_self_managed_urls_normalize(self, tmp_path):
        store, _ = _store_with_one_project(tmp_path)

        gitlab_com = store.update(
            "proj-sync1",
            forge_kind="GITLAB",
            forge_base_url="https://gitlab.com/",
            repo_url="git@gitlab.com:group/subgroup/repo.git",
            tracker_kind="gitlab_issues",
        )
        assert gitlab_com.forge_kind == "gitlab"
        assert gitlab_com.forge_base_url == "https://gitlab.com"

        self_managed = store.update(
            "proj-sync1",
            forge_base_url="https://gitlab.example.test/gitlab/",
            repo_url="https://gitlab.example.test/group/subgroup/repo.git",
        )
        assert self_managed.forge_base_url == "https://gitlab.example.test/gitlab"

    @pytest.mark.parametrize(
        ("fields", "message"),
        [
            ({"forge_kind": "bitbucket"}, "forge_kind must be"),
            ({"forge_base_url": "http://gitlab.example.test"}, "https://"),
            (
                {"forge_kind": "github", "tracker_kind": "gitlab_issues"},
                "requires forge_kind='gitlab'",
            ),
            (
                {
                    "forge_kind": "gitlab",
                    "forge_base_url": "https://gitlab.example.test",
                    "repo_url": "https://github.com/acme/repo.git",
                },
                "repo_url host is github.com",
            ),
            (
                {
                    "forge_kind": "gitlab",
                    "forge_base_url": "https://gitlab.example.test",
                    "repo_url": "https://other-gitlab.example.test/acme/repo.git",
                },
                "does not match forge_base_url host",
            ),
        ],
    )
    def test_update_rejects_invalid_or_mismatched_forge_configuration(
        self, tmp_path, fields, message
    ):
        store, _ = _store_with_one_project(tmp_path)

        with pytest.raises(ProjectError, match=message):
            store.update("proj-sync1", **fields)

    def test_external_intake_alias_updates_legacy_persisted_field(self, tmp_path):
        store, _ = _store_with_one_project(tmp_path)

        project = store.update(
            "proj-sync1", external_issue_intake_enabled=True
        )

        assert project.github_issue_intake_enabled is True
        saved = Project.from_dict(project.to_dict())
        assert saved.github_issue_intake_enabled is True

    def test_non_github_url_returns_none_pair(self):
        assert github_owner_repo_from_url("https://gitlab.com/org/repo.git") == (
            None,
            None,
        )


class TestSanitizeIdentifier:
    def test_clean(self):
        assert _sanitize_identifier("task-001") == "task-001"

    def test_special_chars(self):
        assert _sanitize_identifier("foo/bar baz") == "foo_bar_baz"

    def test_preserves_dots(self):
        assert _sanitize_identifier("v1.2.3") == "v1.2.3"


class TestBootstrapLFS:
    def test_success_path_does_not_dirty_repo(self, tmp_path):
        repo = _make_repo(tmp_path)

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "lfs", "install"]:
                return subprocess.CompletedProcess(args, 0, "", "")
            raise AssertionError(f"unexpected command: {args}")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            ok = _bootstrap_lfs(str(repo))

        assert ok is True
        assert not (repo / ".oompah").exists()

    def test_idempotent(self, tmp_path):
        repo = _make_repo(tmp_path)

        with patch("oompah.projects.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0, "", "")
            assert _bootstrap_lfs(str(repo)) is True
            assert _bootstrap_lfs(str(repo)) is True

        assert mock_run.call_count == 2
        assert not (repo / ".oompah").exists()

    def test_no_lfs_installed_returns_false(self, tmp_path):
        repo = _make_repo(tmp_path)

        with patch("oompah.projects.subprocess.run", side_effect=FileNotFoundError):
            assert _bootstrap_lfs(str(repo)) is False

    def test_lfs_install_failure_returns_false(self, tmp_path):
        repo = _make_repo(tmp_path)

        with patch("oompah.projects.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, ["git", "lfs"])
            assert _bootstrap_lfs(str(repo)) is False


class TestCreateProjectTrackerDefaults:
    def test_default_create_uses_oompah_md_and_pauses(self, tmp_path):
        store = _store(tmp_path)
        repo_path = tmp_path / "repos" / "repo"
        repo_path.mkdir(parents=True)
        (repo_path / ".git").mkdir()

        with patch("oompah.projects.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            project = store.create(
                str(repo_path),
                name="repo",
                git_user_name="Test",
                git_user_email="t@example.com",
            )

        assert project.tracker_kind == "oompah_md"
        assert project.paused is True

    def test_github_backed_create_sets_tracker_fields(self, tmp_path):
        store = _store(tmp_path)
        repo_path = tmp_path / "repos" / "repo"
        repo_path.mkdir(parents=True)
        (repo_path / ".git").mkdir()

        with patch("oompah.projects.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            project = store.create(
                str(repo_path),
                name="repo",
                git_user_name="Test",
                git_user_email="t@example.com",
                tracker_kind="github_issues",
                tracker_owner="example-org",
                tracker_repo="oompah",
            )

        assert project.tracker_kind == "github_issues"
        assert project.tracker_owner == "example-org"
        assert project.tracker_repo == "oompah"
        assert project.paused is True

    def test_oompah_md_create_sets_tracker_kind(self, tmp_path):
        store = _store(tmp_path)
        repo_path = tmp_path / "repos" / "repo"
        repo_path.mkdir(parents=True)
        (repo_path / ".git").mkdir()

        with patch("oompah.projects.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            project = store.create(
                str(repo_path),
                name="repo",
                git_user_name="Test",
                git_user_email="t@example.com",
                tracker_kind="oompah_md",
            )

        assert project.tracker_kind == "oompah_md"
        assert project.paused is True

    def test_github_backed_create_infers_tracker_owner_repo_from_github_url(self, tmp_path):
        store = _store(tmp_path)
        repo_path = tmp_path / "repos" / "repo"
        repo_path.mkdir(parents=True)
        (repo_path / ".git").mkdir()

        with patch("oompah.projects.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            project = store.create(
                "https://actor@github.com/example-org/example-repo.git",
                name="repo",
                git_user_name="Test",
                git_user_email="t@example.com",
                tracker_kind="github_issues",
            )

        assert project.tracker_owner == "example-org"
        assert project.tracker_repo == "example-repo"

    def test_oompah_md_github_intake_infers_tracker_owner_repo_from_github_url(self, tmp_path):
        store = _store(tmp_path)
        repo_path = tmp_path / "repos" / "repo"
        repo_path.mkdir(parents=True)
        (repo_path / ".git").mkdir()

        with patch("oompah.projects.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            project = store.create(
                "https://github.com/example-org/example-repo.git",
                name="repo",
                git_user_name="Test",
                git_user_email="t@example.com",
                tracker_kind="oompah_md",
                github_issue_intake_enabled=True,
            )

        assert project.tracker_kind == "oompah_md"
        assert project.github_issue_intake_enabled is True
        assert project.tracker_owner == "example-org"
        assert project.tracker_repo == "example-repo"


class TestSyncProjectSources:
    _SOUND = {"sound": True, "actions": ["ff-pull"], "unrecoverable": [], "reset": False}

    def test_runs_git_self_heal_when_present(self, tmp_path):
        store, repo = _store_with_one_project(tmp_path)
        with patch("oompah.projects.ensure_repo_sound", return_value=dict(self._SOUND)) as heal:
            status = store.sync_project_sources("proj-sync1")

        assert status["git"] == "ok"
        heal.assert_called_once()
        assert heal.call_args.args[0] == str(repo)
        assert heal.call_args.args[1] == "main"

    def test_reset_recovery_is_reported_in_git_status(self, tmp_path):
        store, _repo = _store_with_one_project(tmp_path)
        healed = {"sound": True, "actions": ["hard-reset"], "unrecoverable": [], "reset": True}
        with patch("oompah.projects.ensure_repo_sound", return_value=healed):
            status = store.sync_project_sources("proj-sync1")
        assert status["git"] == "reset:ok"
        assert status.get("heal") == "hard-reset"

    def test_unhealable_checkout_reports_git_failure(self, tmp_path):
        store, _repo = _store_with_one_project(tmp_path)
        unsound = {"sound": False, "actions": [], "unrecoverable": [], "reset": False}
        with patch("oompah.projects.ensure_repo_sound", return_value=unsound):
            status = store.sync_project_sources("proj-sync1")

        assert status["git"].startswith("failed")

    def test_unknown_project_returns_skipped(self, tmp_path):
        store, _repo = _store_with_one_project(tmp_path)
        status = store.sync_project_sources("proj-nope")
        assert status["git"].startswith("skipped")


def _store_with_github_project(tmp_path):
    """Return (store, repo_path) for a GitHub-backed project."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    store = _store(tmp_path)
    project = Project(
        id="proj-gh1",
        name="ghrepo",
        repo_url="https://github.com/org/repo.git",
        repo_path=str(repo),
        branch="main",
        default_branch="main",
        tracker_kind="github_issues",
    )
    store._projects[project.id] = project
    return store, repo


def _store_with_oompah_md_project(tmp_path):
    """Return (store, repo_path) for a native oompah Markdown project."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    store = _store(tmp_path)
    project = Project(
        id="proj-md1",
        name="mdrepo",
        repo_url="https://github.com/org/repo.git",
        repo_path=str(repo),
        branch="main",
        default_branch="main",
        tracker_kind="oompah_md",
    )
    store._projects[project.id] = project
    return store, repo


class TestIsGithubBacked:
    def test_github_issues_kind_is_github_backed(self):
        p = Project(
            id="x", name="x", repo_url="x", repo_path="/x",
            branch="main", default_branch="main", tracker_kind="github_issues",
        )
        assert _is_github_backed(p) is True

    def test_github_issues_with_hyphen_is_github_backed(self):
        p = Project(
            id="x", name="x", repo_url="x", repo_path="/x",
            branch="main", default_branch="main", tracker_kind="github-issues",
        )
        assert _is_github_backed(p) is True

    def test_uppercase_is_normalised(self):
        p = Project(
            id="x", name="x", repo_url="x", repo_path="/x",
            branch="main", default_branch="main", tracker_kind="GITHUB_ISSUES",
        )
        assert _is_github_backed(p) is True

    def test_none_tracker_kind_is_not_github_backed(self):
        p = Project(
            id="x", name="x", repo_url="x", repo_path="/x",
            branch="main", default_branch="main", tracker_kind=None,
        )
        assert _is_github_backed(p) is False

class TestSyncProjectSourcesGitHubBacked:
    """sync_project_sources for GitHub-backed projects reports tracker identity."""

    _SOUND = {"sound": True, "actions": [], "unrecoverable": [], "reset": False}

    def test_github_backed_reports_tracker_key(self, tmp_path):
        store, _repo = _store_with_github_project(tmp_path)
        with patch("oompah.projects.ensure_repo_sound", return_value=dict(self._SOUND)):
            status = store.sync_project_sources("proj-gh1")

        assert status["tracker"] == "github_issues"

    def test_github_backed_git_self_heal_runs(self, tmp_path):
        store, _repo = _store_with_github_project(tmp_path)
        with patch("oompah.projects.ensure_repo_sound", return_value=dict(self._SOUND)) as heal:
            status = store.sync_project_sources("proj-gh1")

        heal.assert_called_once()
        assert status["git"] == "ok"

    def test_github_backed_unsound_checkout_does_not_pause_project(self, tmp_path):
        store, _repo = _store_with_github_project(tmp_path)
        unsound = {
            "sound": False,
            "actions": [],
            "unrecoverable": ["some/file.txt"],
            "reset": False,
        }
        with patch("oompah.projects.ensure_repo_sound", return_value=unsound):
            status = store.sync_project_sources("proj-gh1")

        assert status["git"].startswith("failed")
        project = store._projects["proj-gh1"]
        assert not project.paused

    def test_github_backed_reset_recovery_reported(self, tmp_path):
        store, _repo = _store_with_github_project(tmp_path)
        healed = {"sound": True, "actions": ["hard-reset"], "unrecoverable": [], "reset": True}
        with patch("oompah.projects.ensure_repo_sound", return_value=healed):
            status = store.sync_project_sources("proj-gh1")

        assert status["git"] == "reset:ok"
        assert status.get("heal") == "hard-reset"
        assert status["tracker"] == "github_issues"

    def test_github_backed_no_git_dir_skips_heal(self, tmp_path):
        store, repo = _store_with_github_project(tmp_path)
        # Remove the .git dir to simulate a missing checkout
        (repo / ".git").rmdir()
        with patch("oompah.projects.ensure_repo_sound") as mock_heal:
            status = store.sync_project_sources("proj-gh1")

        mock_heal.assert_not_called()
        assert status["git"] == "skipped: no .git"
        assert status["tracker"] == "github_issues"

    def test_oompah_md_reports_tracker_key(self, tmp_path):
        store, _repo = _store_with_oompah_md_project(tmp_path)
        with patch("oompah.projects.ensure_repo_sound", return_value=dict(self._SOUND)):
            status = store.sync_project_sources("proj-md1")

        assert status["tracker"] == "oompah_md"


class TestSyncAllSources:
    def test_empty_store_returns_empty_dict(self, tmp_path):
        assert _store(tmp_path).sync_all_sources() == {}

    def test_runs_for_every_project(self, tmp_path):
        store = _store(tmp_path)
        for i in range(3):
            repo = tmp_path / f"repo{i}"
            repo.mkdir()
            (repo / ".git").mkdir()
            store._projects[f"p-{i}"] = Project(
                id=f"p-{i}",
                name=f"r{i}",
                repo_url="x",
                repo_path=str(repo),
                branch="main",
                default_branch="main",
            )

        with patch(
            "oompah.projects.ensure_repo_sound",
            return_value={"sound": True, "actions": [], "unrecoverable": [], "reset": False},
        ):
            results = store.sync_all_sources()

        assert set(results) == {"p-0", "p-1", "p-2"}
        assert all(st.get("git") == "ok" for st in results.values())


_LOCK_STDERR = (
    "Preparing worktree (new branch 'task-1')\n"
    "error: could not lock config file .git/config: File exists\n"
    "error: unable to write upstream branch configuration\n"
)


class TestGitWorktreeAddWithRecovery:
    def test_lock_error_with_worktree_created_succeeds(self, tmp_path):
        wt = tmp_path / "wt"

        def fake_run(args, **kwargs):
            wt.mkdir()
            raise subprocess.CalledProcessError(
                returncode=255,
                cmd=args,
                stderr=_LOCK_STDERR,
            )

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            _git_worktree_add_with_recovery(
                ["git", "worktree", "add", "-b", "task-1", str(wt), "origin/main"],
                cwd="/repo",
                wt_path=str(wt),
            )

    def test_lock_error_without_worktree_retries_then_succeeds(self, tmp_path):
        wt = tmp_path / "wt"
        attempts = {"n": 0}

        def fake_run(args, **kwargs):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise subprocess.CalledProcessError(
                    returncode=255,
                    cmd=args,
                    stderr=_LOCK_STDERR,
                )
            wt.mkdir()
            return MagicMock(returncode=0, stdout="", stderr="")

        sleeps = []
        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            _git_worktree_add_with_recovery(
                ["git", "worktree", "add", "-b", "task-1", str(wt), "origin/main"],
                cwd="/repo",
                wt_path=str(wt),
                sleep_fn=lambda seconds: sleeps.append(seconds),
            )

        assert attempts["n"] == 2
        assert sleeps == [0.1]

    def test_non_lock_error_raises_immediately(self, tmp_path):
        wt = tmp_path / "wt"

        def fake_run(args, **kwargs):
            raise subprocess.CalledProcessError(
                returncode=128,
                cmd=args,
                stderr="fatal: invalid reference: origin/main",
            )

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            with pytest.raises(subprocess.CalledProcessError):
                _git_worktree_add_with_recovery(
                    ["git", "worktree", "add", "-b", "task-1", str(wt), "origin/main"],
                    cwd="/repo",
                    wt_path=str(wt),
                    sleep_fn=lambda _seconds: None,
                )


class TestWorktreeErrorClassifiers:
    def test_transient_git_config_lock_detector(self):
        assert _is_transient_git_config_lock_error(_LOCK_STDERR) is True
        assert _is_transient_git_config_lock_error("fatal: invalid ref") is False

    def test_branch_name_extraction(self):
        assert _branch_name_from_worktree_cmd(
            ["git", "worktree", "add", "-b", "task-1", "/wt", "origin/main"]
        ) == "task-1"
        assert _branch_name_from_worktree_cmd(["git", "status"]) is None

    def test_ref_namespace_conflict_detector(self):
        stderr = (
            "fatal: 'refs/heads/task-1/sub' exists; "
            "cannot create 'refs/heads/task-1'\n"
        )
        assert _is_ref_namespace_conflict_error(stderr, "task-1") is True
        assert _is_ref_namespace_conflict_error(stderr, "task-2") is False

    def test_branch_already_used_detector(self):
        assert _is_worktree_branch_already_used_error(
            "fatal: 'task-1' is already used by worktree at '/other'\n"
        ) is True
        assert _is_worktree_branch_already_used_error("fatal: already exists") is False


class TestResolveRefNamespaceConflict:
    def test_renames_nested_local_refs(self):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[:2] == ["git", "for-each-ref"]:
                return MagicMock(returncode=0, stdout="task-1/sub\n", stderr="")
            if args[:3] == ["git", "show-ref", "--verify"]:
                return MagicMock(returncode=1, stdout="", stderr="")
            if args[:3] == ["git", "branch", "-m"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            renames = _resolve_ref_namespace_conflict("/repo", "task-1")

        assert renames == [("task-1/sub", "task-1__sub")]
        assert ["git", "branch", "-m", "task-1/sub", "task-1__sub"] in calls


class TestCreateWorktreeAlreadyUsedFallback:
    def test_create_worktree_reuses_branch_checked_out_elsewhere(self, tmp_path):
        repo = _make_repo(tmp_path)
        store = _store(tmp_path)
        project = Project(
            id="proj-wt",
            name="wtproj",
            repo_url="https://example.com/wtproj.git",
            repo_path=str(repo),
            branch="main",
            default_branch="main",
        )
        store._projects[project.id] = project
        wt_path = store.worktree_path_for(project.id, "task-1")
        hit_used = {"n": 0}

        def fake_run(args, **kwargs):
            if args[:4] == ["git", "worktree", "add", "-b"]:
                hit_used["n"] += 1
                raise subprocess.CalledProcessError(
                    returncode=128,
                    cmd=args,
                    stderr=(
                        "fatal: 'task-1' is already used by worktree "
                        "at '/other/path'\n"
                    ),
                )
            if args[:3] == ["git", "worktree", "add"] and args[2] == wt_path:
                os.makedirs(wt_path, exist_ok=True)
                return MagicMock(returncode=0, stdout="", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            returned = store.create_worktree(project.id, "task-1")

        assert hit_used["n"] == 1
        assert returned == wt_path
        assert os.path.isdir(wt_path)


class TestExistingWorktreeBranchValidation:
    def test_wrong_branch_refuses_to_reset_registered_task_worktree(self, tmp_path):
        repo = tmp_path / "repo"
        subprocess.run(["git", "init", str(repo)], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "Test"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
            check=True,
        )
        (repo / "base.txt").write_text("base\n")
        subprocess.run(["git", "-C", str(repo), "add", "base.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True)
        subprocess.run(["git", "-C", str(repo), "branch", "-M", "main"], check=True)

        store = _store(tmp_path)
        project = Project(
            id="proj-worktree-branch",
            name="worktree-branch",
            repo_url=str(repo),
            repo_path=str(repo),
            branch="main",
            default_branch="main",
        )
        store._projects[project.id] = project
        worktree = store.worktree_path_for(project.id, "TASK-1")
        worktree_branch = "epic-EPIC-1--task-TASK-1"
        os.makedirs(os.path.dirname(worktree), exist_ok=True)
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-b", worktree_branch, worktree],
            check=True,
        )
        original_head = subprocess.run(
            ["git", "-C", worktree, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        unsaved = os.path.join(worktree, "unsaved.txt")
        with open(unsaved, "w", encoding="utf-8") as handle:
            handle.write("must not be cleaned\n")

        with pytest.raises(ProjectError, match="refusing to reset"):
            store.create_worktree(
                project.id,
                "TASK-1",
                branch_name="main",
            )

        assert subprocess.run(
            ["git", "-C", worktree, "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip() == worktree_branch
        assert subprocess.run(
            ["git", "-C", worktree, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip() == original_head
        assert open(unsaved, encoding="utf-8").read() == "must not be cleaned\n"

    def test_dirty_retry_snapshots_staged_unstaged_and_untracked_files(self, tmp_path):
        """Retry reuse must preserve every task-owned dirty file byte-for-byte."""
        repo = tmp_path / "repo"
        subprocess.run(["git", "init", "-b", "main", str(repo)], check=True)
        for key, value in (("user.name", "Test"), ("user.email", "test@example.com")):
            subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
        (repo / ".gitignore").write_text(".oompah-no-hooks/\n", encoding="utf-8")
        (repo / "tracked.txt").write_bytes(b"before\n")
        subprocess.run(
            ["git", "-C", str(repo), "add", ".gitignore", "tracked.txt"],
            check=True,
        )
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True)

        store = _store(tmp_path)
        project = Project(
            id="proj-recovery",
            name="recovery",
            repo_url=str(repo),
            repo_path=str(repo),
            branch="main",
            default_branch="main",
        )
        store._projects[project.id] = project
        worktree = store.worktree_path_for(project.id, "TASK-RECOVERY")
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-b", "TASK-RECOVERY", worktree, "main"],
            check=True,
        )

        generated_hook = Path(worktree) / ".oompah-no-hooks" / "prepare-commit-msg"
        generated_hook.parent.mkdir()
        generated_hook.write_text("generated helper\n", encoding="utf-8")
        (Path(worktree) / "tracked.txt").write_bytes(b"unstaged bytes\n")
        (Path(worktree) / "staged.txt").write_bytes(b"staged bytes\x00\n")
        subprocess.run(["git", "-C", worktree, "add", "staged.txt"], check=True)
        (Path(worktree) / "untracked.bin").write_bytes(b"untracked bytes\xff\n")

        original_head = subprocess.run(
            ["git", "-C", worktree, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        returned = store.create_worktree(project.id, "TASK-RECOVERY")

        assert returned == worktree
        assert (Path(worktree) / "tracked.txt").read_bytes() == b"unstaged bytes\n"
        assert (Path(worktree) / "staged.txt").read_bytes() == b"staged bytes\x00\n"
        assert (Path(worktree) / "untracked.bin").read_bytes() == b"untracked bytes\xff\n"
        assert generated_hook.exists()  # the next dispatch reinstalls the hook
        assert subprocess.run(
            ["git", "-C", worktree, "check-ignore", "--quiet", str(generated_hook)],
            check=False,
        ).returncode == 0
        task_status = store._git_status_for_worktree(worktree)
        assert store._worktree_dirty_paths(task_status.stdout) == []

        context = store.worktree_recovery_context(project.id, "TASK-RECOVERY")
        assert context is not None
        assert context["prior_head"] == original_head
        assert context["branch"] == "TASK-RECOVERY"
        assert set(context["changed_paths"]) == {
            "tracked.txt",
            "staged.txt",
            "untracked.bin",
        }
        assert context["excluded_generated_helpers"] == [
            ".oompah-no-hooks/prepare-commit-msg"
        ]
        assert context["snapshot_head"] == subprocess.run(
            ["git", "-C", worktree, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        snapshot_identity = subprocess.run(
            [
                "git",
                "-C",
                worktree,
                "show",
                "-s",
                "--format=%an%n%ae%n%B",
                str(context["snapshot_head"]),
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert snapshot_identity.startswith(
            "oompah\nlesserevil@users.noreply.github.com\n"
        )
        assert snapshot_identity.rstrip().endswith(
            "🤖 Generated with https://github.com/lesserevil/oompah\n\n"
            "Co-authored-by: oompah <lesserevil@users.noreply.github.com>"
        )
        tree = subprocess.run(
            ["git", "-C", worktree, "ls-tree", "-r", "--name-only", str(context["snapshot_head"])],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        assert ".oompah-no-hooks/prepare-commit-msg" not in tree

    def test_paused_rebase_checkpoint_preserves_branch_index_and_todo(self, tmp_path):
        """A detached paused rebase is checkpointed without consuming its state."""
        repo = tmp_path / "repo"
        subprocess.run(["git", "init", "-b", "main", str(repo)], check=True)
        for key, value in (("user.name", "Test"), ("user.email", "test@example.com")):
            subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
        (repo / "conflict.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "conflict.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True)

        store = _store(tmp_path)
        project = Project(
            id="proj-rebase-recovery",
            name="rebase-recovery",
            repo_url=str(repo),
            repo_path=str(repo),
            branch="main",
            default_branch="main",
        )
        store._projects[project.id] = project
        worktree = store.worktree_path_for(project.id, "TASK-REBASE")
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-b", "TASK-REBASE", worktree, "main"],
            check=True,
        )
        (Path(worktree) / "conflict.txt").write_text("feature\n", encoding="utf-8")
        subprocess.run(["git", "-C", worktree, "add", "conflict.txt"], check=True)
        subprocess.run(["git", "-C", worktree, "commit", "-m", "feature"], check=True)
        (repo / "conflict.txt").write_text("main\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "conflict.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "main conflict"], check=True)

        subprocess.run(
            ["git", "-C", worktree, "rebase", "main"],
            check=False,
            env={"PATH": os.environ["PATH"], "GIT_EDITOR": "true", "GIT_SEQUENCE_EDITOR": "true"},
            capture_output=True,
            text=True,
        )
        (Path(worktree) / "conflict.txt").write_text("resolved feature\n", encoding="utf-8")
        subprocess.run(["git", "-C", worktree, "add", "conflict.txt"], check=True)
        branch_before = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "refs/heads/TASK-REBASE"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        todo_state = subprocess.run(
            ["git", "-C", worktree, "rev-parse", "--git-path", "rebase-merge/git-rebase-todo"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        todo_contents = Path(todo_state).read_text(encoding="utf-8")

        store.create_worktree(project.id, "TASK-REBASE")
        context = store.worktree_recovery_context(project.id, "TASK-REBASE")

        assert context is not None
        assert context["branch"] == "TASK-REBASE"
        assert context["branch_head"] == branch_before
        assert context["operation"]["kind"] == "rebase"
        assert context["operation"]["detached"] is True
        assert context["operation"]["metadata"]["git-rebase-todo"] == todo_contents
        assert subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "refs/heads/TASK-REBASE"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip() == branch_before
        assert subprocess.run(
            ["git", "-C", worktree, "symbolic-ref", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        ).returncode != 0
        assert (Path(worktree) / "conflict.txt").read_text(encoding="utf-8") == (
            "resolved feature\n"
        )
        assert subprocess.run(
            ["git", "-C", worktree, "ls-files", "-u"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout == ""
        assert subprocess.run(
            ["git", "-C", worktree, "cat-file", "-e", f"{context['snapshot_head']}:conflict.txt"],
            check=True,
        ).returncode == 0

    def test_recovery_snapshot_is_idempotent_across_repeated_retries(self, tmp_path):
        """Repeated retry preparation reuses one durable snapshot."""
        repo = tmp_path / "repo"
        subprocess.run(["git", "init", "-b", "main", str(repo)], check=True)
        for key, value in (("user.name", "Test"), ("user.email", "test@example.com")):
            subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
        (repo / "base.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "base.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True)
        store = _store(tmp_path)
        project = Project(
            id="proj-idempotent",
            name="idempotent",
            repo_url=str(repo),
            repo_path=str(repo),
            branch="main",
            default_branch="main",
        )
        store._projects[project.id] = project
        worktree = store.worktree_path_for(project.id, "TASK-IDEMPOTENT")
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-b", "TASK-IDEMPOTENT", worktree, "main"],
            check=True,
        )
        (Path(worktree) / "work.txt").write_text("preserved\n", encoding="utf-8")

        store.create_worktree(project.id, "TASK-IDEMPOTENT")
        first = store.worktree_recovery_context(project.id, "TASK-IDEMPOTENT")
        first_head = subprocess.run(
            ["git", "-C", worktree, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        store.create_worktree(project.id, "TASK-IDEMPOTENT")
        second = store.worktree_recovery_context(project.id, "TASK-IDEMPOTENT")
        second_head = subprocess.run(
            ["git", "-C", worktree, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert first == second
        assert first["snapshot_head"] == first_head == second_head

    def test_recovery_survives_restart_base_advance_and_other_task(self, tmp_path):
        """Recovery refs survive process restart and remain task-scoped."""
        repo = tmp_path / "repo"
        subprocess.run(["git", "init", "-b", "main", str(repo)], check=True)
        for key, value in (("user.name", "Test"), ("user.email", "test@example.com")):
            subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
        (repo / "base.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "base.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True)

        project = Project(
            id="proj-restarted-recovery",
            name="restarted-recovery",
            repo_url=str(repo),
            repo_path=str(repo),
            branch="main",
            default_branch="main",
        )
        first_store = _store(tmp_path)
        first_store._projects[project.id] = project
        first_path = first_store.worktree_path_for(project.id, "TASK-FIRST")
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "worktree",
                "add",
                "-b",
                "TASK-FIRST",
                first_path,
                "main",
            ],
            check=True,
        )
        (Path(first_path) / "first.txt").write_bytes(b"first task bytes\xff\n")
        first_store.create_worktree(project.id, "TASK-FIRST")
        first_context = first_store.worktree_recovery_context(
            project.id, "TASK-FIRST"
        )
        first_head = subprocess.run(
            ["git", "-C", first_path, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        (repo / "base.txt").write_text("advanced\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "base.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "advance main"],
            check=True,
        )

        restarted_store = _store(tmp_path)
        restarted_store._projects[project.id] = project
        assert (
            restarted_store.create_worktree(project.id, "TASK-FIRST")
            == first_path
        )
        restarted_context = restarted_store.worktree_recovery_context(
            project.id, "TASK-FIRST"
        )
        assert restarted_context == first_context
        assert (Path(first_path) / "first.txt").read_bytes() == (
            b"first task bytes\xff\n"
        )
        assert subprocess.run(
            ["git", "-C", first_path, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip() == first_head

        second_path = restarted_store.worktree_path_for(
            project.id, "TASK-SECOND"
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "worktree",
                "add",
                "-b",
                "TASK-SECOND",
                second_path,
                "main",
            ],
            check=True,
        )
        (Path(second_path) / "second.txt").write_text(
            "second task\n", encoding="utf-8"
        )
        restarted_store.create_worktree(project.id, "TASK-SECOND")
        second_context = restarted_store.worktree_recovery_context(
            project.id, "TASK-SECOND"
        )
        assert first_context is not None
        assert second_context is not None
        assert first_context["recovery_ref"] != second_context["recovery_ref"]
        assert restarted_store.worktree_recovery_context(
            project.id, "TASK-FIRST"
        ) == first_context

    def test_snapshot_failure_fails_closed_without_reset_or_clean(self, tmp_path):
        """A failed snapshot leaves the exact dirty worktree for human repair."""
        repo = tmp_path / "repo"
        subprocess.run(["git", "init", "-b", "main", str(repo)], check=True)
        for key, value in (("user.name", "Test"), ("user.email", "test@example.com")):
            subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
        (repo / "base.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "base.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True)
        store = _store(tmp_path)
        project = Project(
            id="proj-failed-recovery",
            name="failed-recovery",
            repo_url=str(repo),
            repo_path=str(repo),
            branch="main",
            default_branch="main",
        )
        store._projects[project.id] = project
        worktree = store.worktree_path_for(project.id, "TASK-FAILED")
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-b", "TASK-FAILED", worktree, "main"],
            check=True,
        )
        dirty = Path(worktree) / "dirty.txt"
        dirty.write_text("do not lose this\n", encoding="utf-8")
        real_run = subprocess.run
        calls = []

        def fail_add(args, **kwargs):
            calls.append(list(args))
            if args[:2] == ["git", "add"]:
                return subprocess.CompletedProcess(args, 1, "", "snapshot denied")
            return real_run(args, **kwargs)

        with patch("oompah.projects.subprocess.run", side_effect=fail_add):
            with pytest.raises(ProjectError, match="could not stage recovery snapshot"):
                store.create_worktree(project.id, "TASK-FAILED")

        assert dirty.read_text(encoding="utf-8") == "do not lose this\n"
        assert not any(call[:2] == ["git", "reset"] for call in calls)
        assert not any(call[:2] == ["git", "clean"] for call in calls)
        assert store.worktree_recovery_context(project.id, "TASK-FAILED") is None

    def test_terminal_cleanup_preserves_dirty_task_worktree(self, tmp_path):
        """Terminal cleanup must snapshot then leave dirty unpublished work."""
        repo = tmp_path / "repo"
        subprocess.run(["git", "init", "-b", "main", str(repo)], check=True)
        for key, value in (("user.name", "Test"), ("user.email", "test@example.com")):
            subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
        (repo / "base.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "base.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True)
        store = _store(tmp_path)
        project = Project(
            id="proj-terminal-recovery",
            name="terminal-recovery",
            repo_url=str(repo),
            repo_path=str(repo),
            branch="main",
            default_branch="main",
        )
        store._projects[project.id] = project
        worktree = store.worktree_path_for(project.id, "TASK-TERMINAL")
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-b", "TASK-TERMINAL", worktree, "main"],
            check=True,
        )
        (Path(worktree) / "dirty.txt").write_bytes(b"must survive\n")

        with pytest.raises(ProjectError, match="dirty task worktree"):
            store.cleanup_terminal_issue(
                project.id,
                "TASK-TERMINAL",
                branch_name="TASK-TERMINAL",
            )

        assert Path(worktree, "dirty.txt").read_bytes() == b"must survive\n"
        assert os.path.isdir(worktree)
        assert store.worktree_recovery_context(project.id, "TASK-TERMINAL") is not None


class TestGithubWorkBranchName:
    """Tests for :func:`github_work_branch_name` (TASK-461.3 AC#1)."""

    def test_simple_project_and_number(self):
        assert github_work_branch_name("trickle", 1234) == "oompah/trickle/gh-1234"

    def test_number_as_string(self):
        assert github_work_branch_name("trickle", "42") == "oompah/trickle/gh-42"

    def test_project_name_is_sanitized(self):
        # Slashes and spaces in the project name are replaced with underscores
        assert github_work_branch_name("my project", 7) == "oompah/my_project/gh-7"

    def test_project_name_with_hyphens_preserved(self):
        assert github_work_branch_name("oompah-tasks", 99) == "oompah/oompah-tasks/gh-99"

    def test_result_has_gh_prefix(self):
        name = github_work_branch_name("myproject", 5)
        assert name.startswith("oompah/myproject/gh-")

    def test_does_not_use_bare_number(self):
        # AC#1: branch names must never rely on bare task numbers
        name = github_work_branch_name("myproject", 1234)
        assert name != "1234"
        assert name != "gh-1234"
        assert "oompah/" in name


class TestCreateWorktreeWithExplicitBranchName:
    """create_worktree() must accept and use a caller-supplied branch_name
    (TASK-461.3: GitHub-safe branch names instead of sanitized identifiers)."""

    def _store_and_project(self, tmp_path):
        repo = _make_repo(tmp_path)
        store = _store(tmp_path)
        project = Project(
            id="proj-ghwt",
            name="ghproj",
            repo_url="https://example.com/ghproj.git",
            repo_path=str(repo),
            branch="main",
            default_branch="main",
        )
        store._projects[project.id] = project
        return store, project

    def test_explicit_branch_name_passed_to_git(self, tmp_path):
        """When branch_name is supplied, git worktree add should use it."""
        store, project = self._store_and_project(tmp_path)
        wt_path = store.worktree_path_for(project.id, "owner/repo#1234")
        branch_used = {}

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "worktree", "add"]:
                # Record the -b <name> argument
                try:
                    b_idx = args.index("-b")
                    branch_used["name"] = args[b_idx + 1]
                except ValueError:
                    pass
                os.makedirs(wt_path, exist_ok=True)
                return MagicMock(returncode=0, stdout="", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        work_branch = github_work_branch_name("ghproj", 1234)
        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            store.create_worktree(
                project.id,
                "owner/repo#1234",
                branch_name=work_branch,
            )

        assert branch_used.get("name") == work_branch

    def test_default_falls_back_to_sanitized_identifier(self, tmp_path):
        """When branch_name is omitted, the sanitized identifier is used."""
        store, project = self._store_and_project(tmp_path)
        identifier = "TASK-789"
        wt_path = store.worktree_path_for(project.id, identifier)
        branch_used = {}

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "worktree", "add"]:
                try:
                    b_idx = args.index("-b")
                    branch_used["name"] = args[b_idx + 1]
                except ValueError:
                    pass
                os.makedirs(wt_path, exist_ok=True)
                return MagicMock(returncode=0, stdout="", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            store.create_worktree(project.id, identifier)

        assert branch_used.get("name") == "TASK-789"

    def test_worktree_path_uses_sanitized_identifier_not_branch_name(self, tmp_path):
        """The worktree directory path is always derived from issue_identifier,
        not from the optional branch_name — so the path stays stable regardless
        of what branch name the caller supplies."""
        store, project = self._store_and_project(tmp_path)
        wt_path = store.worktree_path_for(project.id, "owner/repo#1234")

        def fake_run(args, **kwargs):
            os.makedirs(wt_path, exist_ok=True)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            result = store.create_worktree(
                project.id,
                "owner/repo#1234",
                branch_name="oompah/ghproj/gh-1234",
            )

        assert result == wt_path


class TestRemoveWorktreeCleanup:
    def _store_and_project(self, tmp_path):
        repo = _make_repo(tmp_path)
        store = _store(tmp_path)
        project = Project(
            id="proj-clean",
            name="cleanrepo",
            repo_url="https://example.com/cleanrepo.git",
            repo_path=str(repo),
            branch="main",
            default_branch="main",
        )
        store._projects[project.id] = project
        return store, project

    def test_stale_remove_error_detector(self):
        assert _is_stale_worktree_remove_error(
            "fatal: '/tmp/wt' is not a working tree"
        )
        assert _is_stale_worktree_remove_error(
            "fatal: not a git repository: /tmp/wt/.git"
        )
        assert not _is_stale_worktree_remove_error(
            "fatal: cannot remove a locked working tree"
        )

    def test_remove_worktree_falls_back_for_stale_registered_dir(self, tmp_path):
        store, project = self._store_and_project(tmp_path)
        wt_path = store.worktree_path_for(project.id, "TASK-1")
        os.makedirs(wt_path)
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[:3] == ["git", "worktree", "remove"]:
                raise subprocess.CalledProcessError(
                    returncode=128,
                    cmd=args,
                    stderr=f"fatal: '{wt_path}' is not a working tree",
                )
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            store.remove_worktree(project.id, "TASK-1")

        assert not os.path.exists(wt_path)
        assert ["git", "worktree", "prune"] in calls

    def test_remove_worktree_preserves_locked_dir(self, tmp_path):
        store, project = self._store_and_project(tmp_path)
        wt_path = store.worktree_path_for(project.id, "TASK-1")
        os.makedirs(wt_path)

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "worktree", "remove"]:
                raise subprocess.CalledProcessError(
                    returncode=128,
                    cmd=args,
                    stderr="fatal: cannot remove a locked working tree",
                )
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            with pytest.raises(ProjectError):
                store.remove_worktree(project.id, "TASK-1")

        assert os.path.isdir(wt_path)

    def test_remove_worktree_refuses_valid_worktree_from_another_repo(self, tmp_path):
        store, project = self._store_and_project(tmp_path)
        wt_path = store.worktree_path_for(project.id, "TASK-1")
        os.makedirs(wt_path)

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "worktree", "remove"]:
                raise subprocess.CalledProcessError(
                    returncode=128,
                    cmd=args,
                    stderr=f"fatal: '{wt_path}' is not a working tree",
                )
            if args[:3] == ["git", "-C", wt_path]:
                return MagicMock(returncode=0, stdout="true\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            with pytest.raises(ProjectError, match="valid Git worktree"):
                store.remove_worktree(project.id, "TASK-1")

        assert os.path.isdir(wt_path)

    def test_remove_missing_worktree_prunes_git_metadata(self, tmp_path):
        store, project = self._store_and_project(tmp_path)
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            removed = store.remove_worktree(project.id, "TASK-1")

        assert calls == [["git", "worktree", "prune"]]
        assert removed is False

    def test_remove_epic_worktree_falls_back_for_stale_dir(self, tmp_path):
        store, project = self._store_and_project(tmp_path)
        wt_path = store.epic_worktree_path_for(project.id, "TASK-EPIC")
        os.makedirs(wt_path)

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "worktree", "remove"]:
                raise subprocess.CalledProcessError(
                    returncode=128,
                    cmd=args,
                    stderr=f"fatal: '{wt_path}' is not a working tree",
                )
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            store.remove_epic_worktree(project.id, "TASK-EPIC")

        assert not os.path.exists(wt_path)

    def test_cleanup_stale_worktree_dirs_removes_only_unregistered_children(
        self, tmp_path
    ):
        store, project = self._store_and_project(tmp_path)
        active = store.worktree_path_for(project.id, "TASK-ACTIVE")
        stale_a = store.worktree_path_for(project.id, "TASK-STALE-A")
        stale_b = store.worktree_path_for(project.id, "TASK-STALE-B")
        os.makedirs(active)
        os.makedirs(stale_a)
        os.makedirs(stale_b)

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "worktree", "list"]:
                return MagicMock(
                    returncode=0,
                    stdout=f"worktree {active}\nHEAD abc123\n",
                    stderr="",
                )
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            removed, deferred = store.cleanup_stale_worktree_dirs(
                project.id, limit=1
            )

        assert removed == 1
        assert deferred is True
        assert os.path.isdir(active)
        assert not os.path.exists(stale_a)
        assert os.path.isdir(stale_b)

    def test_cleanup_stale_worktree_dirs_preserves_valid_unregistered_worktree(
        self, tmp_path
    ):
        store, project = self._store_and_project(tmp_path)
        active = store.worktree_path_for(project.id, "TASK-ACTIVE")
        valid_other = store.worktree_path_for(project.id, "TASK-OTHER-REPO")
        stale = store.worktree_path_for(project.id, "TASK-STALE")
        os.makedirs(active)
        os.makedirs(valid_other)
        os.makedirs(stale)

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "worktree", "list"]:
                return MagicMock(
                    returncode=0,
                    stdout=f"worktree {active}\nHEAD abc123\n",
                    stderr="",
                )
            if args[:3] == ["git", "-C", valid_other]:
                return MagicMock(returncode=0, stdout="true\n", stderr="")
            if args[:3] == ["git", "-C", stale]:
                return MagicMock(returncode=128, stdout="", stderr="not a git repo")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            removed, deferred = store.cleanup_stale_worktree_dirs(project.id)

        assert removed == 1
        assert deferred is False
        assert os.path.isdir(active)
        assert os.path.isdir(valid_other)
        assert not os.path.exists(stale)

    def test_terminal_cleanup_deletes_owned_local_and_remote_branch(self, tmp_path):
        store, project = self._store_and_project(tmp_path)
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[:3] == ["git", "worktree", "list"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            if args[:4] == ["git", "show-ref", "--verify", "--quiet"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            changed, skip_reason = store.cleanup_terminal_issue(
                project.id,
                "TASK-42",
                branch_name="TASK-42",
            )

        assert changed is True
        assert skip_reason is None
        assert ["git", "push", "origin", "--delete", "TASK-42"] in calls
        assert ["git", "branch", "-D", "--", "TASK-42"] in calls

    def test_terminal_cleanup_deletes_real_local_and_remote_refs(self, tmp_path):
        remote = tmp_path / "origin.git"
        repo = tmp_path / "checkout"
        subprocess.run(
            ["git", "init", "--bare", str(remote)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "init", "-b", "main", str(repo)],
            check=True,
            capture_output=True,
            text=True,
        )
        for args in (
            ["config", "user.name", "Oompah Test"],
            ["config", "user.email", "oompah@example.test"],
            ["remote", "add", "origin", str(remote)],
        ):
            subprocess.run(
                ["git", *args],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )
        (repo / "README.md").write_text("test\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "README.md"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "main"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "branch", "TASK-42"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "TASK-42"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )

        store = _store(tmp_path)
        project = Project(
            id="proj-real-clean",
            name="real-clean",
            repo_url=str(remote),
            repo_path=str(repo),
            branch="main",
            default_branch="main",
        )
        store._projects[project.id] = project

        changed, skip_reason = store.cleanup_terminal_issue(
            project.id,
            "TASK-42",
            branch_name="TASK-42",
        )

        assert changed is True
        assert skip_reason is None
        assert (
            subprocess.run(
                ["git", "show-ref", "--verify", "--quiet", "refs/heads/TASK-42"],
                cwd=repo,
                check=False,
            ).returncode
            == 1
        )
        assert (
            subprocess.run(
                ["git", "ls-remote", "--heads", "origin", "refs/heads/TASK-42"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            == ""
        )

    @pytest.mark.parametrize("recorded_branch", ["epic-TASK-42", None])
    def test_terminal_cleanup_deletes_legacy_epic_named_task_workspace(
        self, tmp_path, recorded_branch
    ):
        remote = tmp_path / "origin.git"
        repo = tmp_path / "checkout"
        subprocess.run(
            ["git", "init", "--bare", str(remote)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "init", "-b", "main", str(repo)],
            check=True,
            capture_output=True,
            text=True,
        )
        for args in (
            ["config", "user.name", "Oompah Test"],
            ["config", "user.email", "oompah@example.test"],
            ["remote", "add", "origin", str(remote)],
        ):
            subprocess.run(
                ["git", *args],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )
        (repo / "README.md").write_text("test\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "README.md"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "main"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )

        store = _store(tmp_path)
        project = Project(
            id="proj-legacy-clean",
            name="legacy-clean",
            repo_url=str(remote),
            repo_path=str(repo),
            branch="main",
            default_branch="main",
        )
        store._projects[project.id] = project
        legacy_branch = "epic-TASK-42"
        legacy_worktree = store.epic_worktree_path_for(project.id, "TASK-42")
        subprocess.run(
            ["git", "branch", legacy_branch],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", legacy_branch],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "worktree", "add", legacy_worktree, legacy_branch],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )

        changed, skip_reason = store.cleanup_terminal_issue(
            project.id,
            "TASK-42",
            branch_name=recorded_branch,
            is_epic=False,
        )

        assert changed is True
        assert skip_reason is None
        assert not os.path.exists(legacy_worktree)
        assert (
            subprocess.run(
                [
                    "git",
                    "show-ref",
                    "--verify",
                    "--quiet",
                    f"refs/heads/{legacy_branch}",
                ],
                cwd=repo,
                check=False,
            ).returncode
            == 1
        )
        assert (
            subprocess.run(
                ["git", "ls-remote", "--heads", "origin", legacy_branch],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            == ""
        )

    def test_terminal_child_cleanup_preserves_shared_epic_branch(self, tmp_path):
        store, project = self._store_and_project(tmp_path)
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            changed, skip_reason = store.cleanup_terminal_issue(
                project.id,
                "TASK-42",
                branch_name="epic-TASK-EPIC",
            )

        assert changed is False
        assert skip_reason == "shared_epic_branch"
        assert not any(call[:2] == ["git", "push"] for call in calls)
        assert not any(call[:3] == ["git", "branch", "-D"] for call in calls)
        assert store._is_owned_issue_branch(
            project,
            "TASK-42",
            "epic-TASK-42",
            is_epic=False,
        )
        assert not store._is_owned_issue_branch(
            project,
            "TASK-42",
            "epic-TASK-EPIC",
            is_epic=False,
        )

    def test_terminal_cleanup_requires_exact_github_issue_branch(self, tmp_path):
        store, project = self._store_and_project(tmp_path)

        assert store._is_owned_issue_branch(
            project,
            "owner/repo#42",
            "oompah/cleanrepo/gh-42",
            is_epic=False,
            issue_number="42",
        )
        assert not store._is_owned_issue_branch(
            project,
            "owner/repo#42",
            "oompah/cleanrepo/gh-43",
            is_epic=False,
            issue_number="42",
        )

    def test_terminal_cleanup_preserves_local_branch_when_remote_delete_fails(
        self, tmp_path
    ):
        store, project = self._store_and_project(tmp_path)
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[:3] == ["git", "worktree", "list"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            if args[:4] == ["git", "show-ref", "--verify", "--quiet"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            if args[:2] == ["git", "push"]:
                return MagicMock(returncode=1, stdout="", stderr="denied")
            return MagicMock(returncode=0, stdout="", stderr="")

        with (
            patch("oompah.projects.subprocess.run", side_effect=fake_run),
            pytest.raises(ProjectError, match="remote branch delete failed"),
        ):
            store.cleanup_terminal_issue(
                project.id,
                "TASK-42",
                branch_name="TASK-42",
            )

        assert not any(call[:3] == ["git", "branch", "-D"] for call in calls)

    def test_stale_branch_cleanup_deletes_only_merged_unchecked_branches(
        self, tmp_path
    ):
        store, project = self._store_and_project(tmp_path)
        project.branches = ["main", "release/*"]
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[:3] == ["git", "worktree", "list"]:
                return MagicMock(
                    returncode=0,
                    stdout="branch refs/heads/TASK-CHECKED\n",
                    stderr="",
                )
            if args[:3] == ["git", "for-each-ref", "--format=%(refname:short)%09%(upstream:track)"]:
                return MagicMock(
                    returncode=0,
                    stdout=(
                        "TASK-MERGED\t[gone]\n"
                        "TASK-UNMERGED\t[gone]\n"
                        "TASK-CHECKED\t[gone]\n"
                        "release/1.x\t[gone]\n"
                        "TASK-ACTIVE\t[ahead 1]\n"
                    ),
                    stderr="",
                )
            if args[:3] == ["git", "merge-base", "--is-ancestor"]:
                return MagicMock(
                    returncode=0 if args[3] == "TASK-MERGED" else 1,
                    stdout="",
                    stderr="",
                )
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            removed, deferred = store.cleanup_stale_local_branches(project.id)

        assert (removed, deferred) == (1, False)
        assert ["git", "branch", "-D", "--", "TASK-MERGED"] in calls
        assert ["git", "branch", "-D", "--", "TASK-UNMERGED"] not in calls
        assert ["git", "branch", "-D", "--", "TASK-CHECKED"] not in calls
        assert ["git", "branch", "-D", "--", "release/1.x"] not in calls

    def test_stale_branch_cleanup_reports_deferred_at_removal_limit(self, tmp_path):
        store, project = self._store_and_project(tmp_path)

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "worktree", "list"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            if args[:3] == ["git", "for-each-ref", "--format=%(refname:short)%09%(upstream:track)"]:
                return MagicMock(
                    returncode=0,
                    stdout="TASK-1\t[gone]\nTASK-2\t[gone]\n",
                    stderr="",
                )
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            removed, deferred = store.cleanup_stale_local_branches(
                project.id,
                limit=1,
            )

        assert (removed, deferred) == (1, True)


# ---------------------------------------------------------------------------
# Epic repair workspace cleanup (_cleanup_epic_repair_workspace_locked via
# cleanup_terminal_issue with is_epic=True)
# ---------------------------------------------------------------------------


class TestEpicRepairWorkspaceCleanup:
    """cleanup_terminal_issue for a terminal epic also prunes the auxiliary
    task-style repair workspace at <worktree_root>/<project>/<id> on branch
    <id> when it is registered, clean, and fully merged."""

    # ------------------------------------------------------------------
    # Shared bare-remote Git repo setup (mirroring the real-path tests above)
    # ------------------------------------------------------------------

    @staticmethod
    def _setup_bare_remote(tmp_path):
        """Create a bare remote and a local clone with an initial commit on main."""
        remote = tmp_path / "origin.git"
        repo = tmp_path / "checkout"
        subprocess.run(
            ["git", "init", "--bare", str(remote)],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "init", "-b", "main", str(repo)],
            check=True, capture_output=True, text=True,
        )
        for args in (
            ["config", "user.name", "Oompah Test"],
            ["config", "user.email", "oompah@example.test"],
            ["remote", "add", "origin", str(remote)],
        ):
            subprocess.run(
                ["git", *args], cwd=repo, check=True, capture_output=True, text=True,
            )
        (repo / "README.md").write_text("initial\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "README.md"],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "main"],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        return remote, repo

    def _store_and_project(self, tmp_path, remote, repo):
        store = _store(tmp_path)
        project = Project(
            id="proj-epic-repair",
            name="epic-repair",
            repo_url=str(remote),
            repo_path=str(repo),
            branch="main",
            default_branch="main",
        )
        store._projects[project.id] = project
        return store, project

    # ------------------------------------------------------------------
    # Happy path: real bare-remote scenario
    # ------------------------------------------------------------------

    def test_terminal_epic_cleanup_removes_auxiliary_repair_workspace(
        self, tmp_path
    ):
        """The normal aggressive cleanup pass removes a merged, clean repair
        workspace at the task-style path/<id> on branch <id> for a terminal
        epic that has a canonical epic-<id> work_branch."""
        remote, repo = self._setup_bare_remote(tmp_path)
        store, project = self._store_and_project(tmp_path, remote, repo)

        # Primary epic worktree/branch (canonical epic-<id> shape)
        epic_branch = store.epic_branch_name("EPIC-1")       # epic-EPIC-1
        epic_wt = store.epic_worktree_path_for(project.id, "EPIC-1")
        subprocess.run(
            ["git", "branch", epic_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", epic_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "worktree", "add", epic_wt, epic_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        )

        # Auxiliary task-style repair worktree at <id> on branch <id>
        repair_branch = "EPIC-1"
        repair_wt = store.worktree_path_for(project.id, "EPIC-1")
        subprocess.run(
            ["git", "branch", repair_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", repair_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "worktree", "add", repair_wt, repair_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        )

        # Simulate terminal epic cleanup with work_branch=epic-<id>
        changed, skip_reason = store.cleanup_terminal_issue(
            project.id,
            "EPIC-1",
            branch_name=epic_branch,
            is_epic=True,
        )

        assert changed is True
        assert skip_reason is None

        # Primary epic worktree and branch removed
        assert not os.path.exists(epic_wt)
        assert subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{epic_branch}"],
            cwd=repo, check=False,
        ).returncode == 1
        assert subprocess.run(
            ["git", "ls-remote", "--heads", "origin", epic_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        ).stdout == ""

        # Auxiliary repair worktree and branch also removed
        assert not os.path.exists(repair_wt)
        assert subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{repair_branch}"],
            cwd=repo, check=False,
        ).returncode == 1
        assert subprocess.run(
            ["git", "ls-remote", "--heads", "origin", repair_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        ).stdout == ""

    # ------------------------------------------------------------------
    # Guards: dirty, unmerged, shared, different-identifier — all preserved
    # ------------------------------------------------------------------

    def test_epic_repair_cleanup_preserves_dirty_worktree(self, tmp_path):
        """A dirty repair workspace is never removed."""
        remote, repo = self._setup_bare_remote(tmp_path)
        store, project = self._store_and_project(tmp_path, remote, repo)

        repair_branch = "EPIC-DIRTY"
        repair_wt = store.worktree_path_for(project.id, "EPIC-DIRTY")
        subprocess.run(
            ["git", "branch", repair_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "worktree", "add", repair_wt, repair_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        # Make the worktree dirty
        (tmp_path / "checkout" / repair_wt / "dirty.txt").parent.mkdir(
            parents=True, exist_ok=True
        )
        open(os.path.join(repair_wt, "dirty.txt"), "w").close()
        subprocess.run(
            ["git", "add", "dirty.txt"],
            cwd=repair_wt, check=True, capture_output=True, text=True,
        )

        changed = store.cleanup_terminal_issue(
            project.id,
            "EPIC-DIRTY",
            branch_name=store.epic_branch_name("EPIC-DIRTY"),
            is_epic=True,
        )

        # Repair workspace preserved (dirty)
        assert os.path.isdir(repair_wt)
        assert subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{repair_branch}"],
            cwd=repo, check=False,
        ).returncode == 0

    def test_epic_repair_cleanup_preserves_unmerged_head(self, tmp_path):
        """A repair workspace whose head is not merged is never removed."""
        remote, repo = self._setup_bare_remote(tmp_path)
        store, project = self._store_and_project(tmp_path, remote, repo)

        repair_branch = "EPIC-UNMERGED"
        repair_wt = store.worktree_path_for(project.id, "EPIC-UNMERGED")
        subprocess.run(
            ["git", "branch", repair_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", repair_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "worktree", "add", repair_wt, repair_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        # Add an unmerged commit on the repair branch
        (tmp_path / "new.txt").write_text("extra\n", encoding="utf-8")
        import shutil
        shutil.copy(str(tmp_path / "new.txt"), os.path.join(repair_wt, "new.txt"))
        subprocess.run(
            ["git", "add", "new.txt"],
            cwd=repair_wt, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "unmerged"],
            cwd=repair_wt, check=True, capture_output=True, text=True,
        )

        changed = store.cleanup_terminal_issue(
            project.id,
            "EPIC-UNMERGED",
            branch_name=store.epic_branch_name("EPIC-UNMERGED"),
            is_epic=True,
        )

        # Repair workspace preserved (unmerged)
        assert os.path.isdir(repair_wt)
        assert subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{repair_branch}"],
            cwd=repo, check=False,
        ).returncode == 0

    def test_epic_repair_cleanup_preserves_shared_branch(self, tmp_path):
        """A repair branch checked out in an additional worktree is never removed."""
        remote, repo = self._setup_bare_remote(tmp_path)
        store, project = self._store_and_project(tmp_path, remote, repo)

        repair_branch = "EPIC-SHARED"
        repair_wt = store.worktree_path_for(project.id, "EPIC-SHARED")
        # Create a SECOND worktree on the same branch (simulating shared use)
        extra_wt = str(tmp_path / "extra-wt")
        subprocess.run(
            ["git", "branch", repair_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", repair_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "worktree", "add", repair_wt, repair_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        # The repair branch is now checked out in repair_wt. A second worktree
        # on the same branch isn't directly possible in git; instead we verify
        # that the _delete_owned_issue_branch_locked "checked out elsewhere"
        # guard fires by mocking the registered branches after removing the wt.
        # We test the direct guard path: branch still in registered set → skip.
        calls = []
        real_run = subprocess.run

        def intercept(args, **kwargs):
            calls.append(list(args))
            if args[:3] == ["git", "merge-base"]:
                # Passes the merge check — head IS an ancestor
                return MagicMock(returncode=0, stdout="", stderr="")
            if args[:3] == ["git", "status"]:
                # Clean worktree
                return MagicMock(returncode=0, stdout="", stderr="")
            if args[:3] == ["git", "symbolic-ref"]:
                return MagicMock(returncode=0, stdout=repair_branch + "\n", stderr="")
            if args[:3] == ["git", "worktree", "list"]:
                # After removal, report branch as STILL checked out elsewhere
                return MagicMock(
                    returncode=0,
                    stdout=(
                        f"worktree {repair_wt}\n"
                        f"HEAD abc\n"
                        f"branch refs/heads/{repair_branch}\n"
                        f"\n"
                        f"worktree {extra_wt}\n"
                        f"HEAD abc\n"
                        f"branch refs/heads/{repair_branch}\n"
                        f"\n"
                    ),
                    stderr="",
                )
            if args[:3] == ["git", "worktree", "remove"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return real_run(args, **kwargs)

        with patch("oompah.projects.subprocess.run", side_effect=intercept):
            changed = store.cleanup_terminal_issue(
                project.id,
                "EPIC-SHARED",
                branch_name=store.epic_branch_name("EPIC-SHARED"),
                is_epic=True,
            )

        # Branch was NOT deleted because it's still checked out elsewhere
        assert ["git", "push", "origin", "--delete", repair_branch] not in calls
        assert ["git", "branch", "-D", "--", repair_branch] not in calls

    def test_epic_repair_cleanup_skips_non_matching_identifier(self, tmp_path):
        """A repair workspace with a different-identifier branch is never touched."""
        remote, repo = self._setup_bare_remote(tmp_path)
        store, project = self._store_and_project(tmp_path, remote, repo)

        # Create a task-style worktree at EPIC-1's path, but with a DIFFERENT branch
        repair_wt = store.worktree_path_for(project.id, "EPIC-1")
        other_branch = "EPIC-999"
        subprocess.run(
            ["git", "branch", other_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", other_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "worktree", "add", repair_wt, other_branch],
            cwd=repo, check=True, capture_output=True, text=True,
        )

        changed = store.cleanup_terminal_issue(
            project.id,
            "EPIC-1",
            branch_name=store.epic_branch_name("EPIC-1"),
            is_epic=True,
        )

        # The workspace at EPIC-1's path with EPIC-999 branch must be preserved
        assert os.path.isdir(repair_wt)
        assert subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{other_branch}"],
            cwd=repo, check=False,
        ).returncode == 0

    def test_epic_repair_cleanup_skips_unregistered_directory(self, tmp_path):
        """A directory at the repair path that is not a registered worktree is skipped."""
        remote, repo = self._setup_bare_remote(tmp_path)
        store, project = self._store_and_project(tmp_path, remote, repo)

        # Create just a directory at the repair path (not a git worktree)
        repair_wt = store.worktree_path_for(project.id, "EPIC-UNREG")
        os.makedirs(repair_wt)

        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[:3] == ["git", "worktree", "list"]:
                # The path is NOT registered
                return MagicMock(returncode=0, stdout="", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            store.cleanup_terminal_issue(
                project.id,
                "EPIC-UNREG",
                branch_name=store.epic_branch_name("EPIC-UNREG"),
                is_epic=True,
            )

        # Directory is preserved; no symbolic-ref, status, or merge-base calls
        assert os.path.isdir(repair_wt)
        assert not any(
            args[:2] == ["git", "symbolic-ref"] for args in calls
        )

    def test_non_epic_cleanup_does_not_trigger_repair_path(self, tmp_path):
        """cleanup_terminal_issue for a non-epic issue does not attempt
        to clean up an auxiliary repair workspace (is_epic=False path)."""
        remote, repo = self._setup_bare_remote(tmp_path)
        store, project = self._store_and_project(tmp_path, remote, repo)

        repair_wt = store.worktree_path_for(project.id, "TASK-NE")
        subprocess.run(
            ["git", "branch", "TASK-NE"],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "TASK-NE"],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "worktree", "add", repair_wt, "TASK-NE"],
            cwd=repo, check=True, capture_output=True, text=True,
        )

        # Non-epic cleanup: removes the task worktree normally
        changed, skip_reason = store.cleanup_terminal_issue(
            project.id,
            "TASK-NE",
            branch_name="TASK-NE",
            is_epic=False,
        )
        assert changed is True
        assert skip_reason is None
        # Worktree was removed (normal path, not repair cleanup)
        assert not os.path.isdir(repair_wt)


# ---------------------------------------------------------------------------
# Direct shared-epic maintenance cleanup
# ---------------------------------------------------------------------------


class TestDirectEpicAuxiliaryCleanup:
    """Prune only the private checkout left by a direct epic task."""

    @staticmethod
    def _setup_bare_remote(tmp_path):
        remote = tmp_path / "origin.git"
        repo = tmp_path / "checkout"
        subprocess.run(
            ["git", "init", "--bare", str(remote)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "init", "-b", "main", str(repo)],
            check=True,
            capture_output=True,
            text=True,
        )
        for args in (
            ["config", "user.name", "Oompah Test"],
            ["config", "user.email", "oompah@example.test"],
            ["remote", "add", "origin", str(remote)],
        ):
            subprocess.run(
                ["git", *args],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )
        (repo / "README.md").write_text("initial\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "README.md"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "main"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        return remote, repo

    def _make_auxiliary(self, tmp_path, *, unique=False):
        remote, repo = self._setup_bare_remote(tmp_path)
        store = _store(tmp_path)
        project = Project(
            id="proj-direct-epic",
            name="direct-epic",
            repo_url=str(remote),
            repo_path=str(repo),
            branch="main",
            default_branch="main",
        )
        store._projects[project.id] = project
        parent = "EXOCOMP-130"
        issue = "EXOCOMP-240"
        epic_branch = store.epic_branch_name(parent)
        derived_branch = store.epic_child_branch_name(parent, issue)
        epic_path = store.epic_worktree_path_for(project.id, parent)
        auxiliary_path = store.worktree_path_for(project.id, issue)

        subprocess.run(
            ["git", "branch", epic_branch],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", epic_branch],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "worktree", "add", epic_path, epic_branch],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "branch", derived_branch, epic_branch],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "worktree", "add", auxiliary_path, derived_branch],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        if unique:
            (Path(auxiliary_path) / "maintenance.txt").write_text(
                "rebased head\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "add", "maintenance.txt"],
                cwd=auxiliary_path,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "rebase maintenance"],
                cwd=auxiliary_path,
                check=True,
                capture_output=True,
                text=True,
            )
        return {
            "remote": remote,
            "repo": repo,
            "store": store,
            "project": project,
            "parent": parent,
            "issue": issue,
            "epic_branch": epic_branch,
            "derived_branch": derived_branch,
            "epic_path": epic_path,
            "auxiliary_path": auxiliary_path,
        }

    @staticmethod
    def _push_trusted_sibling(fixture):
        sibling = fixture["store"].epic_child_branch_name(
            fixture["parent"],
            "EXOCOMP-145",
        )
        subprocess.run(
            ["git", "push", "origin", f"HEAD:refs/heads/{sibling}"],
            cwd=fixture["auxiliary_path"],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "fetch", "origin", sibling],
            cwd=fixture["repo"],
            check=True,
            capture_output=True,
            text=True,
        )
        return sibling

    def _cleanup(self, fixture):
        return fixture["store"].cleanup_terminal_issue(
            fixture["project"].id,
            fixture["issue"],
            branch_name=fixture["epic_branch"],
            is_epic=False,
        )

    def _publish_auxiliary_head(self, fixture):
        old = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=fixture["epic_path"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        (Path(fixture["auxiliary_path"]) / "published.txt").write_text(
            "published\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "published.txt"],
            cwd=fixture["auxiliary_path"],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "publish epic rebase"],
            cwd=fixture["auxiliary_path"],
            check=True,
            capture_output=True,
            text=True,
        )
        published = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=fixture["auxiliary_path"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            [
                "git",
                "push",
                "origin",
                f"HEAD:refs/heads/{fixture['epic_branch']}",
            ],
            cwd=fixture["auxiliary_path"],
            check=True,
            capture_output=True,
            text=True,
        )
        return old, published

    def test_reconciles_clean_registered_epic_after_direct_publication(self, tmp_path):
        fixture = self._make_auxiliary(tmp_path)
        old, published = self._publish_auxiliary_head(fixture)

        result = fixture["store"].reconcile_published_epic_worktree(
            fixture["project"].id,
            fixture["parent"],
            published,
            expected_old_sha=old,
            maintenance_identifier=fixture["issue"],
        )

        assert result.status == "reconciled"
        assert result.completed is True
        assert subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=fixture["epic_path"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip() == published
        # The private checkout and its branch are durable evidence; the
        # reconciliation only realigns the registered shared epic checkout.
        assert os.path.isdir(fixture["auxiliary_path"])
        assert subprocess.run(
            [
                "git",
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{fixture['derived_branch']}",
            ],
            cwd=fixture["repo"],
            check=False,
        ).returncode == 0

    @pytest.mark.parametrize("change_kind", ["dirty", "active", "recovery", "divergent"])
    def test_reconciliation_preserves_unsafe_epic_checkout_states(
        self, tmp_path, change_kind
    ):
        fixture = self._make_auxiliary(tmp_path)
        old, published = self._publish_auxiliary_head(fixture)
        epic_path = Path(fixture["epic_path"])

        if change_kind == "dirty":
            (epic_path / "keep-me.txt").write_text("do not erase\n", encoding="utf-8")
        elif change_kind == "active":
            git_dir = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=epic_path,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            (Path(git_dir) / "rebase-merge").mkdir()
        elif change_kind == "recovery":
            subprocess.run(
                ["git", "update-ref", _worktree_recovery_ref(fixture["issue"]), old],
                cwd=fixture["repo"],
                check=True,
                capture_output=True,
                text=True,
            )
        else:
            (epic_path / "divergent.txt").write_text("unproven\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", "divergent.txt"],
                cwd=epic_path,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "unproven local divergence"],
                cwd=epic_path,
                check=True,
                capture_output=True,
                text=True,
            )

        result = fixture["store"].reconcile_published_epic_worktree(
            fixture["project"].id,
            fixture["parent"],
            published,
            expected_old_sha=old,
            maintenance_identifier=fixture["issue"],
        )

        expected_status = {
            "dirty": "dirty",
            "active": "active_operation",
            "recovery": "recovery",
            "divergent": "divergent",
        }[change_kind]
        assert result.status == expected_status
        assert result.completed is False
        if change_kind == "dirty":
            assert (epic_path / "keep-me.txt").exists()
        if change_kind == "divergent":
            assert (epic_path / "divergent.txt").exists()
        assert subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", _worktree_recovery_ref(fixture["issue"])],
            cwd=fixture["repo"],
            check=False,
        ).returncode == (0 if change_kind == "recovery" else 1)

    def test_prunes_direct_epic_auxiliary_and_only_its_local_ref(self, tmp_path):
        fixture = self._make_auxiliary(tmp_path, unique=True)
        sibling = self._push_trusted_sibling(fixture)

        changed, skip_reason = self._cleanup(fixture)

        assert (changed, skip_reason) == (True, None)
        assert not os.path.exists(fixture["auxiliary_path"])
        assert subprocess.run(
            [
                "git",
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{fixture['derived_branch']}",
            ],
            cwd=fixture["repo"],
            check=False,
        ).returncode == 1
        # The authoritative epic checkout/ref and the other private task ref
        # remain available as durable evidence after local pruning.
        assert os.path.isdir(fixture["epic_path"])
        assert subprocess.run(
            ["git", "symbolic-ref", "--short", "HEAD"],
            cwd=fixture["epic_path"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip() == fixture["epic_branch"]
        for branch in (fixture["epic_branch"], sibling):
            assert subprocess.run(
                ["git", "ls-remote", "--heads", "origin", branch],
                cwd=fixture["repo"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout

        # A second maintenance pass is an idempotent no-op and does not
        # attempt to remove the shared epic branch or emit a failure.
        assert self._cleanup(fixture) == (False, "shared_epic_branch")

    @pytest.mark.parametrize("change_kind", ["staged", "unstaged", "untracked"])
    def test_preserves_dirty_auxiliary_worktree(self, tmp_path, change_kind):
        fixture = self._make_auxiliary(tmp_path)
        dirty = Path(fixture["auxiliary_path"]) / f"{change_kind}.txt"
        dirty.write_text("keep me\n", encoding="utf-8")
        if change_kind == "staged":
            subprocess.run(
                ["git", "add", dirty.name],
                cwd=fixture["auxiliary_path"],
                check=True,
                capture_output=True,
                text=True,
            )

        changed, skip_reason = self._cleanup(fixture)

        assert changed is False
        assert skip_reason == "direct_epic_auxiliary_dirty"
        assert dirty.exists()
        assert os.path.isdir(fixture["auxiliary_path"])

    def test_preserves_recovery_ref(self, tmp_path):
        fixture = self._make_auxiliary(tmp_path)
        recovery_ref = _worktree_recovery_ref(fixture["issue"])
        subprocess.run(
            ["git", "update-ref", recovery_ref, "HEAD"],
            cwd=fixture["repo"],
            check=True,
            capture_output=True,
            text=True,
        )

        changed, skip_reason = self._cleanup(fixture)

        assert (changed, skip_reason) == (False, "direct_epic_auxiliary_recovery")
        assert os.path.isdir(fixture["auxiliary_path"])
        assert subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", recovery_ref],
            cwd=fixture["repo"],
            check=False,
        ).returncode == 0

    def test_preserves_paused_rebase(self, tmp_path):
        fixture = self._make_auxiliary(tmp_path)
        git_dir = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=fixture["auxiliary_path"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        rebase_dir = Path(git_dir) / "rebase-merge"
        rebase_dir.mkdir()
        (rebase_dir / "head-name").write_text(
            f"refs/heads/{fixture['derived_branch']}\n",
            encoding="utf-8",
        )

        changed, skip_reason = self._cleanup(fixture)

        assert (changed, skip_reason) == (
            False,
            "direct_epic_auxiliary_active_operation",
        )
        assert os.path.isdir(fixture["auxiliary_path"])

    def test_preserves_unique_unpublished_head_without_remote_evidence(self, tmp_path):
        fixture = self._make_auxiliary(tmp_path, unique=True)

        changed, skip_reason = self._cleanup(fixture)

        assert (changed, skip_reason) == (
            False,
            "direct_epic_auxiliary_unpublished",
        )
        assert os.path.isdir(fixture["auxiliary_path"])
        assert subprocess.run(
            [
                "git",
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{fixture['derived_branch']}",
            ],
            cwd=fixture["repo"],
            check=False,
        ).returncode == 0

    def test_preserves_mismatched_issue_suffix(self, tmp_path):
        fixture = self._make_auxiliary(tmp_path)
        wrong_branch = fixture["store"].epic_child_branch_name(
            fixture["parent"],
            "EXOCOMP-999",
        )
        subprocess.run(
            ["git", "worktree", "remove", fixture["auxiliary_path"], "--force"],
            cwd=fixture["repo"],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "branch", wrong_branch, fixture["epic_branch"]],
            cwd=fixture["repo"],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "worktree", "add", fixture["auxiliary_path"], wrong_branch],
            cwd=fixture["repo"],
            check=True,
            capture_output=True,
            text=True,
        )

        with pytest.raises(ProjectError, match="expected branch"):
            self._cleanup(fixture)
        assert os.path.isdir(fixture["auxiliary_path"])
        assert subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{wrong_branch}"],
            cwd=fixture["repo"],
            check=False,
        ).returncode == 0

    def test_preserves_shared_private_checkout(self, tmp_path):
        fixture = self._make_auxiliary(tmp_path)
        auxiliary_realpath = os.path.realpath(fixture["auxiliary_path"])
        with patch.object(
            fixture["store"],
            "_registered_worktree_branch_paths",
            return_value={
                fixture["derived_branch"]: {
                    auxiliary_realpath,
                    str(tmp_path / "another-task-worktree"),
                }
            },
        ):
            changed, skip_reason = self._cleanup(fixture)

        assert (changed, skip_reason) == (
            False,
            "direct_epic_auxiliary_shared_checkout",
        )
        assert os.path.isdir(fixture["auxiliary_path"])

    def test_preserves_unregistered_cross_project_checkout(self, tmp_path):
        fixture = self._make_auxiliary(tmp_path)
        subprocess.run(
            ["git", "worktree", "remove", fixture["auxiliary_path"], "--force"],
            cwd=fixture["repo"],
            check=True,
            capture_output=True,
            text=True,
        )
        # A different repository happens to occupy the managed-looking path.
        # Registration in the project repository is required before inspection.
        subprocess.run(
            ["git", "init", "-b", fixture["derived_branch"], fixture["auxiliary_path"]],
            check=True,
            capture_output=True,
            text=True,
        )

        changed, skip_reason = self._cleanup(fixture)

        assert (changed, skip_reason) == (
            False,
            "direct_epic_auxiliary_unregistered",
        )
        assert os.path.isdir(fixture["auxiliary_path"])


# ---------------------------------------------------------------------------
# ProjectStore.find_by_name
# ---------------------------------------------------------------------------


class TestNestedEpicTerminalCleanup:
    """Nested epic cleanup follows the recorded parent-target landing proof."""

    @staticmethod
    def _setup_repo(tmp_path, *, landing: str | None = "merge"):
        remote = tmp_path / "origin.git"
        repo = tmp_path / "checkout"
        subprocess.run(
            ["git", "init", "--bare", str(remote)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "init", "-b", "main", str(repo)],
            check=True,
            capture_output=True,
            text=True,
        )
        for args in (
            ["config", "user.name", "Oompah Test"],
            ["config", "user.email", "oompah@example.test"],
            ["remote", "add", "origin", str(remote)],
        ):
            subprocess.run(
                ["git", *args],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )
        (repo / "README.md").write_text("initial\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True)
        subprocess.run(
            ["git", "push", "-u", "origin", "main"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )

        store = _store(tmp_path)
        project = Project(
            id="proj-nested-terminal",
            name="nested-terminal",
            repo_url=str(remote),
            repo_path=str(repo),
            branch="main",
            default_branch="main",
        )
        store._projects[project.id] = project

        parent_branch = store.epic_branch_name("PARENT")
        source_branch = store.epic_branch_name("CHILD")
        subprocess.run(["git", "branch", parent_branch], cwd=repo, check=True)
        subprocess.run(
            ["git", "push", "-u", "origin", parent_branch],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(["git", "branch", source_branch], cwd=repo, check=True)
        subprocess.run(
            ["git", "push", "-u", "origin", source_branch],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )

        worktree = store.epic_worktree_path_for(project.id, "CHILD")
        subprocess.run(
            ["git", "worktree", "add", worktree, source_branch],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        (Path(worktree) / "child.txt").write_text("nested work\n", encoding="utf-8")
        subprocess.run(["git", "add", "child.txt"], cwd=worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "nested child"],
            cwd=worktree,
            check=True,
            capture_output=True,
            text=True,
        )
        source_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=worktree,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        if landing is not None:
            subprocess.run(["git", "checkout", parent_branch], cwd=repo, check=True)
            merge_args = (
                ["git", "merge", "--no-ff", "--no-edit", source_branch]
                if landing == "merge"
                else ["git", "merge", "--ff-only", source_branch]
            )
            subprocess.run(
                merge_args,
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "push", "origin", parent_branch],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)

        return store, project, worktree, source_branch, parent_branch, source_head

    @pytest.mark.parametrize("landing", ["merge", "fast-forward"])
    def test_prunes_clean_nested_epic_after_parent_landing(
        self, tmp_path, landing
    ):
        store, project, worktree, source, target, source_head = self._setup_repo(
            tmp_path, landing=landing
        )
        subprocess.run(
            ["git", "push", "origin", "--delete", source],
            cwd=project.repo_path,
            check=True,
            capture_output=True,
            text=True,
        )

        changed, skip_reason = store.cleanup_terminal_issue(
            project.id,
            "CHILD",
            branch_name=source,
            is_epic=True,
            target_branch=target,
            review_head=source_head,
            require_target_branch=True,
        )

        assert (changed, skip_reason) == (True, None)
        assert not os.path.isdir(worktree)
        assert subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{source}"],
            cwd=project.repo_path,
            check=False,
        ).returncode == 1

    def test_target_fetch_failure_preserves_source_worktree_and_ref(self, tmp_path):
        store, project, worktree, source, target, source_head = self._setup_repo(
            tmp_path
        )
        with patch.object(
            store,
            "_run_network_git",
            return_value=subprocess.CompletedProcess(
                ["git", "fetch"], 1, "", "target unavailable"
            ),
        ):
            with pytest.raises(ProjectError, match="target branch refresh failed"):
                store.cleanup_terminal_issue(
                    project.id,
                    "CHILD",
                    branch_name=source,
                    is_epic=True,
                    target_branch=target,
                    review_head=source_head,
                    require_target_branch=True,
                )
        assert os.path.isdir(worktree)
        assert subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{source}"],
            cwd=project.repo_path,
            check=False,
        ).returncode == 0

    def test_unreachable_head_and_wrong_target_are_preserved(self, tmp_path):
        store, project, worktree, source, target, source_head = self._setup_repo(
            tmp_path, landing=None
        )
        wrong_target = store.epic_branch_name("OTHER")
        subprocess.run(["git", "branch", wrong_target], cwd=project.repo_path, check=True)
        subprocess.run(
            ["git", "push", "-u", "origin", wrong_target],
            cwd=project.repo_path,
            check=True,
            capture_output=True,
            text=True,
        )
        with pytest.raises(ProjectError, match="not reachable"):
            store.cleanup_terminal_issue(
                project.id,
                "CHILD",
                branch_name=source,
                is_epic=True,
                target_branch=wrong_target,
                review_head=source_head,
                require_target_branch=True,
            )
        assert os.path.isdir(worktree)
        assert target != wrong_target

    def test_dirty_and_active_nested_worktrees_are_preserved(self, tmp_path):
        store, project, worktree, source, target, source_head = self._setup_repo(
            tmp_path
        )
        (Path(worktree) / "uncommitted.txt").write_text("keep\n", encoding="utf-8")
        with pytest.raises(ProjectError, match="dirty task worktree"):
            store.cleanup_terminal_issue(
                project.id,
                "CHILD",
                branch_name=source,
                is_epic=True,
                target_branch=target,
                review_head=source_head,
                require_target_branch=True,
            )
        assert os.path.isdir(worktree)

        (Path(worktree) / "uncommitted.txt").unlink()
        git_dir = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=worktree,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        git_dir_path = Path(git_dir)
        if not git_dir_path.is_absolute():
            git_dir_path = Path(worktree) / git_dir_path
        (git_dir_path / "rebase-merge").mkdir()
        (git_dir_path / "rebase-merge" / "head-name").write_text(
            f"refs/heads/{source}\n", encoding="utf-8"
        )
        with pytest.raises(ProjectError, match="active rebase"):
            store.cleanup_terminal_issue(
                project.id,
                "CHILD",
                branch_name=source,
                is_epic=True,
                target_branch=target,
                review_head=source_head,
                require_target_branch=True,
            )
        assert os.path.isdir(worktree)

    def test_missing_nested_evidence_and_unregistered_path_fail_closed(self, tmp_path):
        store, project, worktree, source, target, source_head = self._setup_repo(
            tmp_path
        )
        with pytest.raises(ProjectError, match="target branch evidence"):
            store.cleanup_terminal_issue(
                project.id,
                "CHILD",
                branch_name=source,
                is_epic=True,
                require_target_branch=True,
            )
        assert os.path.isdir(worktree)

        subprocess.run(
            ["git", "worktree", "remove", worktree, "--force"],
            cwd=project.repo_path,
            check=True,
        )
        os.makedirs(worktree)
        with pytest.raises(ProjectError, match="unregistered worktree"):
            store.cleanup_terminal_issue(
                project.id,
                "CHILD",
                branch_name=source,
                is_epic=True,
                target_branch=target,
                review_head=source_head,
                require_target_branch=True,
            )
        assert os.path.isdir(worktree)

    def test_repeated_cleanup_is_quiet_and_idempotent(self, tmp_path):
        store, project, worktree, source, target, source_head = self._setup_repo(
            tmp_path
        )
        first = store.cleanup_terminal_issue(
            project.id,
            "CHILD",
            branch_name=source,
            is_epic=True,
            target_branch=target,
            review_head=source_head,
            require_target_branch=True,
        )
        second = store.cleanup_terminal_issue(
            project.id,
            "CHILD",
            branch_name=source,
            is_epic=True,
            target_branch=target,
            review_head=source_head,
            require_target_branch=True,
        )
        assert first == (True, None)
        assert second == (False, None)
        assert not os.path.exists(worktree)

    def test_already_pruned_branch_still_retires_recovery_generations(self, tmp_path):
        store, project, worktree, source, target, source_head = self._setup_repo(
            tmp_path
        )
        assert store.cleanup_terminal_issue(
            project.id,
            "CHILD",
            branch_name=source,
            is_epic=True,
            target_branch=target,
            review_head=source_head,
            require_target_branch=True,
        ) == (True, None)
        recovery_ref = _worktree_recovery_ref("CHILD")
        consumed_ref = _worktree_consumed_recovery_ref("CHILD", source_head)
        for ref in (recovery_ref, consumed_ref):
            subprocess.run(
                ["git", "update-ref", ref, source_head],
                cwd=project.repo_path,
                check=True,
            )

        # The owned branch and worktree are already absent, but terminal
        # cleanup must still retire task-scoped recovery lifecycle evidence.
        assert store.cleanup_terminal_issue(
            project.id,
            "CHILD",
            branch_name=source,
            is_epic=True,
            target_branch=target,
            review_head=source_head,
            require_target_branch=True,
        ) == (False, None)
        for ref in (recovery_ref, consumed_ref):
            assert subprocess.run(
                ["git", "show-ref", "--verify", "--quiet", ref],
                cwd=project.repo_path,
                check=False,
            ).returncode == 1

        assert store.cleanup_terminal_issue(
            project.id,
            "CHILD",
            branch_name=source,
            is_epic=True,
            target_branch=target,
            review_head=source_head,
            require_target_branch=True,
        ) == (False, None)

class TestProjectStoreFindByName:
    """Tests for the secondary name-based project lookup."""

    def _make_store_with_projects(self, tmp_path):
        store = _store(tmp_path)
        p1 = Project(
            id="proj-aaa",
            name="coroot",
            repo_url="https://example.com/coroot.git",
            repo_path=str(tmp_path / "coroot"),
        )
        p2 = Project(
            id="proj-bbb",
            name="trickle",
            repo_url="https://example.com/trickle.git",
            repo_path=str(tmp_path / "trickle"),
        )
        store._projects[p1.id] = p1
        store._projects[p2.id] = p2
        return store, p1, p2

    def test_find_by_name_returns_matching_project(self, tmp_path):
        """find_by_name returns the project whose name matches."""
        store, p1, p2 = self._make_store_with_projects(tmp_path)
        result = store.find_by_name("coroot")
        assert result is p1

    def test_find_by_name_returns_second_project(self, tmp_path):
        """find_by_name can return any project, not just the first."""
        store, p1, p2 = self._make_store_with_projects(tmp_path)
        result = store.find_by_name("trickle")
        assert result is p2

    def test_find_by_name_returns_none_for_unknown_name(self, tmp_path):
        """find_by_name returns None when no project has the given name."""
        store, _, _ = self._make_store_with_projects(tmp_path)
        result = store.find_by_name("nonexistent")
        assert result is None

    def test_find_by_name_does_not_match_project_id(self, tmp_path):
        """find_by_name matches names only, not internal IDs."""
        store, _, _ = self._make_store_with_projects(tmp_path)
        result = store.find_by_name("proj-aaa")
        assert result is None

    def test_find_by_name_empty_store(self, tmp_path):
        """find_by_name returns None on an empty store."""
        store = _store(tmp_path)
        result = store.find_by_name("coroot")
        assert result is None

    def test_get_still_works_by_id(self, tmp_path):
        """get() still returns a project by its internal ID after adding find_by_name."""
        store, p1, _ = self._make_store_with_projects(tmp_path)
        result = store.get("proj-aaa")
        assert result is p1

    def test_get_does_not_fall_back_to_name(self, tmp_path):
        """get() does NOT look up by name — use find_by_name for that."""
        store, _, _ = self._make_store_with_projects(tmp_path)
        result = store.get("coroot")  # 'coroot' is a name, not an id
        assert result is None
