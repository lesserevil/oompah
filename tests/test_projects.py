"""Tests for project storage and git worktree helpers."""

from __future__ import annotations

import os
import subprocess
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
            store.remove_worktree(project.id, "TASK-1")

        assert calls == [["git", "worktree", "prune"]]

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


# ---------------------------------------------------------------------------
# ProjectStore.find_by_name
# ---------------------------------------------------------------------------

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
