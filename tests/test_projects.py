"""Tests for oompah.projects (unit-testable parts)."""

from oompah.projects import _repo_name_from_url, _sanitize_identifier


class TestRepoNameFromUrl:
    def test_https_with_git(self):
        assert _repo_name_from_url("https://github.com/org/repo.git") == "repo"

    def test_https_without_git(self):
        assert _repo_name_from_url("https://github.com/org/repo") == "repo"

    def test_ssh(self):
        assert _repo_name_from_url("git@github.com:org/repo.git") == "repo"

    def test_trailing_slash(self):
        assert _repo_name_from_url("https://github.com/org/repo/") == "repo"

    def test_local_path(self):
        assert _repo_name_from_url("/home/user/projects/myrepo") == "myrepo"

    def test_empty_returns_unnamed(self):
        assert _repo_name_from_url("") == "unnamed"


class TestSanitizeIdentifier:
    def test_clean(self):
        assert _sanitize_identifier("beads-001") == "beads-001"

    def test_special_chars(self):
        assert _sanitize_identifier("foo/bar baz") == "foo_bar_baz"

    def test_preserves_dots(self):
        assert _sanitize_identifier("v1.2.3") == "v1.2.3"


# ---------------------------------------------------------------------------
# LFS bootstrap on project registration (oompah-a9c.2)
# ---------------------------------------------------------------------------

import os
import subprocess
from unittest.mock import patch

import pytest

from oompah.projects import _bootstrap_lfs, _configure_beads_jsonl_ignore


def _make_repo(tmp_path) -> str:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    return str(repo)


class TestBootstrapLFS:
    def test_success_path_writes_gitattributes(self, tmp_path):
        repo = _make_repo(tmp_path)
        # Mock subprocess.run only for the `git lfs install` call.
        real_run = subprocess.run

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "lfs", "install"]:
                return subprocess.CompletedProcess(args, 0, "", "")
            return real_run(args, **kwargs)

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            ok = _bootstrap_lfs(repo)
        assert ok is True
        ga = os.path.join(repo, ".oompah", "attachments", ".gitattributes")
        assert os.path.isfile(ga)

    def test_idempotent(self, tmp_path):
        repo = _make_repo(tmp_path)
        real_run = subprocess.run

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "lfs", "install"]:
                return subprocess.CompletedProcess(args, 0, "", "")
            return real_run(args, **kwargs)

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            assert _bootstrap_lfs(repo) is True
            # Second call must also succeed; .gitattributes content is stable.
            assert _bootstrap_lfs(repo) is True

    def test_no_lfs_installed_returns_false(self, tmp_path):
        repo = _make_repo(tmp_path)

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "lfs", "install"]:
                raise FileNotFoundError("git-lfs not on PATH")
            return subprocess.run(args, **kwargs)

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            ok = _bootstrap_lfs(repo)
        assert ok is False
        # .gitattributes is NOT written when LFS is unavailable.
        assert not os.path.exists(
            os.path.join(repo, ".oompah", "attachments", ".gitattributes")
        )

    def test_lfs_install_failure_returns_false(self, tmp_path):
        repo = _make_repo(tmp_path)

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "lfs", "install"]:
                raise subprocess.CalledProcessError(
                    1, args, output="", stderr="some failure",
                )
            return subprocess.run(args, **kwargs)

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            assert _bootstrap_lfs(repo) is False


class TestConfigureBeadsJsonlIgnore:
    """Tests for ``_configure_beads_jsonl_ignore`` (oompah-zlz_2-mp4v).

    Verifies that the helper:
    1. Adds ``.beads/*.jsonl`` to ``.gitignore`` (idempotent).
    2. Untracks any currently-tracked ``.beads/*.jsonl`` via ``git rm --cached``.
    3. Sets ``bd config set export.git-add false``.
    """

    def _make_repo_with_beads(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
        beads = repo / ".beads"
        beads.mkdir()
        return repo

    def test_returns_false_for_nonexistent_path(self, tmp_path):
        result = _configure_beads_jsonl_ignore(str(tmp_path / "does-not-exist"))
        assert result is False

    def test_adds_gitignore_block_when_absent(self, tmp_path):
        repo = self._make_repo_with_beads(tmp_path)
        (repo / ".gitignore").write_text("*.log\n")

        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            assert _configure_beads_jsonl_ignore(str(repo)) is True

        gi = (repo / ".gitignore").read_text()
        assert ".beads/*.jsonl" in gi
        assert "*.log" in gi  # original content preserved
        assert "oompah-zlz_2-mp4v" in gi  # bears the explanatory comment

    def test_creates_gitignore_when_missing(self, tmp_path):
        repo = self._make_repo_with_beads(tmp_path)
        # No .gitignore at all
        assert not (repo / ".gitignore").exists()

        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            assert _configure_beads_jsonl_ignore(str(repo)) is True

        gi = (repo / ".gitignore").read_text()
        assert ".beads/*.jsonl" in gi

    def test_idempotent_on_repeated_calls(self, tmp_path):
        repo = self._make_repo_with_beads(tmp_path)
        (repo / ".gitignore").write_text("# starter\n")

        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            assert _configure_beads_jsonl_ignore(str(repo)) is True
            first = (repo / ".gitignore").read_text()
            assert _configure_beads_jsonl_ignore(str(repo)) is True
            second = (repo / ".gitignore").read_text()

        # File content unchanged on second call.
        assert first == second
        # Exactly one occurrence of the .beads/*.jsonl pattern.
        assert first.count(".beads/*.jsonl") == 1

    def test_skips_when_pattern_present_without_marker(self, tmp_path):
        """Operator-added .beads/*.jsonl entry is respected; we don't duplicate."""
        repo = self._make_repo_with_beads(tmp_path)
        (repo / ".gitignore").write_text(
            "# Operator's own ignore\n.beads/*.jsonl\n*.bak\n"
        )

        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            assert _configure_beads_jsonl_ignore(str(repo)) is True

        gi = (repo / ".gitignore").read_text()
        # Single occurrence — no duplicate appended.
        assert gi.count(".beads/*.jsonl") == 1
        # Operator's other entries preserved.
        assert "*.bak" in gi

    def test_untracks_tracked_jsonl_files(self, tmp_path):
        repo = self._make_repo_with_beads(tmp_path)

        # Pretend issues.jsonl and interactions.jsonl are tracked.
        ls_files_output = ".beads/issues.jsonl\n.beads/interactions.jsonl\n"
        rm_call = []

        def fake_run(args, **kwargs):
            if args[:2] == ["git", "ls-files"]:
                return subprocess.CompletedProcess(
                    args, 0, ls_files_output, "",
                )
            if args[:3] == ["git", "rm", "--cached"]:
                rm_call.append(args)
                return subprocess.CompletedProcess(args, 0, "", "")
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            _configure_beads_jsonl_ignore(str(repo))

        assert len(rm_call) == 1
        # Both jsonl files should be in the rm call.
        rm_paths = rm_call[0]
        assert ".beads/issues.jsonl" in rm_paths
        assert ".beads/interactions.jsonl" in rm_paths

    def test_does_not_untrack_backup_subdirectory_files(self, tmp_path):
        """``.beads/*.jsonl`` should only match top-level, not ``.beads/backup/*.jsonl``."""
        repo = self._make_repo_with_beads(tmp_path)

        # git ls-files may return recursive matches even when given a
        # top-level glob; the helper must filter those out.
        ls_files_output = (
            ".beads/issues.jsonl\n"
            ".beads/backup/comments.jsonl\n"
            ".beads/backup/issues.jsonl\n"
        )
        rm_call = []

        def fake_run(args, **kwargs):
            if args[:2] == ["git", "ls-files"]:
                return subprocess.CompletedProcess(
                    args, 0, ls_files_output, "",
                )
            if args[:3] == ["git", "rm", "--cached"]:
                rm_call.append(args)
                return subprocess.CompletedProcess(args, 0, "", "")
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            _configure_beads_jsonl_ignore(str(repo))

        assert len(rm_call) == 1
        rm_paths = rm_call[0]
        assert ".beads/issues.jsonl" in rm_paths
        # Backup subdirectory entries must NOT be passed to git rm.
        assert ".beads/backup/comments.jsonl" not in rm_paths
        assert ".beads/backup/issues.jsonl" not in rm_paths

    def test_no_rm_call_when_nothing_tracked(self, tmp_path):
        repo = self._make_repo_with_beads(tmp_path)

        rm_call = []

        def fake_run(args, **kwargs):
            if args[:2] == ["git", "ls-files"]:
                # Empty output → nothing tracked.
                return subprocess.CompletedProcess(args, 0, "", "")
            if args[:3] == ["git", "rm", "--cached"]:
                rm_call.append(args)
                return subprocess.CompletedProcess(args, 0, "", "")
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            _configure_beads_jsonl_ignore(str(repo))

        # Nothing to untrack → no rm call at all.
        assert rm_call == []

    def test_calls_bd_config_set_export_git_add_false(self, tmp_path):
        repo = self._make_repo_with_beads(tmp_path)

        bd_calls = []

        def fake_run(args, **kwargs):
            if args[0] == "bd":
                bd_calls.append(args)
                return subprocess.CompletedProcess(args, 0, "", "")
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            _configure_beads_jsonl_ignore(str(repo))

        # Exactly one bd config set call.
        assert len(bd_calls) == 1
        assert bd_calls[0] == [
            "bd", "config", "set", "export.git-add", "false",
        ]

    def test_resilient_to_bd_command_missing(self, tmp_path):
        """If bd isn't on PATH, the helper logs but returns True."""
        repo = self._make_repo_with_beads(tmp_path)

        def fake_run(args, **kwargs):
            if args[0] == "bd":
                raise FileNotFoundError("bd not on PATH")
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            # Other sub-steps still succeed; overall function returns True.
            assert _configure_beads_jsonl_ignore(str(repo)) is True

    def test_resilient_to_git_rm_failure(self, tmp_path):
        repo = self._make_repo_with_beads(tmp_path)

        def fake_run(args, **kwargs):
            if args[:2] == ["git", "ls-files"]:
                return subprocess.CompletedProcess(
                    args, 0, ".beads/issues.jsonl\n", "",
                )
            if args[:3] == ["git", "rm", "--cached"]:
                raise subprocess.CalledProcessError(
                    1, args, output="", stderr="not in index",
                )
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            # Failure is logged, not raised.  Overall result still True.
            assert _configure_beads_jsonl_ignore(str(repo)) is True

    def test_resilient_to_gitignore_oserror(self, tmp_path):
        """If we can't read or write .gitignore, log but continue."""
        repo = self._make_repo_with_beads(tmp_path)

        def fake_open(*args, **kwargs):
            raise OSError("permission denied")

        # Patch builtin open used by the helper.  We still need
        # subprocess.run to succeed.
        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch("oompah.projects.open", side_effect=fake_open, create=True), \
             patch("oompah.projects.subprocess.run", side_effect=fake_run):
            assert _configure_beads_jsonl_ignore(str(repo)) is True


class TestConfigureBeadsJsonlIgnoreCreate:
    """``ProjectStore.create()`` must call ``_configure_beads_jsonl_ignore``."""

    def test_create_calls_configure_helper(self, tmp_path):
        from oompah.projects import ProjectStore
        from unittest.mock import MagicMock

        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )

        def fake_run(args, **kwargs):
            # Simulate git clone by making the repo dir appear with .beads/.
            if args[:2] == ["git", "clone"]:
                target = args[-1]
                os.makedirs(os.path.join(target, ".git"), exist_ok=True)
                os.makedirs(os.path.join(target, ".beads"), exist_ok=True)
                return MagicMock(returncode=0, stdout="", stderr="")
            if args == ["git", "config", "--global", "user.name"]:
                return MagicMock(returncode=0, stdout="Test User\n", stderr="")
            if args == ["git", "config", "--global", "user.email"]:
                return MagicMock(returncode=0, stdout="test@example.com\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run), \
             patch("oompah.projects._bootstrap_lfs", return_value=False), \
             patch("oompah.projects._install_beads_merge_driver", return_value=True), \
             patch(
                 "oompah.projects._configure_beads_jsonl_ignore",
                 return_value=True,
             ) as mock_cfg:
            store.create(
                repo_url="https://example.com/repo.git",
                name="testrepo",
                branch="main",
            )

        assert mock_cfg.call_count == 1, (
            "Expected ProjectStore.create() to call "
            "_configure_beads_jsonl_ignore exactly once"
        )


class TestConfigureBeadsJsonlIgnoreSync:
    """``sync_project_sources`` must self-heal existing projects."""

    def test_sync_calls_configure_helper(self, tmp_path):
        store = _store_with_one_project(tmp_path)

        def fake_run(args, **kwargs):
            return _MM(returncode=0, stdout="", stderr="")

        with _patch.object(_subprocess, "run", side_effect=fake_run), \
             _patch(
                 "oompah.projects._configure_beads_jsonl_ignore",
                 return_value=True,
             ) as mock_cfg:
            store.sync_project_sources("proj-sync1")

        assert mock_cfg.call_count == 1, (
            "Expected sync_project_sources to invoke "
            "_configure_beads_jsonl_ignore once"
        )

    def test_sync_does_not_raise_when_configure_helper_errors(self, tmp_path):
        store = _store_with_one_project(tmp_path)

        def fake_run(args, **kwargs):
            return _MM(returncode=0, stdout="", stderr="")

        with _patch.object(_subprocess, "run", side_effect=fake_run), \
             _patch(
                 "oompah.projects._configure_beads_jsonl_ignore",
                 side_effect=RuntimeError("boom"),
             ):
            # Top-level catches any exception from the helper.
            status = store.sync_project_sources("proj-sync1")

        # Should still return a status dict — git and beads runs proceed.
        assert isinstance(status, dict)
        assert status.get("git") == "ok"


class TestProjectLFSAvailableField:
    def test_default_false(self):
        from oompah.models import Project
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x")
        assert p.lfs_available is False

    def test_round_trip(self):
        from oompah.models import Project
        p = Project(id="p", name="n", repo_url="u", repo_path="/tmp/x", lfs_available=True)
        d = p.to_dict()
        assert d["lfs_available"] is True
        p2 = Project.from_dict(d)
        assert p2.lfs_available is True


# ---------------------------------------------------------------------------
# Startup source sync — covers the "use old git code" issue raised against
# the orchestrator: at boot we now run git pull + bd dolt pull on every
# project so dispatch operates on fresh state, not whatever was sitting
# in the local clone or local dolt DB.
# ---------------------------------------------------------------------------

import subprocess as _subprocess

from unittest.mock import patch as _patch, MagicMock as _MM

from oompah.models import Project as _Project
from oompah.projects import ProjectStore as _PS


def _store_with_one_project(tmp_path) -> _PS:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / ".beads").mkdir()
    store = _PS(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "wt"),
    )
    p = _Project(
        id="proj-sync1", name="syncrepo",
        repo_url="https://example.com/x.git",
        repo_path=str(repo), branch="main",
    )
    store._projects[p.id] = p
    return store


class TestSyncProjectSources:
    def test_runs_both_git_and_bd_when_dirs_present(self, tmp_path):
        store = _store_with_one_project(tmp_path)
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            return _MM(returncode=0, stdout="", stderr="")

        with _patch.object(_subprocess, "run", side_effect=fake_run):
            status = store.sync_project_sources("proj-sync1")

        assert status == {"git": "ok", "beads": "ok"}
        # Both `git fetch`+`git pull` and `bd dolt pull` should run.
        cmds = [c[0] if isinstance(c, list) else c for c in calls]
        assert any(c == "git" and "fetch" in calls[i] for i, c in enumerate(cmds))
        assert any(c == "git" and "pull" in calls[i] for i, c in enumerate(cmds))
        assert any(c == "bd" for c in cmds)

    def test_skips_git_when_no_dot_git(self, tmp_path):
        store = _PS(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        repo = tmp_path / "norepo"
        repo.mkdir()
        (repo / ".beads").mkdir()
        # No .git/ in the repo path.
        p = _Project(
            id="p-nogit", name="nogit", repo_url="x", repo_path=str(repo),
        )
        store._projects[p.id] = p

        with _patch.object(_subprocess, "run") as mock_run:
            mock_run.return_value = _MM(returncode=0, stdout="", stderr="")
            status = store.sync_project_sources("p-nogit")

        assert status["git"].startswith("skipped"), status
        # bd dolt pull should still attempt to run.
        assert status["beads"] == "ok"

    def test_skips_beads_when_no_dot_beads(self, tmp_path):
        store = _PS(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        repo = tmp_path / "nobeads"
        repo.mkdir()
        (repo / ".git").mkdir()
        # No .beads/ in the repo path.
        p = _Project(
            id="p-nobd", name="nobd", repo_url="x", repo_path=str(repo),
        )
        store._projects[p.id] = p

        with _patch.object(_subprocess, "run") as mock_run:
            mock_run.return_value = _MM(returncode=0, stdout="", stderr="")
            status = store.sync_project_sources("p-nobd")

        assert status["git"] == "ok"
        assert status["beads"].startswith("skipped"), status

    def test_git_pull_failure_does_not_raise(self, tmp_path):
        store = _store_with_one_project(tmp_path)

        def fake_run(args, **kwargs):
            # First call (fetch) ok; second call (pull) fails.
            if args[:2] == ["git", "pull"]:
                return _MM(returncode=1, stdout="", stderr="non-fast-forward")
            return _MM(returncode=0, stdout="", stderr="")

        with _patch.object(_subprocess, "run", side_effect=fake_run):
            status = store.sync_project_sources("proj-sync1")

        assert status["git"].startswith("failed: non-fast-forward")
        # bd dolt pull still attempted and reported.
        assert status["beads"] == "ok"

    def test_bd_pull_failure_does_not_raise(self, tmp_path):
        store = _store_with_one_project(tmp_path)

        def fake_run(args, **kwargs):
            if args[:1] == ["bd"]:
                return _MM(returncode=1, stdout="", stderr="merge conflict")
            return _MM(returncode=0, stdout="", stderr="")

        with _patch.object(_subprocess, "run", side_effect=fake_run):
            status = store.sync_project_sources("proj-sync1")

        assert status["git"] == "ok"
        assert status["beads"].startswith("failed: merge conflict")

    def test_timeout_does_not_raise(self, tmp_path):
        store = _store_with_one_project(tmp_path)

        def fake_run(args, **kwargs):
            raise _subprocess.TimeoutExpired(cmd=args, timeout=1)

        with _patch.object(_subprocess, "run", side_effect=fake_run):
            status = store.sync_project_sources("proj-sync1", timeout_s=1)

        assert status["git"].startswith("failed:")
        assert status["beads"].startswith("failed:")

    def test_unknown_project_returns_skipped(self, tmp_path):
        store = _store_with_one_project(tmp_path)
        status = store.sync_project_sources("proj-nope")
        assert status["git"].startswith("skipped")
        assert status["beads"].startswith("skipped")


class TestSyncAllSources:
    def test_empty_store_returns_empty_dict(self, tmp_path):
        store = _PS(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        assert store.sync_all_sources() == {}

    def test_runs_for_every_project(self, tmp_path):
        store = _PS(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        for i in range(3):
            repo = tmp_path / f"repo{i}"
            repo.mkdir()
            (repo / ".git").mkdir()
            (repo / ".beads").mkdir()
            p = _Project(
                id=f"p-{i}", name=f"r{i}", repo_url="x", repo_path=str(repo),
            )
            store._projects[p.id] = p

        with _patch.object(_subprocess, "run") as mock_run:
            mock_run.return_value = _MM(returncode=0, stdout="", stderr="")
            results = store.sync_all_sources()

        assert set(results.keys()) == {"p-0", "p-1", "p-2"}
        for pid, st in results.items():
            assert st == {"git": "ok", "beads": "ok"}

    def test_one_failing_project_does_not_break_others(self, tmp_path):
        store = _PS(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        for i in range(2):
            repo = tmp_path / f"repo{i}"
            repo.mkdir()
            (repo / ".git").mkdir()
            (repo / ".beads").mkdir()
            p = _Project(
                id=f"p-{i}", name=f"r{i}", repo_url="x", repo_path=str(repo),
            )
            store._projects[p.id] = p

        # First project's bd pull fails; second project's all succeeds.
        def fake_run(args, **kwargs):
            cwd = kwargs.get("cwd", "")
            if "repo0" in cwd and args[:1] == ["bd"]:
                return _MM(returncode=1, stdout="", stderr="boom")
            return _MM(returncode=0, stdout="", stderr="")

        with _patch.object(_subprocess, "run", side_effect=fake_run):
            results = store.sync_all_sources()

        assert results["p-0"]["beads"].startswith("failed: boom")
        assert results["p-1"]["beads"] == "ok"


# ---------------------------------------------------------------------------
# _strip_worktree_beads_fork — defensive cleanup of per-worktree dolt detritus.
# ---------------------------------------------------------------------------

class TestStripWorktreeBeadsFork:
    def _store(self, tmp_path):
        return _PS(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )

    def test_no_op_when_no_beads_dir(self, tmp_path):
        store = self._store(tmp_path)
        wt = tmp_path / "worktree"
        wt.mkdir()
        # Should not raise — worktree has no .beads/ at all.
        store._strip_worktree_beads_fork(str(wt))

    def test_removes_dolt_dir_and_runtime_files(self, tmp_path):
        store = self._store(tmp_path)
        wt = tmp_path / "worktree"
        wt.mkdir()
        beads = wt / ".beads"
        beads.mkdir()
        # Tracked content stays.
        (beads / "issues.jsonl").write_text("[]")
        (beads / "config.yaml").write_text("# config")
        # Forked-dolt artefacts that should be removed.
        (beads / "dolt").mkdir()
        (beads / "dolt" / "data.bin").write_text("binary")
        (beads / "embeddeddolt").mkdir()
        (beads / "dolt-server.log").write_text("log")
        (beads / "dolt-server.pid").write_text("99999")
        (beads / "dolt-server.port").write_text("3306")
        (beads / "dolt-server.lock").write_text("")

        store._strip_worktree_beads_fork(str(wt))

        # Tracked content preserved.
        assert (beads / "issues.jsonl").exists()
        assert (beads / "config.yaml").exists()
        # All forked-dolt artefacts removed.
        for entry in (
            "dolt", "embeddeddolt", "dolt-server.log",
            "dolt-server.pid", "dolt-server.port", "dolt-server.lock",
        ):
            assert not (beads / entry).exists(), f"{entry} should be gone"

    def test_handles_missing_runtime_files(self, tmp_path):
        store = self._store(tmp_path)
        wt = tmp_path / "worktree"
        wt.mkdir()
        beads = wt / ".beads"
        beads.mkdir()
        # Only some of the forked-dolt artefacts present.
        (beads / "embeddeddolt").mkdir()
        (beads / "issues.jsonl").write_text("[]")
        # No dolt-server.* at all — function should not raise.
        store._strip_worktree_beads_fork(str(wt))
        assert not (beads / "embeddeddolt").exists()
        assert (beads / "issues.jsonl").exists()

    def test_pid_kill_swallows_lookup_error(self, tmp_path, monkeypatch):
        """If the pid in dolt-server.pid is no longer alive, we shouldn't
        crash — just clean up the file."""
        store = self._store(tmp_path)
        wt = tmp_path / "worktree"
        wt.mkdir()
        beads = wt / ".beads"
        beads.mkdir()
        (beads / "dolt-server.pid").write_text("99999999")  # almost certainly dead

        store._strip_worktree_beads_fork(str(wt))

        assert not (beads / "dolt-server.pid").exists()


# ---------------------------------------------------------------------------
# _git_worktree_add_with_recovery — handle transient .git/config lock errors
# (oompah-zlz_2-7iq).
# ---------------------------------------------------------------------------

from oompah.projects import (
    _is_transient_git_config_lock_error,
    _git_worktree_add_with_recovery,
)


# Stderr verbatim from the bug report (oompah-zlz_2-7iq).
_LOCK_STDERR = (
    "Preparing worktree (new branch 'oompah-zlz_2-l7e')\n"
    "error: could not lock config file .git/config: File exists\n"
    "error: unable to write upstream branch configuration\n"
    "hint:\n"
    "hint: After fixing the error cause you may try to fix up\n"
    "hint: the remote tracking information by invoking:\n"
    "hint:   git branch --set-upstream-to=origin/refs/heads/main\n"
)


class TestIsTransientGitConfigLockError:
    def test_matches_bug_report_stderr(self):
        assert _is_transient_git_config_lock_error(_LOCK_STDERR) is True

    def test_not_match_already_exists(self):
        assert _is_transient_git_config_lock_error(
            "fatal: 'wt-path' already exists",
        ) is False

    def test_not_match_empty(self):
        assert _is_transient_git_config_lock_error("") is False


class TestGitWorktreeAddWithRecovery:
    def _cmd(self):
        return ["git", "worktree", "add", "-b", "br", "/wt", "origin/main"]

    def test_first_attempt_success(self, tmp_path):
        wt = tmp_path / "wt"
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            wt.mkdir()
            return _MM(returncode=0, stdout="", stderr="")

        sleeps = []
        with _patch("oompah.projects.subprocess.run", side_effect=fake_run):
            _git_worktree_add_with_recovery(
                self._cmd(), cwd="/repo", wt_path=str(wt),
                sleep_fn=lambda s: sleeps.append(s),
            )
        assert len(calls) == 1
        assert sleeps == []  # no retry needed

    def test_lock_error_with_worktree_created_succeeds(self, tmp_path):
        """The bug report's exact scenario: worktree was prepared on disk,
        only the upstream-config write failed. Treat as success."""
        wt = tmp_path / "wt"

        def fake_run(args, **kwargs):
            # Simulate git creating the worktree path then failing at config.
            wt.mkdir()
            raise subprocess.CalledProcessError(
                returncode=255, cmd=args, output="", stderr=_LOCK_STDERR,
            )

        sleeps = []
        with _patch("oompah.projects.subprocess.run", side_effect=fake_run):
            # Should not raise.
            _git_worktree_add_with_recovery(
                self._cmd(), cwd="/repo", wt_path=str(wt),
                sleep_fn=lambda s: sleeps.append(s),
            )
        # No retry needed once we observed the worktree dir exists.
        assert sleeps == []

    def test_lock_error_without_worktree_retries_then_succeeds(self, tmp_path):
        """Transient lock that doesn't create the worktree on first try
        should back off and retry."""
        wt = tmp_path / "wt"
        attempts = {"n": 0}

        def fake_run(args, **kwargs):
            attempts["n"] += 1
            if attempts["n"] == 1:
                # No worktree dir created; pure lock failure.
                raise subprocess.CalledProcessError(
                    returncode=255, cmd=args, output="", stderr=_LOCK_STDERR,
                )
            # On retry, succeed.
            wt.mkdir()
            return _MM(returncode=0, stdout="", stderr="")

        sleeps = []
        with _patch("oompah.projects.subprocess.run", side_effect=fake_run):
            _git_worktree_add_with_recovery(
                self._cmd(), cwd="/repo", wt_path=str(wt),
                sleep_fn=lambda s: sleeps.append(s),
            )
        assert attempts["n"] == 2
        assert len(sleeps) == 1
        assert 0 < sleeps[0] < 1.0  # exponential backoff started at 0.1s

    def test_lock_error_exhausts_retries_raises(self, tmp_path):
        wt = tmp_path / "wt"

        def fake_run(args, **kwargs):
            raise subprocess.CalledProcessError(
                returncode=255, cmd=args, output="", stderr=_LOCK_STDERR,
            )

        sleeps = []
        with _patch("oompah.projects.subprocess.run", side_effect=fake_run):
            with pytest.raises(subprocess.CalledProcessError) as exc_info:
                _git_worktree_add_with_recovery(
                    self._cmd(), cwd="/repo", wt_path=str(wt),
                    max_attempts=3,
                    sleep_fn=lambda s: sleeps.append(s),
                )
        assert _LOCK_STDERR in (exc_info.value.stderr or "")
        # 3 attempts, sleeping between attempts 1->2 and 2->3.
        assert len(sleeps) == 2

    def test_non_lock_error_raises_immediately(self, tmp_path):
        """Any other CalledProcessError must NOT be retried — the caller's
        existing 'already exists' handling depends on the exception
        flowing through."""
        wt = tmp_path / "wt"

        def fake_run(args, **kwargs):
            raise subprocess.CalledProcessError(
                returncode=128, cmd=args, output="",
                stderr="fatal: invalid reference: origin/main",
            )

        sleeps = []
        with _patch("oompah.projects.subprocess.run", side_effect=fake_run):
            with pytest.raises(subprocess.CalledProcessError):
                _git_worktree_add_with_recovery(
                    self._cmd(), cwd="/repo", wt_path=str(wt),
                    sleep_fn=lambda s: sleeps.append(s),
                )
        # No retries for non-lock errors.
        assert sleeps == []

    def test_already_exists_error_propagates(self, tmp_path):
        """The 'already exists' case must propagate so create_worktree's
        outer handler can fall back to attach-existing-branch."""
        wt = tmp_path / "wt"

        def fake_run(args, **kwargs):
            raise subprocess.CalledProcessError(
                returncode=128, cmd=args, output="",
                stderr="fatal: '/wt' already exists",
            )

        with _patch("oompah.projects.subprocess.run", side_effect=fake_run):
            with pytest.raises(subprocess.CalledProcessError) as exc_info:
                _git_worktree_add_with_recovery(
                    self._cmd(), cwd="/repo", wt_path=str(wt),
                    sleep_fn=lambda s: None,
                )
        assert "already exists" in (exc_info.value.stderr or "")

    def test_timeout_propagates(self, tmp_path):
        wt = tmp_path / "wt"

        def fake_run(args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=args, timeout=30)

        with _patch("oompah.projects.subprocess.run", side_effect=fake_run):
            with pytest.raises(subprocess.TimeoutExpired):
                _git_worktree_add_with_recovery(
                    self._cmd(), cwd="/repo", wt_path=str(wt),
                    sleep_fn=lambda s: None,
                )


class TestCreateWorktreeRecoversFromLockError:
    """End-to-end: bug-report stderr should NOT cause ProjectStore.create_worktree
    to raise ProjectError when the worktree directory was created."""

    def test_create_worktree_succeeds_despite_lock_error(self, tmp_path):
        # Set up a fake project pointing at an empty repo dir.
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".beads").mkdir()

        store = _PS(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        p = _Project(
            id="proj-lock", name="lockrepo",
            repo_url="https://example.com/x.git",
            repo_path=str(repo), branch="main",
        )
        store._projects[p.id] = p

        wt_path = store.worktree_path_for(p.id, "oompah-zlz_2-l7e")

        # Track whether the "main" worktree add was the one that hit the lock.
        seen_lock = {"hit": False}

        def fake_run(args, **kwargs):
            # First match: the actual 'git worktree add -b ...' call. Simulate
            # git creating the worktree path then failing at config write.
            if (
                args[:4] == ["git", "worktree", "add", "-b"]
                and not seen_lock["hit"]
            ):
                seen_lock["hit"] = True
                os.makedirs(wt_path, exist_ok=True)
                raise subprocess.CalledProcessError(
                    returncode=255, cmd=args, output="", stderr=_LOCK_STDERR,
                )
            # All other git calls (fetch, config user.name/email, etc.) succeed.
            return _MM(returncode=0, stdout="", stderr="")

        with _patch("oompah.projects.subprocess.run", side_effect=fake_run):
            # Must NOT raise ProjectError.
            returned = store.create_worktree(p.id, "oompah-zlz_2-l7e")

        assert seen_lock["hit"] is True
        assert returned == wt_path
        assert os.path.isdir(wt_path)


# ---------------------------------------------------------------------------
# Ref namespace conflict recovery (oompah-zlz_2-kudu).
#
# When a previous run created a nested-style branch like
# `trickle-u02z/strip-signing`, subsequent `git worktree add -b trickle-u02z`
# fails because git's filesystem-based ref storage can't have both
# refs/heads/trickle-u02z (file) and refs/heads/trickle-u02z/<sub>.
# ---------------------------------------------------------------------------

from oompah.projects import (
    _is_ref_namespace_conflict_error,
    _resolve_ref_namespace_conflict,
    _branch_name_from_worktree_cmd,
)


# Stderr verbatim from the bug report (oompah-zlz_2-kudu).
_NAMESPACE_STDERR = (
    "Preparing worktree (new branch 'trickle-u02z')\n"
    "fatal: cannot lock ref 'refs/heads/trickle-u02z': "
    "'refs/heads/trickle-u02z/strip-signing' exists; "
    "cannot create 'refs/heads/trickle-u02z'\n"
)


class TestIsRefNamespaceConflictError:
    def test_matches_bug_report_stderr(self):
        assert _is_ref_namespace_conflict_error(
            _NAMESPACE_STDERR, "trickle-u02z",
        ) is True

    def test_does_not_match_other_branch(self):
        """A conflict for branch X must not be reported for branch Y."""
        assert _is_ref_namespace_conflict_error(
            _NAMESPACE_STDERR, "other-branch",
        ) is False

    def test_does_not_match_lock_config_error(self):
        """Must not confuse with the transient .git/config lock error."""
        assert _is_ref_namespace_conflict_error(
            "error: could not lock config file .git/config: File exists",
            "trickle-u02z",
        ) is False

    def test_empty_stderr(self):
        assert _is_ref_namespace_conflict_error("", "foo") is False

    def test_empty_branch_name(self):
        assert _is_ref_namespace_conflict_error(_NAMESPACE_STDERR, "") is False


class TestBranchNameFromWorktreeCmd:
    def test_extract_with_dash_b(self):
        cmd = ["git", "worktree", "add", "-b", "trickle-u02z",
               "/wt", "origin/main"]
        assert _branch_name_from_worktree_cmd(cmd) == "trickle-u02z"

    def test_extract_with_dash_capital_b(self):
        cmd = ["git", "worktree", "add", "-B", "epic-foo", "/wt", "origin/main"]
        assert _branch_name_from_worktree_cmd(cmd) == "epic-foo"

    def test_no_branch_flag_returns_none(self):
        """When the command attaches an existing branch (no -b/-B), return None."""
        cmd = ["git", "worktree", "add", "/wt", "existing-branch"]
        assert _branch_name_from_worktree_cmd(cmd) is None

    def test_unrecognised_shape(self):
        assert _branch_name_from_worktree_cmd(["git", "status"]) is None


class TestResolveRefNamespaceConflict:
    def test_renames_nested_local_refs(self, tmp_path):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[:2] == ["git", "for-each-ref"]:
                # Two nested local branches under trickle-u02z/.
                return _MM(
                    returncode=0,
                    stdout="trickle-u02z/strip-signing\ntrickle-u02z/other\n",
                    stderr="",
                )
            if args[:3] == ["git", "show-ref", "--verify"]:
                # No collision on the new flat names.
                return _MM(returncode=1, stdout="", stderr="")
            if args[:3] == ["git", "branch", "-m"]:
                return _MM(returncode=0, stdout="", stderr="")
            return _MM(returncode=0, stdout="", stderr="")

        with _patch("oompah.projects.subprocess.run", side_effect=fake_run):
            renames = _resolve_ref_namespace_conflict("/repo", "trickle-u02z")
        assert renames == [
            ("trickle-u02z/strip-signing", "trickle-u02z__strip-signing"),
            ("trickle-u02z/other", "trickle-u02z__other"),
        ]
        # Verify branch -m was called with the right arguments.
        mv_calls = [c for c in calls if c[:3] == ["git", "branch", "-m"]]
        assert mv_calls == [
            ["git", "branch", "-m", "trickle-u02z/strip-signing",
             "trickle-u02z__strip-signing"],
            ["git", "branch", "-m", "trickle-u02z/other",
             "trickle-u02z__other"],
        ]

    def test_no_nested_refs_returns_empty(self, tmp_path):
        def fake_run(args, **kwargs):
            if args[:2] == ["git", "for-each-ref"]:
                return _MM(returncode=0, stdout="", stderr="")
            return _MM(returncode=0, stdout="", stderr="")

        with _patch("oompah.projects.subprocess.run", side_effect=fake_run):
            renames = _resolve_ref_namespace_conflict("/repo", "foo")
        assert renames == []

    def test_collision_on_target_name_uses_suffix(self, tmp_path):
        """If the renamed-to target already exists, append a numeric suffix."""
        seen_collisions = {"n": 0}

        def fake_run(args, **kwargs):
            if args[:2] == ["git", "for-each-ref"]:
                return _MM(
                    returncode=0,
                    stdout="trickle-u02z/strip-signing\n",
                    stderr="",
                )
            if args[:3] == ["git", "show-ref", "--verify"]:
                # First lookup says target exists (returncode=0), second is free.
                seen_collisions["n"] += 1
                if seen_collisions["n"] == 1:
                    return _MM(returncode=0, stdout="", stderr="")
                return _MM(returncode=1, stdout="", stderr="")
            if args[:3] == ["git", "branch", "-m"]:
                return _MM(returncode=0, stdout="", stderr="")
            return _MM(returncode=0, stdout="", stderr="")

        with _patch("oompah.projects.subprocess.run", side_effect=fake_run):
            renames = _resolve_ref_namespace_conflict("/repo", "trickle-u02z")
        assert renames == [
            ("trickle-u02z/strip-signing", "trickle-u02z__strip-signing_1"),
        ]

    def test_for_each_ref_failure_returns_empty(self, tmp_path):
        def fake_run(args, **kwargs):
            if args[:2] == ["git", "for-each-ref"]:
                return _MM(returncode=1, stdout="", stderr="boom")
            return _MM(returncode=0, stdout="", stderr="")

        with _patch("oompah.projects.subprocess.run", side_effect=fake_run):
            renames = _resolve_ref_namespace_conflict("/repo", "foo")
        assert renames == []

    def test_rename_failure_skips_branch(self, tmp_path):
        """If 'git branch -m' fails for one branch, others should still be tried."""
        def fake_run(args, **kwargs):
            if args[:2] == ["git", "for-each-ref"]:
                return _MM(
                    returncode=0,
                    stdout="foo/a\nfoo/b\n",
                    stderr="",
                )
            if args[:3] == ["git", "show-ref", "--verify"]:
                return _MM(returncode=1, stdout="", stderr="")
            if args[:3] == ["git", "branch", "-m"]:
                # Fail for the first one (foo/a -> foo__a), succeed for second.
                if args[3] == "foo/a":
                    return _MM(returncode=1, stdout="", stderr="locked")
                return _MM(returncode=0, stdout="", stderr="")
            return _MM(returncode=0, stdout="", stderr="")

        with _patch("oompah.projects.subprocess.run", side_effect=fake_run):
            renames = _resolve_ref_namespace_conflict("/repo", "foo")
        assert renames == [("foo/b", "foo__b")]

    def test_empty_branch_name_returns_empty(self):
        assert _resolve_ref_namespace_conflict("/repo", "") == []


class TestGitWorktreeAddWithRefNamespaceConflict:
    """End-to-end: _git_worktree_add_with_recovery should auto-recover from
    the trickle-u02z/strip-signing-style namespace conflict by renaming the
    nested local branches and retrying once."""

    def _cmd(self):
        return ["git", "worktree", "add", "-b", "trickle-u02z",
                "/wt", "origin/main"]

    def test_recovers_by_renaming_and_retrying(self, tmp_path):
        wt = tmp_path / "wt"
        attempts = {"n": 0}

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "worktree", "add"]:
                attempts["n"] += 1
                if attempts["n"] == 1:
                    raise subprocess.CalledProcessError(
                        returncode=128, cmd=args, output="",
                        stderr=_NAMESPACE_STDERR,
                    )
                # Second attempt: succeed.
                wt.mkdir()
                return _MM(returncode=0, stdout="", stderr="")
            if args[:2] == ["git", "for-each-ref"]:
                return _MM(
                    returncode=0,
                    stdout="trickle-u02z/strip-signing\n",
                    stderr="",
                )
            if args[:3] == ["git", "show-ref", "--verify"]:
                return _MM(returncode=1, stdout="", stderr="")
            if args[:3] == ["git", "branch", "-m"]:
                return _MM(returncode=0, stdout="", stderr="")
            return _MM(returncode=0, stdout="", stderr="")

        sleeps = []
        with _patch("oompah.projects.subprocess.run", side_effect=fake_run):
            _git_worktree_add_with_recovery(
                self._cmd(), cwd="/repo", wt_path=str(wt),
                sleep_fn=lambda s: sleeps.append(s),
            )
        # Two worktree add attempts: original failure + post-rename success.
        assert attempts["n"] == 2
        # No exponential-backoff sleeps for namespace conflict (it's
        # one-shot mitigation, not a transient race).
        assert sleeps == []

    def test_namespace_conflict_with_no_renamable_refs_propagates(self, tmp_path):
        """If for_each_ref returns nothing (e.g. the offending ref lives in
        packed-refs and listing it failed), re-raise so the operator sees it."""
        wt = tmp_path / "wt"

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "worktree", "add"]:
                raise subprocess.CalledProcessError(
                    returncode=128, cmd=args, output="",
                    stderr=_NAMESPACE_STDERR,
                )
            if args[:2] == ["git", "for-each-ref"]:
                return _MM(returncode=0, stdout="", stderr="")
            return _MM(returncode=0, stdout="", stderr="")

        with _patch("oompah.projects.subprocess.run", side_effect=fake_run):
            with pytest.raises(subprocess.CalledProcessError) as exc_info:
                _git_worktree_add_with_recovery(
                    self._cmd(), cwd="/repo", wt_path=str(wt),
                    sleep_fn=lambda s: None,
                )
        assert "cannot lock ref" in (exc_info.value.stderr or "")

    def test_namespace_recovery_is_one_shot(self, tmp_path):
        """If the namespace error recurs after a successful rename, do NOT
        loop — re-raise immediately. Guards against pathological packed-ref
        states where renaming a local branch doesn't actually free the
        namespace."""
        wt = tmp_path / "wt"
        attempts = {"n": 0}

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "worktree", "add"]:
                attempts["n"] += 1
                # Always fail with namespace conflict.
                raise subprocess.CalledProcessError(
                    returncode=128, cmd=args, output="",
                    stderr=_NAMESPACE_STDERR,
                )
            if args[:2] == ["git", "for-each-ref"]:
                return _MM(
                    returncode=0,
                    stdout="trickle-u02z/strip-signing\n",
                    stderr="",
                )
            if args[:3] == ["git", "show-ref", "--verify"]:
                return _MM(returncode=1, stdout="", stderr="")
            if args[:3] == ["git", "branch", "-m"]:
                return _MM(returncode=0, stdout="", stderr="")
            return _MM(returncode=0, stdout="", stderr="")

        with _patch("oompah.projects.subprocess.run", side_effect=fake_run):
            with pytest.raises(subprocess.CalledProcessError):
                _git_worktree_add_with_recovery(
                    self._cmd(), cwd="/repo", wt_path=str(wt),
                    sleep_fn=lambda s: None,
                )
        # Exactly 2 worktree add attempts: original + 1 post-rename retry.
        # No further loops.
        assert attempts["n"] == 2
