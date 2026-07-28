"""Tests for the pytest-session Git network remote barrier (OOMPAH-491).

Coverage:

  § 1  Blocked schemes — HTTPS, HTTP, SSH URL, SCP-style, git-protocol
       remotes all fail without DNS/network access.
  § 2  Allowed transports — absolute-path bare remote and a temporary
       ``file://`` bare remote can be fetched and pushed successfully.
  § 3  Config-count preservation — existing numbered
       ``GIT_CONFIG_COUNT/KEY_N/VALUE_N`` entries survive the barrier
       installation (tested via the ``build_network_barrier_env`` helper).
  § 4  Session barrier is active — the current pytest session has the barrier
       env vars set so git subprocesses inherit the guard.

All tests use local filesystem fixtures only; no live network connections are
made or expected.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterator

import pytest

from tests.conftest import (
    _BARRIER_BASE,
    _BARRIER_RULES,
    build_network_barrier_env,
)


# ---------------------------------------------------------------------------
# Shared git helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run ``git <args>`` in *repo*, capturing output.  Never raises on failure."""
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


def _git_check(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run ``git <args>`` in *repo* and raise if it fails."""
    r = _git(repo, *args)
    if r.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed (exit {r.returncode}):\n"
            f"  stdout: {r.stdout.strip()}\n"
            f"  stderr: {r.stderr.strip()}"
        )
    return r


def _make_bare_repo(path: Path) -> Path:
    """Initialise a bare git repository at *path* and return the path."""
    path.mkdir(parents=True, exist_ok=True)
    _git_check(path, "init", "--bare")
    return path


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


def _ls_remote(url: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run ``git ls-remote <url>`` from *cwd*."""
    return subprocess.run(
        ["git", "ls-remote", url],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# § 1  Blocked schemes
# ---------------------------------------------------------------------------


class TestBlockedSchemes:
    """Network URL schemes must be redirected to a nonexistent local path."""

    @pytest.fixture(autouse=True)
    def _work_repo(self, tmp_path: Path) -> Iterator[Path]:
        """A minimal working repo to run git commands from."""
        self.work = _make_working_repo(tmp_path / "work")
        yield self.work

    def _assert_blocked(self, url: str) -> None:
        """Assert that ``git ls-remote <url>`` fails and the error mentions the barrier."""
        result = _ls_remote(url, self.work)
        assert result.returncode != 0, (
            f"Expected git ls-remote {url!r} to fail (blocked by barrier), "
            f"but it succeeded."
        )
        combined = result.stdout + result.stderr
        assert _BARRIER_BASE in combined, (
            f"Expected error output to mention barrier path {_BARRIER_BASE!r}, "
            f"but got:\n{combined}"
        )

    def test_https_remote_is_blocked(self) -> None:
        """HTTPS remotes must be redirected and fail without network access."""
        self._assert_blocked("https://github.com/example/repo.git")

    def test_http_remote_is_blocked(self) -> None:
        """HTTP remotes must be redirected and fail without network access."""
        self._assert_blocked("http://github.com/example/repo.git")

    def test_ssh_url_remote_is_blocked(self) -> None:
        """SSH URL-style remotes (``ssh://``) must be redirected and fail."""
        self._assert_blocked("ssh://git@github.com/example/repo.git")

    def test_scp_style_remote_is_blocked(self) -> None:
        """SCP-style remotes (``git@host:path``) must be redirected and fail."""
        self._assert_blocked("git@github.com:example/repo.git")

    def test_git_protocol_remote_is_blocked(self) -> None:
        """git:// protocol remotes must be redirected and fail."""
        self._assert_blocked("git://github.com/example/repo.git")


# ---------------------------------------------------------------------------
# § 2  Allowed transports
# ---------------------------------------------------------------------------


class TestAllowedTransports:
    """Absolute-path and file:// remotes must remain fully usable."""

    def _setup_pair(self, tmp_path: Path) -> tuple[Path, Path]:
        """Return (work, bare) with one commit pushed from work to bare."""
        bare = _make_bare_repo(tmp_path / "bare.git")
        work = _make_working_repo(tmp_path / "work")
        return work, bare

    def test_absolute_path_remote_fetch(self, tmp_path: Path) -> None:
        """``git ls-remote /path/to/bare.git`` must succeed."""
        work, bare = self._setup_pair(tmp_path)
        result = _ls_remote(str(bare), work)
        assert result.returncode == 0, (
            f"Expected git ls-remote with absolute path to succeed, but it failed:\n"
            f"  stderr: {result.stderr.strip()}"
        )

    def test_absolute_path_remote_push(self, tmp_path: Path) -> None:
        """``git push`` to an absolute-path bare remote must succeed."""
        work, bare = self._setup_pair(tmp_path)
        _git_check(work, "remote", "add", "origin", str(bare))
        result = _git(work, "push", "--set-upstream", "origin", "main")
        assert result.returncode == 0, (
            f"Expected git push to absolute-path bare remote to succeed:\n"
            f"  stderr: {result.stderr.strip()}"
        )
        # Verify the commit landed in the bare repo.
        r = _git(bare, "rev-parse", "main")
        assert r.returncode == 0 and r.stdout.strip(), (
            "Expected 'main' branch in bare repo after push, but rev-parse failed."
        )

    def test_file_url_remote_fetch(self, tmp_path: Path) -> None:
        """``git ls-remote file:///path/to/bare.git`` must succeed."""
        work, bare = self._setup_pair(tmp_path)
        file_url = bare.as_uri()  # file:///path/to/bare.git
        result = _ls_remote(file_url, work)
        assert result.returncode == 0, (
            f"Expected git ls-remote with file:// URL to succeed, but it failed:\n"
            f"  stderr: {result.stderr.strip()}"
        )

    def test_file_url_remote_push(self, tmp_path: Path) -> None:
        """``git push`` to a ``file://`` bare remote must succeed."""
        work, bare = self._setup_pair(tmp_path)
        file_url = bare.as_uri()
        _git_check(work, "remote", "add", "origin", file_url)
        result = _git(work, "push", "--set-upstream", "origin", "main")
        assert result.returncode == 0, (
            f"Expected git push to file:// bare remote to succeed:\n"
            f"  stderr: {result.stderr.strip()}"
        )
        # Verify the commit landed in the bare repo.
        r = _git(bare, "rev-parse", "main")
        assert r.returncode == 0 and r.stdout.strip(), (
            "Expected 'main' branch in bare repo after push, but rev-parse failed."
        )


# ---------------------------------------------------------------------------
# § 3  GIT_CONFIG_COUNT preservation
# ---------------------------------------------------------------------------


class TestConfigCountPreservation:
    """Pre-existing GIT_CONFIG_COUNT/KEY_N/VALUE_N entries must survive."""

    def test_no_preexisting_entries_installs_five_rules(self) -> None:
        """When starting from an empty config count, five barrier rules are added."""
        env_in: dict[str, str] = {}
        env_out = build_network_barrier_env(env_in)

        assert env_out["GIT_CONFIG_COUNT"] == str(len(_BARRIER_RULES))
        for i in range(len(_BARRIER_RULES)):
            assert f"GIT_CONFIG_KEY_{i}" in env_out
            assert f"GIT_CONFIG_VALUE_{i}" in env_out

    def test_preexisting_entry_at_index_zero_is_preserved(self) -> None:
        """A pre-existing entry at index 0 is not overwritten by the barrier."""
        env_in: dict[str, str] = {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.quotePath",
            "GIT_CONFIG_VALUE_0": "false",
        }
        env_out = build_network_barrier_env(env_in)

        # Pre-existing entry unchanged.
        assert env_out["GIT_CONFIG_KEY_0"] == "core.quotePath"
        assert env_out["GIT_CONFIG_VALUE_0"] == "false"

        # Count is 1 (pre-existing) + 5 (barrier) = 6.
        assert int(env_out["GIT_CONFIG_COUNT"]) == 1 + len(_BARRIER_RULES)

        # Barrier entries start at index 1.
        for i, (cfg_key, cfg_value) in enumerate(_BARRIER_RULES):
            assert env_out[f"GIT_CONFIG_KEY_{1 + i}"] == cfg_key
            assert env_out[f"GIT_CONFIG_VALUE_{1 + i}"] == cfg_value

    def test_multiple_preexisting_entries_are_preserved(self) -> None:
        """Multiple pre-existing entries are all preserved at their original indices."""
        env_in: dict[str, str] = {
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": "core.quotePath",
            "GIT_CONFIG_VALUE_0": "false",
            "GIT_CONFIG_KEY_1": "core.autocrlf",
            "GIT_CONFIG_VALUE_1": "input",
        }
        env_out = build_network_barrier_env(env_in)

        assert env_out["GIT_CONFIG_KEY_0"] == "core.quotePath"
        assert env_out["GIT_CONFIG_VALUE_0"] == "false"
        assert env_out["GIT_CONFIG_KEY_1"] == "core.autocrlf"
        assert env_out["GIT_CONFIG_VALUE_1"] == "input"
        assert int(env_out["GIT_CONFIG_COUNT"]) == 2 + len(_BARRIER_RULES)

    def test_preexisting_entries_visible_to_git_subprocess(
        self, tmp_path: Path
    ) -> None:
        """Pre-existing config entries are visible to git alongside the barrier.

        This runs a real git subprocess with a composed env dict that combines
        one pre-existing entry (``core.commentChar``) with the barrier rules,
        then verifies git can read the pre-existing entry.
        """
        repo = _make_working_repo(tmp_path / "repo")

        # Build the test environment: one pre-existing entry, then barrier.
        pre_env: dict[str, str] = {
            **os.environ,
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.commentChar",
            "GIT_CONFIG_VALUE_0": ";",
        }
        full_env = build_network_barrier_env(pre_env)

        result = subprocess.run(
            ["git", "config", "--get", "core.commentChar"],
            cwd=str(repo),
            env=full_env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"git config --get core.commentChar failed:\n{result.stderr.strip()}"
        )
        assert result.stdout.strip() == ";", (
            f"Expected ';', got {result.stdout.strip()!r}"
        )

    def test_barrier_values_cover_all_required_schemes(self) -> None:
        """The barrier must block https, http, ssh://, git://, and git@ prefixes."""
        env_out = build_network_barrier_env({})
        count = int(env_out["GIT_CONFIG_COUNT"])
        blocked_prefixes = {
            env_out[f"GIT_CONFIG_VALUE_{i}"] for i in range(count)
        }
        required = {"https://", "http://", "ssh://", "git://", "git@"}
        assert required.issubset(blocked_prefixes), (
            f"Missing blocked prefixes: {required - blocked_prefixes}"
        )


# ---------------------------------------------------------------------------
# § 4  Session barrier is active
# ---------------------------------------------------------------------------


class TestSessionBarrierIsActive:
    """The pytest session itself must have the barrier env vars installed."""

    def test_git_config_count_is_set(self) -> None:
        """``GIT_CONFIG_COUNT`` must be set in the current process environment."""
        count_str = os.environ.get("GIT_CONFIG_COUNT")
        assert count_str is not None, (
            "GIT_CONFIG_COUNT is not set — the _block_network_git_remotes "
            "session fixture may not have run."
        )
        count = int(count_str)
        assert count >= len(_BARRIER_RULES), (
            f"Expected GIT_CONFIG_COUNT >= {len(_BARRIER_RULES)}, got {count}"
        )

    def test_barrier_keys_are_present_in_env(self) -> None:
        """All barrier ``GIT_CONFIG_KEY_N`` entries must be in ``os.environ``."""
        count = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
        barrier_keys_found: list[str] = []
        for i in range(count):
            key_val = os.environ.get(f"GIT_CONFIG_KEY_{i}", "")
            if _BARRIER_BASE in key_val:
                barrier_keys_found.append(key_val)

        assert len(barrier_keys_found) == len(_BARRIER_RULES), (
            f"Expected {len(_BARRIER_RULES)} barrier entries in env, "
            f"found {len(barrier_keys_found)}: {barrier_keys_found}"
        )

    def test_barrier_is_inherited_by_git_subprocess(self, tmp_path: Path) -> None:
        """A git subprocess inherits the barrier and cannot reach HTTPS remotes."""
        work = _make_working_repo(tmp_path / "work")
        result = _ls_remote("https://github.com/example/repo-does-not-exist.git", work)
        assert result.returncode != 0, (
            "Expected git ls-remote https://... to fail (barrier active), "
            "but it succeeded — the barrier may not be working."
        )
        combined = result.stdout + result.stderr
        assert _BARRIER_BASE in combined, (
            f"Expected barrier marker {_BARRIER_BASE!r} in git output, "
            f"but got:\n{combined}"
        )
