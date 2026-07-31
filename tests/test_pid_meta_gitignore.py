"""Tests for PID metadata gitignore handling (OOMPAH-654).

Regression test to ensure lifecycle metadata files (.oompah.pid.meta) and
atomic temporary variants don't dirty git status, while unrelated *.meta
files remain visible.

Coverage:
- .oompah.pid.meta files are ignored by git
- .oompah.pid.meta.tmp.* temporary files are ignored by git
- Unrelated *.meta files are NOT ignored
- git status --porcelain remains clean with lifecycle metadata present
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterator

import pytest


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run ``git <args>`` in *repo*, capturing output. Never raises on failure."""
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


def _git_check(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run ``git <args>`` in *repo* and raise if it fails."""
    r = _run_git(repo, *args)
    if r.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed (exit {r.returncode}):\n"
            f"  stdout: {r.stdout.strip()}\n"
            f"  stderr: {r.stderr.strip()}"
        )
    return r


def _make_working_repo(path: Path) -> Path:
    """Initialise a working git repository with an initial commit."""
    path.mkdir(parents=True, exist_ok=True)
    _git_check(path, "init", "-b", "main")
    _git_check(path, "config", "user.name", "Test User")
    _git_check(path, "config", "user.email", "test@example.com")
    (path / "README.md").write_text("# test\n", encoding="utf-8")
    _git_check(path, "add", ".")
    _git_check(path, "commit", "-m", "initial")
    return path


class TestPidMetaGitignore:
    """PID metadata files must not dirty git status."""

    @pytest.fixture(autouse=True)
    def _work_repo(self, tmp_path: Path) -> Iterator[Path]:
        """A minimal working repo with .gitignore rules from the project."""
        self.work = _make_working_repo(tmp_path / "work")

        # Copy .gitignore from the project root to the test repo.
        # This ensures we test the actual gitignore rules.
        try:
            project_gitignore = Path(".gitignore").read_text(encoding="utf-8")
            (self.work / ".gitignore").write_text(project_gitignore, encoding="utf-8")
            _git_check(self.work, "add", ".gitignore")
            _git_check(self.work, "commit", "-m", "add gitignore")
        except FileNotFoundError:
            # If .gitignore doesn't exist at root, that's okay for testing
            pass

        yield self.work

    def _git_status_porcelain(self) -> str:
        """Return git status --porcelain output (untracked and modified files)."""
        result = _run_git(self.work, "status", "--porcelain")
        return result.stdout

    def _assert_status_clean(self, message: str = "") -> None:
        """Assert that git status --porcelain shows no changes."""
        status = self._git_status_porcelain()
        assert status == "", (
            f"Expected clean git status, but got:\n{status}" + (f"\n{message}" if message else "")
        )

    def test_pid_file_does_not_dirty_status(self) -> None:
        """Creating .oompah.pid does not dirty git status."""
        (self.work / ".oompah.pid").write_text("12345\n", encoding="utf-8")
        self._assert_status_clean("After creating .oompah.pid")

    def test_pid_meta_file_does_not_dirty_status(self) -> None:
        """Creating .oompah.pid.meta does not dirty git status."""
        meta = {
            "pid": 12345,
            "cwd": str(self.work),
            "process_group": 12345,
            "session": 12345,
        }
        (self.work / ".oompah.pid.meta").write_text(
            json.dumps(meta), encoding="utf-8"
        )
        self._assert_status_clean("After creating .oompah.pid.meta")

    def test_pid_meta_tmp_file_does_not_dirty_status(self) -> None:
        """Creating .oompah.pid.meta.tmp.XXXXXX does not dirty git status.

        Simulates the atomic write pattern used in Makefile:
        META_TMP=$(mktemp "$(PID_META_FILE).tmp.XXXXXX")
        """
        meta = {
            "pid": 12345,
            "cwd": str(self.work),
            "process_group": 12345,
            "session": 12345,
        }
        (self.work / ".oompah.pid.meta.tmp.ABC123").write_text(
            json.dumps(meta), encoding="utf-8"
        )
        self._assert_status_clean("After creating .oompah.pid.meta.tmp.ABC123")

    def test_all_lifecycle_artifacts_together_do_not_dirty_status(self) -> None:
        """All PID lifecycle artifacts together don't dirty git status."""
        # Create all the files that make start/restart might create
        (self.work / ".oompah.pid").write_text("12345\n", encoding="utf-8")

        meta = {
            "pid": 12345,
            "cwd": str(self.work),
            "process_group": 12345,
            "session": 12345,
        }
        (self.work / ".oompah.pid.meta").write_text(
            json.dumps(meta), encoding="utf-8"
        )
        (self.work / ".oompah.pid.meta.tmp.XYZ789").write_text(
            json.dumps(meta), encoding="utf-8"
        )

        self._assert_status_clean("After creating all lifecycle artifacts")

    def test_unrelated_meta_files_are_visible(self) -> None:
        """Unrelated *.meta files are NOT ignored (remain visible to git)."""
        # Create an unrelated .meta file
        (self.work / "config.meta").write_text("some metadata\n", encoding="utf-8")

        status = self._git_status_porcelain()
        assert "config.meta" in status, (
            f"Expected unrelated 'config.meta' to be visible in git status, "
            f"but got:\n{status}"
        )

    def test_pid_meta_ignored_but_unrelated_meta_visible(self) -> None:
        """PID metadata is ignored while unrelated metadata is visible.

        This is the key requirement: we ignore only lifecycle metadata,
        not all *.meta files.
        """
        # Create PID metadata (should be ignored)
        meta = {
            "pid": 12345,
            "cwd": str(self.work),
            "process_group": 12345,
            "session": 12345,
        }
        (self.work / ".oompah.pid.meta").write_text(
            json.dumps(meta), encoding="utf-8"
        )

        # Create unrelated metadata (should be visible)
        (self.work / "other.meta").write_text("other metadata\n", encoding="utf-8")

        status = self._git_status_porcelain()

        # PID metadata should NOT appear
        assert ".oompah.pid.meta" not in status, (
            f"Expected .oompah.pid.meta to be ignored, but it appears in:\n{status}"
        )

        # Unrelated metadata should appear
        assert "other.meta" in status, (
            f"Expected other.meta to be visible, but it doesn't appear in:\n{status}"
        )
