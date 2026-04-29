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
