#!/usr/bin/env python3
"""Install the exact source revision into the canonical user CLI location.

This helper deliberately performs all validation before changing the UV tool
installation.  If UV fails or the installed command reports an unexpected
revision, the previous launcher and tool environment are restored.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


DEFAULT_SOURCE_URL = "https://github.com/lesserevil/oompah"
_REVISION_RE = re.compile(r"revision\s+([0-9a-fA-F]{7,64})\b")


class SyncError(RuntimeError):
    """Raised when canonical CLI synchronization cannot be completed safely."""


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _git(repo: Path, *args: str) -> str:
    result = _run(["git", *args], cwd=repo)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise SyncError(f"git {' '.join(args)} failed: {detail or 'unknown error'}")
    return result.stdout.strip()


def selected_revision(repo: Path) -> str:
    """Validate that the server source is clean and fully pushed."""
    status = _git(repo, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise SyncError(
            "refusing CLI synchronization: server checkout is dirty; "
            "commit or remove all changes first"
        )

    head = _git(repo, "rev-parse", "HEAD")
    try:
        upstream = _git(repo, "rev-parse", "@{upstream}")
    except SyncError as exc:
        raise SyncError(
            "refusing CLI synchronization: server checkout has no upstream; "
            "push the selected revision and configure its upstream first"
        ) from exc
    if head != upstream:
        raise SyncError(
            "refusing CLI synchronization: server checkout is not exactly "
            "at its pushed upstream revision (push or rebase before deploying)"
        )
    return head


def _version_revision(output: str) -> str | None:
    match = _REVISION_RE.search(output)
    return match.group(1).lower() if match else None


def _command_resolves_to(canonical: Path, *, path: str | None = None) -> bool:
    """Check the literal command path, not just the target of a symlink."""
    resolved = shutil.which("oompah", path=path)
    return resolved is not None and os.path.abspath(resolved) == os.path.abspath(canonical)


def _snapshot(path: Path, root: Path) -> Path | None:
    """Copy one exact file, symlink, or directory into a rollback directory."""
    if not os.path.lexists(path):
        return None
    root.mkdir(parents=True, exist_ok=True)
    backup = root / path.name
    if path.is_symlink():
        backup.symlink_to(os.readlink(path))
    elif path.is_dir():
        shutil.copytree(path, backup, symlinks=True)
    else:
        shutil.copy2(path, backup)
    return backup


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def _restore(path: Path, backup: Path | None) -> None:
    _remove_path(path)
    if backup is None:
        return
    if backup.is_symlink():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(os.readlink(backup))
    elif backup.is_dir():
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(backup, path, symlinks=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, path)


def _verify(canonical: Path, revision: str, *, path: str) -> None:
    if not _command_resolves_to(canonical, path=path):
        actual = shutil.which("oompah", path=path) or "not found"
        raise SyncError(
            f"canonical CLI was installed but command -v oompah resolves to {actual!r}; "
            f"expected {str(canonical)!r}"
        )
    result = _run([str(canonical), "--version"], env={**os.environ, "PATH": path})
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise SyncError(f"canonical oompah --version failed: {detail or 'unknown error'}")
    actual_revision = _version_revision(result.stdout + result.stderr)
    if actual_revision != revision.lower():
        raise SyncError(
            "canonical CLI revision mismatch: "
            f"server={revision}, cli={actual_revision or 'unknown'}"
        )


def synchronize(
    *,
    repo: Path,
    canonical: Path,
    source_url: str = DEFAULT_SOURCE_URL,
    uv: str = "uv",
    tool_dir: Path | None = None,
    bin_dir: Path | None = None,
    environ: dict[str, str] | None = None,
) -> bool:
    """Synchronize the canonical CLI and return whether an install occurred."""
    env = dict(os.environ if environ is None else environ)
    home = Path(env.get("HOME", str(Path.home())))
    tool_dir = tool_dir or Path(env.get("UV_TOOL_DIR", home / ".local/share/uv/tools"))
    bin_dir = bin_dir or Path(env.get("UV_TOOL_BIN_DIR", canonical.parent))
    canonical = canonical.expanduser()
    tool_path = tool_dir / "oompah"
    revision = selected_revision(repo)
    path = env.get("PATH", "")

    # Validate PATH even for a no-op. A stale local virtualenv must never win
    # command resolution after deployment.
    if os.path.lexists(canonical) and _command_resolves_to(canonical, path=env.get("PATH")):
        current = _run([str(canonical), "--version"], env=env)
        if current.returncode == 0 and _version_revision(current.stdout + current.stderr) == revision.lower():
            print(f"Canonical oompah already matches revision {revision}.")
            return False

    canonical.parent.mkdir(parents=True, exist_ok=True)
    tool_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="oompah-cli-rollback-") as temp_name:
        rollback = Path(temp_name)
        launcher_backup = _snapshot(canonical, rollback / "launcher")
        tool_backup = _snapshot(tool_path, rollback / "tool")
        install_env = {
            **env,
            "UV_TOOL_DIR": str(tool_dir),
            "UV_TOOL_BIN_DIR": str(bin_dir),
        }
        source = f"git+{source_url}@{revision}"
        command = [uv, "tool", "install", "--force", "--from", source, "oompah"]
        result = _run(command, cwd=repo, env=install_env)
        if result.returncode != 0:
            _restore(canonical, launcher_backup)
            _restore(tool_path, tool_backup)
            detail = (result.stderr or result.stdout).strip()
            preserved = (
                "the previous executable was preserved"
                if launcher_backup is not None or tool_backup is not None
                else "no previous executable existed to preserve"
            )
            raise SyncError(
                f"canonical CLI installation failed; {preserved}. "
                "Retry after fixing UV/source access: "
                f"{detail or 'unknown error'}"
            )
        try:
            _verify(canonical, revision, path=path)
        except SyncError as exc:
            _restore(canonical, launcher_backup)
            _restore(tool_path, tool_backup)
            raise SyncError(
                f"{exc}; the previous executable was preserved. "
                "Fix the revision or PATH and retry."
            ) from exc

    print(f"Canonical oompah synchronized to revision {revision} at {canonical}.")
    return True


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--uv", default="uv")
    parser.add_argument("--tool-dir", type=Path)
    parser.add_argument("--bin-dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        synchronize(
            repo=args.repo,
            canonical=args.canonical,
            source_url=args.source_url,
            uv=args.uv,
            tool_dir=args.tool_dir,
            bin_dir=args.bin_dir,
        )
    except SyncError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
