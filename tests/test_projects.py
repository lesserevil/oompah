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

from oompah.projects import _bootstrap_lfs


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
