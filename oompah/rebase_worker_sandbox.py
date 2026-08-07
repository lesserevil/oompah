"""Restricted executor for direct shared-epic rebase worker commands.

The model/provider process remains in the server control plane so it can use
its provider credential.  Every command it asks oompah to run is instead
executed here: in an empty Bubblewrap namespace with no network, operator
home, worker runtime, or task-handoff capability.  Task state transitions are
handled by the in-process tool callback, never by a shell CLI invocation.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Mapping


class RebaseWorkerSandboxUnavailable(RuntimeError):
    """Raised when mandatory rebase-worker isolation cannot be created."""


class RestrictedRebaseCommand(list[str]):
    """Bubblewrap argv plus private, server-owned files to remove afterwards."""

    def __init__(self, args: list[str], runtime_dir: Path) -> None:
        super().__init__(args)
        self._runtime_dir = runtime_dir

    def cleanup(self) -> None:
        shutil.rmtree(self._runtime_dir, ignore_errors=True)


def _sandbox_environment(environment: Mapping[str, str]) -> dict[str, str]:
    """Return command-only environment; credentials stay in control plane."""
    allowed = {
        key: str(value)
        for key, value in environment.items()
        if key in {"LANG", "LANGUAGE", "LC_ALL", "LC_CTYPE", "TZ", "TERM", "NO_COLOR"}
    }
    allowed.update(
        {
            "PATH": "/usr/bin:/bin",
            "HOME": "/home/oompah",
            "XDG_CONFIG_HOME": "/home/oompah/.config",
            "XDG_CACHE_HOME": "/home/oompah/.cache",
            "XDG_DATA_HOME": "/home/oompah/.local/share",
            "XDG_RUNTIME_DIR": "/tmp/runtime",
            "TMPDIR": "/tmp",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "/bin/false",
            "SSH_ASKPASS": "/bin/false",
            "GIT_SSH_COMMAND": "/bin/false",
        }
    )
    return allowed


def _real_directory(path: Path, *, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise RebaseWorkerSandboxUnavailable(f"{label} is unavailable") from exc
    if not resolved.is_dir() or path.is_symlink():
        raise RebaseWorkerSandboxUnavailable(f"{label} is not a real directory")
    return resolved


def _worktree_git_dirs(workspace: Path) -> tuple[Path, Path]:
    """Resolve linked-worktree metadata without consulting Git configuration."""
    dot_git = workspace / ".git"
    if dot_git.is_dir() and not dot_git.is_symlink():
        git_dir = _real_directory(dot_git, label="workspace git directory")
    elif dot_git.is_file() and not dot_git.is_symlink():
        try:
            line = dot_git.read_text(encoding="utf-8").splitlines()[0]
        except (OSError, IndexError) as exc:
            raise RebaseWorkerSandboxUnavailable("workspace git file is invalid") from exc
        prefix = "gitdir: "
        if not line.startswith(prefix):
            raise RebaseWorkerSandboxUnavailable("workspace git file is invalid")
        candidate = Path(line[len(prefix) :])
        if not candidate.is_absolute():
            candidate = dot_git.parent / candidate
        git_dir = _real_directory(candidate, label="linked-worktree git directory")
    else:
        raise RebaseWorkerSandboxUnavailable("workspace has no safe git metadata")

    common_file = git_dir / "commondir"
    if common_file.is_file() and not common_file.is_symlink():
        try:
            raw = common_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RebaseWorkerSandboxUnavailable("linked-worktree common git directory is invalid") from exc
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = git_dir / candidate
        common_dir = _real_directory(candidate, label="common git directory")
    else:
        common_dir = git_dir
    if git_dir == common_dir:
        raise RebaseWorkerSandboxUnavailable(
            "epic-rebase workspace must be a linked Git worktree"
        )
    return git_dir, common_dir


def _safe_git_config(source: Path, destination: Path) -> None:
    """Copy only local Git behaviour, never remotes, helpers, or includes."""
    if not source.exists():
        destination.touch(mode=0o600)
        return
    if source.is_symlink() or not source.is_file():
        raise RebaseWorkerSandboxUnavailable("Git config is not a regular file")
    try:
        listed = subprocess.run(
            ["git", "config", "--null", "--file", str(source), "--list"],
            check=True,
            capture_output=True,
            timeout=5,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise RebaseWorkerSandboxUnavailable("could not sanitize Git config") from exc
    allowed_prefixes = ("core.", "extensions.", "branch.", "user.", "merge.", "rebase.", "rerere.", "commit.")
    for entry in listed.split(b"\0"):
        if not entry:
            continue
        try:
            key, value = entry.decode("utf-8").split("\n", 1)
        except (UnicodeDecodeError, ValueError) as exc:
            raise RebaseWorkerSandboxUnavailable("Git config contains an invalid entry") from exc
        if not key.lower().startswith(allowed_prefixes):
            continue
        try:
            subprocess.run(
                ["git", "config", "--file", str(destination), "--add", key, value],
                check=True,
                capture_output=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RebaseWorkerSandboxUnavailable("could not write sanitized Git config") from exc


def restricted_rebase_command(
    command: str,
    workspace: Path,
    environment: Mapping[str, str],
) -> RestrictedRebaseCommand:
    """Build a Bubblewrap command with no remote-write authority.

    The linked worktree's minimum Git metadata is mounted at its original
    absolute paths.  A server-generated config overlays both local config
    locations, keeping rebase/index/ref operations working without exposing
    remote URLs, include files, or credential helpers.
    """
    bubblewrap = shutil.which("bwrap")
    if not bubblewrap:
        raise RebaseWorkerSandboxUnavailable(
            "bubblewrap is unavailable; refusing an unsandboxed epic-rebase command"
        )
    workspace = _real_directory(workspace, label="epic-rebase workspace")
    git_dir, common_dir = _worktree_git_dirs(workspace)
    runtime_dir = Path(tempfile.mkdtemp(prefix="oompah-rebase-sandbox-"))
    os.chmod(runtime_dir, 0o700)
    try:
        config_overlays: list[tuple[Path, Path]] = []
        common_config = runtime_dir / "common-config"
        _safe_git_config(common_dir / "config", common_config)
        config_overlays.append((common_config, common_dir / "config"))
        if git_dir != common_dir and (git_dir / "config.worktree").exists():
            worktree_config = runtime_dir / "worktree-config"
            _safe_git_config(git_dir / "config.worktree", worktree_config)
            config_overlays.append((worktree_config, git_dir / "config.worktree"))

        args = [
            bubblewrap,
            "--die-with-parent",
            "--new-session",
            "--unshare-user",
            "--unshare-pid",
            "--unshare-net",
            "--clearenv",
            "--tmpfs", "/",
            "--dir", "/usr",
            "--ro-bind", "/usr", "/usr",
            "--symlink", "usr/bin", "/bin",
            "--symlink", "usr/sbin", "/sbin",
            "--symlink", "usr/lib", "/lib",
            "--symlink", "usr/lib64", "/lib64",
            "--dev", "/dev",
            "--proc", "/proc",
            "--tmpfs", "/tmp",
            "--dir", "/tmp/runtime",
            "--tmpfs", "/home",
            "--dir", "/home/oompah",
            "--dir", "/home/oompah/.config",
            "--dir", "/home/oompah/.cache",
            "--dir", "/home/oompah/.local",
            "--dir", "/home/oompah/.local/share",
        ]
        created_dirs = {
            Path("/"), Path("/usr"), Path("/dev"), Path("/proc"), Path("/tmp"),
            Path("/tmp/runtime"), Path("/home"), Path("/home/oompah"),
            Path("/home/oompah/.config"), Path("/home/oompah/.cache"),
            Path("/home/oompah/.local"), Path("/home/oompah/.local/share"),
        }

        def add_destination(path: Path) -> None:
            current = Path("/")
            for part in path.parts[1:]:
                current /= part
                if current not in created_dirs:
                    args.extend(["--dir", str(current)])
                    created_dirs.add(current)

        # The checkout is writable.  Its .git entry is a text file pointing
        # at ``git_dir``; mount the shared common database read-only, restore
        # writable worktree metadata, then selectively restore only the
        # common object/ref paths required for a local rebase or commit.
        add_destination(workspace)
        args.extend(["--bind", str(workspace), str(workspace)])
        add_destination(common_dir)
        args.extend(["--ro-bind", str(common_dir), str(common_dir)])
        add_destination(git_dir)
        args.extend(["--bind", str(git_dir), str(git_dir)])
        for name in ("objects", "refs", "logs"):
            source = common_dir / name
            if not source.exists():
                continue
            source = _real_directory(source, label=f"common Git {name}")
            add_destination(source)
            args.extend(["--bind", str(source), str(source)])
        packed_refs = common_dir / "packed-refs"
        if packed_refs.exists():
            if packed_refs.is_symlink() or not packed_refs.is_file():
                raise RebaseWorkerSandboxUnavailable("common Git packed-refs is unsafe")
            add_destination(packed_refs.parent)
            args.extend(["--bind", str(packed_refs), str(packed_refs)])
        for source, destination in config_overlays:
            add_destination(destination.parent)
            args.extend(["--ro-bind", str(source), str(destination)])
        for key, value in _sandbox_environment(environment).items():
            args.extend(["--setenv", key, value])
        args.extend(["--chdir", str(workspace), "/bin/bash", "-lc", command])
        return RestrictedRebaseCommand(args, runtime_dir)
    except Exception:
        shutil.rmtree(runtime_dir, ignore_errors=True)
        raise
