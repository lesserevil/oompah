"""Tests for managed repository health checks."""

from unittest.mock import patch

from oompah.repo_health import ensure_repo_sound


def test_ensure_repo_sound_prunes_remote_tracking_refs_during_fetch(tmp_path):
    repo = tmp_path / "repo"
    git_dir = repo / ".git"
    git_dir.mkdir(parents=True)
    calls: list[list[str]] = []

    def fake_run_git(args, repo_path, *, timeout=60):
        calls.append(list(args))
        if args == ["symbolic-ref", "--short", "HEAD"]:
            return 0, "main\n", ""
        if args[:2] == ["rev-list", "--count"]:
            return 0, "0\n", ""
        return 0, "", ""

    with patch("oompah.repo_health._run_git", side_effect=fake_run_git):
        result = ensure_repo_sound(str(repo), "main")

    assert result["sound"] is True
    assert ["fetch", "--prune", "origin"] in calls
