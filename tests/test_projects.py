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
    _is_ref_namespace_conflict_error,
    _is_transient_git_config_lock_error,
    _is_worktree_branch_already_used_error,
    _repo_name_from_url,
    _resolve_ref_namespace_conflict,
    _sanitize_identifier,
)


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
            "statuses: [Backlog, Open, In Progress, Needs Answer, Needs Human, Needs CI Fix, Needs Rebase, In Review, Decomposed, Duplicate Candidate, Done, Merged, Archived]",
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


class TestSyncProjectSources:
    def test_runs_git_and_backlog_compatibility_when_present(self, tmp_path):
        store, _repo = _store_with_one_project(tmp_path)
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            status = store.sync_project_sources("proj-sync1")

        assert status["git"] == "ok"
        assert status["backlog"] == "ok"
        assert status["conflicts"] == "none"
        assert ["git", "fetch", "origin"] in calls
        assert any(args[:2] == ["git", "pull"] for args in calls)
        assert all(args[0] != "bd" for args in calls)

    def test_default_timeout_is_forwarded_to_git_pull(self, tmp_path):
        store, _repo = _store_with_one_project(tmp_path)
        calls = []

        def fake_run(args, **kwargs):
            calls.append((args, kwargs))
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            store.sync_project_sources("proj-sync1")

        pull_calls = [
            kwargs for args, kwargs in calls
            if args[:2] == ["git", "pull"]
        ]
        assert pull_calls
        assert pull_calls[0]["timeout"] == DEFAULT_SOURCE_SYNC_TIMEOUT_S

    def test_legacy_backlog_config_is_migrated(self, tmp_path):
        store, repo = _store_with_one_project(tmp_path, legacy=True)

        with patch("oompah.projects.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            status = store.sync_project_sources("proj-sync1")

        assert status["git"] == "ok"
        assert status["backlog"] == "migrated"
        assert status["conflicts"] == "none"
        config = (repo / "backlog" / "config.yml").read_text(encoding="utf-8")
        assert "default_status: Backlog" in config
        assert "Open" in config

    def test_git_pull_failure_does_not_block_backlog_check(self, tmp_path):
        store, _repo = _store_with_one_project(tmp_path)

        def fake_run(args, **kwargs):
            if args[:2] == ["git", "pull"]:
                return MagicMock(returncode=1, stdout="", stderr="non-fast-forward")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            status = store.sync_project_sources("proj-sync1")

        assert status["git"].startswith("failed: non-fast-forward")
        assert status["backlog"] == "ok"

    def test_missing_backlog_config_is_reported(self, tmp_path):
        store, _repo = _store_with_one_project(tmp_path, backlog=False)

        with patch("oompah.projects.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            status = store.sync_project_sources("proj-sync1")

        assert status["git"] == "ok"
        assert status["backlog"].startswith("failed: No Backlog.md project")

    def test_unknown_project_returns_skipped(self, tmp_path):
        store, _repo = _store_with_one_project(tmp_path)

        status = store.sync_project_sources("proj-nope")

        assert status["git"].startswith("skipped")
        assert status["backlog"].startswith("skipped")


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

        with patch("oompah.projects.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
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
