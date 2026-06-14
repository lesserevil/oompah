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
    _is_github_backed,
    _is_ref_namespace_conflict_error,
    _is_transient_git_config_lock_error,
    _is_worktree_branch_already_used_error,
    _repo_name_from_url,
    _resolve_ref_namespace_conflict,
    _sanitize_identifier,
    github_work_branch_name,
)
from oompah.statuses import CANONICAL_STATUSES


def _make_repo(tmp_path, *, backlog: bool = True):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    if backlog:
        _write_backlog_config(repo)
    return repo


def _write_backlog_config(repo, *, legacy: bool = False):
    backlog_dir = repo / "backlog"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    if legacy:
        content = "\n".join([
            "project_name: Legacy",
            "default_status: To Do",
            "task_prefix: TASK",
            "statuses:",
            "  - To Do",
            "  - In Progress",
            "  - Done",
            "",
        ])
    else:
        content = "\n".join([
            "project_name: Test",
            "default_status: Backlog",
            "task_prefix: TASK",
            f"statuses: [{', '.join(CANONICAL_STATUSES)}]",
            "",
        ])
    (backlog_dir / "config.yml").write_text(content, encoding="utf-8")


def _store(tmp_path) -> ProjectStore:
    return ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "wt"),
    )


def _store_with_one_project(tmp_path, *, backlog: bool = True, legacy: bool = False):
    repo = _make_repo(tmp_path, backlog=backlog)
    if backlog and legacy:
        _write_backlog_config(repo, legacy=True)
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


class TestSanitizeIdentifier:
    def test_clean(self):
        assert _sanitize_identifier("task-001") == "task-001"

    def test_special_chars(self):
        assert _sanitize_identifier("foo/bar baz") == "foo_bar_baz"

    def test_preserves_dots(self):
        assert _sanitize_identifier("v1.2.3") == "v1.2.3"


class TestBootstrapLFS:
    def test_success_path_writes_gitattributes(self, tmp_path):
        repo = _make_repo(tmp_path, backlog=False)

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "lfs", "install"]:
                return subprocess.CompletedProcess(args, 0, "", "")
            raise AssertionError(f"unexpected command: {args}")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            ok = _bootstrap_lfs(str(repo))

        assert ok is True
        assert (repo / ".oompah" / "attachments" / ".gitattributes").is_file()

    def test_idempotent(self, tmp_path):
        repo = _make_repo(tmp_path, backlog=False)

        with patch("oompah.projects.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0, "", "")
            assert _bootstrap_lfs(str(repo)) is True
            first = (repo / ".oompah" / "attachments" / ".gitattributes").read_text()
            assert _bootstrap_lfs(str(repo)) is True
            second = (repo / ".oompah" / "attachments" / ".gitattributes").read_text()

        assert first == second

    def test_no_lfs_installed_returns_false(self, tmp_path):
        repo = _make_repo(tmp_path, backlog=False)

        with patch("oompah.projects.subprocess.run", side_effect=FileNotFoundError):
            assert _bootstrap_lfs(str(repo)) is False

    def test_lfs_install_failure_returns_false(self, tmp_path):
        repo = _make_repo(tmp_path, backlog=False)

        with patch("oompah.projects.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, ["git", "lfs"])
            assert _bootstrap_lfs(str(repo)) is False


class TestCreateProjectBacklogRequirement:
    def test_existing_clone_without_backlog_config_raises(self, tmp_path):
        store = _store(tmp_path)
        repo_path = tmp_path / "repos" / "repo"
        repo_path.mkdir(parents=True)
        (repo_path / ".git").mkdir()

        with patch("oompah.projects.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            with pytest.raises(ProjectError, match="No Backlog.md project"):
                store.create(
                    str(repo_path),
                    name="repo",
                    git_user_name="Test",
                    git_user_email="t@example.com",
                )

    def test_github_backed_create_skips_backlog_compat_check(self, tmp_path):
        store = _store(tmp_path)
        repo_path = tmp_path / "repos" / "repo"
        repo_path.mkdir(parents=True)
        (repo_path / ".git").mkdir()

        with patch("oompah.projects.ensure_backlog_compatible") as mock_compat:
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

        mock_compat.assert_not_called()
        assert project.tracker_kind == "github_issues"
        assert project.tracker_owner == "example-org"
        assert project.tracker_repo == "oompah"
        assert project.paused is True


class TestSyncProjectSources:
    # The git-health portion of sync_project_sources is now delegated to
    # backlog_conflict.ensure_repo_sound(); these tests patch that seam.
    _SOUND = {"sound": True, "actions": ["ff-pull"], "unrecoverable": [], "reset": False}

    def test_runs_git_and_backlog_compatibility_when_present(self, tmp_path):
        store, repo = _store_with_one_project(tmp_path)
        with patch(
            "oompah.backlog_conflict.ensure_repo_sound", return_value=dict(self._SOUND)
        ) as heal:
            status = store.sync_project_sources("proj-sync1")

        assert status["git"] == "ok"
        assert status["backlog"] == "ok"
        assert status["conflicts"] == "none"
        heal.assert_called_once()
        # called with (repo_path, default_branch)
        assert heal.call_args.args[0] == str(repo)
        assert heal.call_args.args[1] == "main"

    def test_reset_recovery_is_reported_in_git_status(self, tmp_path):
        store, _repo = _store_with_one_project(tmp_path)
        healed = {"sound": True, "actions": ["hard-reset"], "unrecoverable": [], "reset": True}
        with patch("oompah.backlog_conflict.ensure_repo_sound", return_value=healed):
            status = store.sync_project_sources("proj-sync1")
        assert status["git"] == "reset:ok"
        assert status.get("heal") == "hard-reset"

    def test_legacy_backlog_config_is_migrated(self, tmp_path):
        store, repo = _store_with_one_project(tmp_path, legacy=True)

        with patch(
            "oompah.backlog_conflict.ensure_repo_sound", return_value=dict(self._SOUND)
        ):
            status = store.sync_project_sources("proj-sync1")

        assert status["git"] == "ok"
        assert status["backlog"] == "migrated"
        assert status["conflicts"] == "none"
        config = (repo / "backlog" / "config.yml").read_text(encoding="utf-8")
        assert "default_status: Backlog" in config
        assert "Open" in config

    def test_unhealable_checkout_does_not_block_backlog_check(self, tmp_path):
        store, _repo = _store_with_one_project(tmp_path)
        unsound = {"sound": False, "actions": [], "unrecoverable": [], "reset": False}
        with patch("oompah.backlog_conflict.ensure_repo_sound", return_value=unsound):
            status = store.sync_project_sources("proj-sync1")

        assert status["git"].startswith("failed")
        assert status["backlog"] == "ok"

    def test_missing_backlog_config_is_reported(self, tmp_path):
        store, _repo = _store_with_one_project(tmp_path, backlog=False)

        with patch(
            "oompah.backlog_conflict.ensure_repo_sound", return_value=dict(self._SOUND)
        ):
            status = store.sync_project_sources("proj-sync1")

        assert status["git"] == "ok"
        assert status["backlog"].startswith("failed: No Backlog.md project")

    def test_unknown_project_returns_skipped(self, tmp_path):
        store, _repo = _store_with_one_project(tmp_path)

        status = store.sync_project_sources("proj-nope")

        assert status["git"].startswith("skipped")
        assert status["backlog"].startswith("skipped")


def _store_with_github_project(tmp_path):
    """Return (store, repo_path) for a GitHub-backed project (no Backlog config)."""
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

    def test_backlog_tracker_kind_is_not_github_backed(self):
        p = Project(
            id="x", name="x", repo_url="x", repo_path="/x",
            branch="main", default_branch="main", tracker_kind="backlog",
        )
        assert _is_github_backed(p) is False


class TestSyncProjectSourcesGitHubBacked:
    """sync_project_sources for GitHub-backed projects skips Backlog-specific steps."""

    _SOUND = {"sound": True, "actions": [], "unrecoverable": [], "reset": False}

    def test_github_backed_reports_tracker_key(self, tmp_path):
        store, _repo = _store_with_github_project(tmp_path)
        with patch(
            "oompah.backlog_conflict.ensure_repo_sound", return_value=dict(self._SOUND)
        ):
            status = store.sync_project_sources("proj-gh1")

        assert status["tracker"] == "github_issues"

    def test_github_backed_git_self_heal_runs(self, tmp_path):
        store, _repo = _store_with_github_project(tmp_path)
        with patch(
            "oompah.backlog_conflict.ensure_repo_sound", return_value=dict(self._SOUND)
        ) as heal:
            status = store.sync_project_sources("proj-gh1")

        heal.assert_called_once()
        assert status["git"] == "ok"

    def test_github_backed_skips_backlog_compat_check(self, tmp_path):
        store, _repo = _store_with_github_project(tmp_path)
        with patch(
            "oompah.backlog_conflict.ensure_repo_sound", return_value=dict(self._SOUND)
        ):
            with patch("oompah.projects.ensure_backlog_compatible") as mock_compat:
                status = store.sync_project_sources("proj-gh1")

        mock_compat.assert_not_called()
        assert status["backlog"] == "skipped: github_issues"

    def test_github_backed_skips_conflict_repair(self, tmp_path):
        store, _repo = _store_with_github_project(tmp_path)
        with patch(
            "oompah.backlog_conflict.ensure_repo_sound", return_value=dict(self._SOUND)
        ):
            with patch(
                "oompah.backlog_conflict.repair_repo_backlog_conflicts"
            ) as mock_repair:
                status = store.sync_project_sources("proj-gh1")

        mock_repair.assert_not_called()
        assert status["conflicts"] == "skipped: github_issues"

    def test_github_backed_does_not_quarantine_on_unmerged_files(self, tmp_path):
        """Unmerged files in a GitHub-backed project must NOT trigger quarantine."""
        store, _repo = _store_with_github_project(tmp_path)
        unsound = {
            "sound": False,
            "actions": [],
            "unrecoverable": ["backlog/tasks/task-1.md"],
            "reset": False,
        }
        with patch("oompah.backlog_conflict.ensure_repo_sound", return_value=unsound):
            status = store.sync_project_sources("proj-gh1")

        # Git healing may fail, but no quarantine should happen
        assert status["git"].startswith("failed")
        # Backlog/conflicts are still skipped, not quarantined
        assert status["backlog"] == "skipped: github_issues"
        assert status["conflicts"] == "skipped: github_issues"
        # Project must NOT be paused
        project = store._projects["proj-gh1"]
        assert not project.paused

    def test_github_backed_reset_recovery_reported(self, tmp_path):
        store, _repo = _store_with_github_project(tmp_path)
        healed = {"sound": True, "actions": ["hard-reset"], "unrecoverable": [], "reset": True}
        with patch("oompah.backlog_conflict.ensure_repo_sound", return_value=healed):
            status = store.sync_project_sources("proj-gh1")

        assert status["git"] == "reset:ok"
        assert status.get("heal") == "hard-reset"
        assert status["tracker"] == "github_issues"

    def test_github_backed_no_git_dir_skips_heal(self, tmp_path):
        store, repo = _store_with_github_project(tmp_path)
        # Remove the .git dir to simulate a missing checkout
        (repo / ".git").rmdir()
        with patch(
            "oompah.backlog_conflict.ensure_repo_sound"
        ) as mock_heal:
            status = store.sync_project_sources("proj-gh1")

        mock_heal.assert_not_called()
        assert status["git"] == "skipped: no .git"
        assert status["backlog"] == "skipped: github_issues"
        assert status["conflicts"] == "skipped: github_issues"
        assert status["tracker"] == "github_issues"


class TestSyncAllSources:
    def test_empty_store_returns_empty_dict(self, tmp_path):
        assert _store(tmp_path).sync_all_sources() == {}

    def test_runs_for_every_project(self, tmp_path):
        store = _store(tmp_path)
        for i in range(3):
            repo = tmp_path / f"repo{i}"
            repo.mkdir()
            (repo / ".git").mkdir()
            _write_backlog_config(repo)
            store._projects[f"p-{i}"] = Project(
                id=f"p-{i}",
                name=f"r{i}",
                repo_url="x",
                repo_path=str(repo),
                branch="main",
                default_branch="main",
            )

        with patch(
            "oompah.backlog_conflict.ensure_repo_sound",
            return_value={"sound": True, "actions": [], "unrecoverable": [], "reset": False},
        ):
            results = store.sync_all_sources()

        assert set(results) == {"p-0", "p-1", "p-2"}
        assert all(
            st.get("git") == "ok" and st.get("backlog") == "ok" and st.get("conflicts") == "none"
            for st in results.values()
        )


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


class TestSyncTaskFileToWorktree:
    def test_copies_current_task_file_and_removes_stale_copy(self, tmp_path):
        store, repo = _store_with_one_project(tmp_path)
        source_dir = repo / "backlog" / "tasks"
        source_dir.mkdir(parents=True, exist_ok=True)
        source = source_dir / "task-389 - current.md"
        source.write_text(
            "\n".join([
                "---",
                "id: TASK-389",
                "status: In Progress",
                "title: Current",
                "---",
                "",
                "Current task body",
                "",
            ]),
            encoding="utf-8",
        )
        wt_path = tmp_path / "wt-task"
        stale_dir = wt_path / "backlog" / "completed"
        stale_dir.mkdir(parents=True)
        stale = stale_dir / "task-389 - stale.md"
        stale.write_text(
            "\n".join([
                "---",
                "id: TASK-389",
                "status: Done",
                "title: Stale",
                "---",
                "",
                "Stale task body",
                "",
            ]),
            encoding="utf-8",
        )

        assert store.sync_task_file_to_worktree(
            "proj-sync1",
            "TASK-389",
            str(wt_path),
        )

        copied = wt_path / "backlog" / "tasks" / source.name
        assert copied.exists()
        assert "status: In Progress" in copied.read_text(encoding="utf-8")
        assert not stale.exists()

    def test_returns_false_when_source_task_file_is_missing(self, tmp_path):
        store, _repo = _store_with_one_project(tmp_path)
        wt_path = tmp_path / "wt-task"
        wt_path.mkdir()

        assert store.sync_task_file_to_worktree(
            "proj-sync1",
            "TASK-999",
            str(wt_path),
        ) is False

    def _setup_status_divergence(self, tmp_path, *, src_status, wt_status):
        """Source (main) has src_status; worktree copy has wt_status."""
        store, repo = _store_with_one_project(tmp_path)
        sdir = repo / "backlog" / "tasks"
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / "task-389 - t.md").write_text(
            f"---\nid: TASK-389\nstatus: {src_status}\ntitle: T\n---\n\nbody\n",
            encoding="utf-8",
        )
        wt_path = tmp_path / "wt-task"
        wdir = wt_path / "backlog" / "tasks"
        wdir.mkdir(parents=True)
        (wdir / "task-389 - t.md").write_text(
            f"---\nid: TASK-389\nstatus: {wt_status}\ntitle: T\n---\n\nbody\n",
            encoding="utf-8",
        )
        return store, wt_path

    def test_preserves_terminal_worktree_status_over_stale_source(self, tmp_path):
        """When the worktree records a terminal status (Done) and the
        source is behind (Open), the sync must NOT regress it."""
        store, wt_path = self._setup_status_divergence(
            tmp_path, src_status="Open", wt_status="Done"
        )
        assert store.sync_task_file_to_worktree(
            "proj-sync1", "TASK-389", str(wt_path),
            preserve_statuses=frozenset({"Done", "Merged", "Archived"}),
        )
        copied = (wt_path / "backlog" / "tasks" / "task-389 - t.md").read_text()
        assert "status: Done" in copied
        # The non-status content still came from source.
        assert "body" in copied

    def test_no_preservation_without_preserve_statuses(self, tmp_path):
        """Default behavior is unchanged: without preserve_statuses the
        source status overwrites the worktree copy."""
        store, wt_path = self._setup_status_divergence(
            tmp_path, src_status="Open", wt_status="Done"
        )
        assert store.sync_task_file_to_worktree(
            "proj-sync1", "TASK-389", str(wt_path),
        )
        copied = (wt_path / "backlog" / "tasks" / "task-389 - t.md").read_text()
        assert "status: Open" in copied

    def test_non_terminal_worktree_status_not_preserved(self, tmp_path):
        """A worktree status that isn't in the preserve set (e.g. In
        Progress) is overwritten by the source as usual."""
        store, wt_path = self._setup_status_divergence(
            tmp_path, src_status="Open", wt_status="In Progress"
        )
        assert store.sync_task_file_to_worktree(
            "proj-sync1", "TASK-389", str(wt_path),
            preserve_statuses=frozenset({"Done", "Merged", "Archived"}),
        )
        copied = (wt_path / "backlog" / "tasks" / "task-389 - t.md").read_text()
        assert "status: Open" in copied


class TestReadTaskStatusInEpicWorktree:
    def _make_epic_worktree(self, store, tmp_path, *, status):
        wt = store.epic_worktree_path_for("proj-sync1", "TASK-706")
        tdir = os.path.join(wt, "backlog", "tasks")
        os.makedirs(tdir, exist_ok=True)
        with open(os.path.join(tdir, "task-706.4 - x.md"), "w", encoding="utf-8") as f:
            f.write(f"---\nid: TASK-706.4\nstatus: {status}\ntitle: X\n---\n\nbody\n")
        return wt

    def test_reads_status_from_epic_worktree(self, tmp_path):
        store, _repo = _store_with_one_project(tmp_path)
        self._make_epic_worktree(store, tmp_path, status="Done")
        assert store.read_task_status_in_epic_worktree(
            "proj-sync1", "TASK-706", "TASK-706.4"
        ) == "Done"

    def test_none_when_worktree_absent(self, tmp_path):
        store, _repo = _store_with_one_project(tmp_path)
        assert store.read_task_status_in_epic_worktree(
            "proj-sync1", "TASK-706", "TASK-706.4"
        ) is None

    def test_none_when_task_file_absent(self, tmp_path):
        store, _repo = _store_with_one_project(tmp_path)
        self._make_epic_worktree(store, tmp_path, status="Done")
        assert store.read_task_status_in_epic_worktree(
            "proj-sync1", "TASK-706", "TASK-999"
        ) is None


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
