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
import uuid
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SOURCE_URL = "https://github.com/lesserevil/oompah"
_REVISION_RE = re.compile(r"revision\s+([0-9a-fA-F]{7,64})\b")


class SyncError(RuntimeError):
    """Raised when canonical CLI synchronization cannot be completed safely."""


@dataclass
class StagedCLI:
    """A verified CLI install which has not changed the canonical launcher."""

    root: Path
    tool_dir: Path
    bin_dir: Path
    launcher: Path
    tool: Path
    revision: str

    def cleanup(self) -> None:
        """Remove the isolated staging tree."""
        shutil.rmtree(self.root, ignore_errors=True)


@dataclass
class Activation:
    """Rollback journal for an activated canonical CLI."""

    canonical: Path
    tool_path: Path
    backup_root: Path
    launcher_backup: Path | None
    tool_backup: Path | None
    _closed: bool = False

    def rollback(self) -> None:
        """Restore the exact launcher and UV environment from before activation."""
        if self._closed:
            return
        _restore(self.canonical, self.launcher_backup)
        _restore(self.tool_path, self.tool_backup)
        shutil.rmtree(self.backup_root, ignore_errors=True)
        self._closed = True

    def commit(self) -> None:
        """Discard rollback material after the new service is healthy."""
        if self._closed:
            return
        shutil.rmtree(self.backup_root, ignore_errors=True)
        self._closed = True


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


def _verify(
    canonical: Path,
    revision: str,
    *,
    path: str,
    environ: dict[str, str] | None = None,
) -> None:
    if not _command_resolves_to(canonical, path=path):
        actual = shutil.which("oompah", path=path) or "not found"
        raise SyncError(
            f"canonical CLI was installed but command -v oompah resolves to {actual!r}; "
            f"expected {str(canonical)!r}"
        )
    result = _run(
        [str(canonical), "--version"],
        env={**(environ or os.environ), "PATH": path},
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise SyncError(f"canonical oompah --version failed: {detail or 'unknown error'}")
    actual_revision = _version_revision(result.stdout + result.stderr)
    if actual_revision != revision.lower():
        raise SyncError(
            "canonical CLI revision mismatch: "
            f"server={revision}, cli={actual_revision or 'unknown'}"
        )


def stage_candidate(
    *,
    repo: Path,
    source_url: str = DEFAULT_SOURCE_URL,
    uv: str = "uv",
    stage_dir: Path | None = None,
    environ: dict[str, str] | None = None,
) -> StagedCLI:
    """Build and verify a CLI in an isolated tree without touching the live CLI.

    The staged launcher is verified with the exact same PATH check used for
    activation.  Keeping both UV directories below ``stage_dir`` means a
    failed download, build, or version check cannot alter the known-good
    canonical launcher or its tool environment.
    """
    env = dict(os.environ if environ is None else environ)
    revision = selected_revision(repo)
    root = Path(stage_dir) if stage_dir is not None else Path(
        tempfile.mkdtemp(prefix="oompah-cli-stage-")
    )
    root.mkdir(parents=True, exist_ok=True)
    tool_dir = root / "tools"
    bin_dir = root / "bin"
    tool_dir.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    install_env = {
        **env,
        "UV_TOOL_DIR": str(tool_dir),
        "UV_TOOL_BIN_DIR": str(bin_dir),
    }
    source = f"git+{source_url}@{revision}"
    result = _run(
        [uv, "tool", "install", "--force", "--from", source, "oompah"],
        cwd=repo,
        env=install_env,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        shutil.rmtree(root, ignore_errors=True)
        raise SyncError(
            "canonical CLI staging failed; the previous executable was preserved. "
            "Retry after fixing UV/source access: "
            f"{detail or 'unknown error'}"
        )

    launcher = bin_dir / "oompah"
    tool = tool_dir / "oompah"
    path = os.pathsep.join(part for part in (str(bin_dir), env.get("PATH", "")) if part)
    try:
        _verify(launcher, revision, path=path, environ=env)
    except SyncError:
        shutil.rmtree(root, ignore_errors=True)
        raise
    return StagedCLI(
        root=root,
        tool_dir=tool_dir,
        bin_dir=bin_dir,
        launcher=launcher,
        tool=tool,
        revision=revision,
    )


def _relocate_launcher(launcher: Path, old_tool_dir: Path, new_tool_dir: Path) -> Path:
    """Make a staged UV launcher refer to its final tool directory.

    UV launchers normally contain an absolute interpreter path.  Staging in a
    temporary UV root is therefore not enough by itself: copy the launcher to
    a temporary destination and rewrite the staged root before activation.
    """
    data = launcher.read_bytes()
    old = str(old_tool_dir).encode()
    new = str(new_tool_dir).encode()
    if old in data:
        data = data.replace(old, new)
    relocated = launcher.parent / f".oompah-relocated-{uuid.uuid4().hex}"
    relocated.write_bytes(data)
    relocated.chmod(launcher.stat().st_mode & 0o777)
    return relocated


def activate_candidate(
    staged: StagedCLI,
    *,
    canonical: Path,
    tool_dir: Path,
    bin_dir: Path,
    environ: dict[str, str] | None = None,
) -> Activation:
    """Atomically publish a staged CLI and return a rollback journal.

    The old launcher remains in place while the candidate tool tree is copied
    and verified.  Only after that preparation succeeds is the launcher
    replaced.  Callers must retain the returned journal until the paired
    server cutover has passed its health/build-id check.
    """
    env = dict(os.environ if environ is None else environ)
    canonical = canonical.expanduser()
    tool_dir = tool_dir.expanduser()
    bin_dir = bin_dir.expanduser()
    tool_path = tool_dir / "oompah"
    backup_root = Path(tempfile.mkdtemp(prefix="oompah-cli-activation-"))
    launcher_backup = _snapshot(canonical, backup_root / "launcher")
    tool_backup = _snapshot(tool_path, backup_root / "tool")
    candidate_tool = tool_dir / f".oompah-candidate-{uuid.uuid4().hex}"
    candidate_launcher = None
    activation = Activation(
        canonical=canonical,
        tool_path=tool_path,
        backup_root=backup_root,
        launcher_backup=launcher_backup,
        tool_backup=tool_backup,
    )
    try:
        canonical.parent.mkdir(parents=True, exist_ok=True)
        tool_dir.mkdir(parents=True, exist_ok=True)
        bin_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staged.tool, candidate_tool, symlinks=True)
        candidate_launcher = _relocate_launcher(
            staged.launcher, staged.tool_dir, tool_dir
        )
        # The candidate tree is complete before the old tree is replaced.
        _remove_path(tool_path)
        os.replace(candidate_tool, tool_path)
        os.replace(candidate_launcher, canonical)
        candidate_launcher = None
        # Verify the operator's real PATH, not a synthetic path that happens
        # to include the destination.  This catches a project virtualenv or
        # another stale executable winning command resolution.
        _verify(canonical, staged.revision, path=env.get("PATH", ""), environ=env)
    except Exception as exc:
        if candidate_launcher is not None:
            _remove_path(candidate_launcher)
        _remove_path(candidate_tool)
        activation.rollback()
        if isinstance(exc, SyncError):
            raise SyncError(
                f"canonical CLI activation failed: {exc}; "
                "the previous executable was preserved"
            ) from exc
        raise SyncError(
            "canonical CLI activation failed; the previous executable was preserved: "
            f"{exc}"
        ) from exc
    return activation


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
    revision = selected_revision(repo)

    # Validate PATH even for a no-op. A stale local virtualenv must never win
    # command resolution after deployment.
    if os.path.lexists(canonical) and not _command_resolves_to(
        canonical, path=env.get("PATH")
    ):
        actual = shutil.which("oompah", path=env.get("PATH")) or "not found"
        raise SyncError(
            f"refusing CLI synchronization: command -v oompah resolves to {actual!r}; "
            f"expected {str(canonical)!r}"
        )
    if os.path.lexists(canonical) and _command_resolves_to(canonical, path=env.get("PATH")):
        current = _run([str(canonical), "--version"], env=env)
        if current.returncode == 0 and _version_revision(current.stdout + current.stderr) == revision.lower():
            print(f"Canonical oompah already matches revision {revision}.")
            return False

    staged = stage_candidate(
        repo=repo,
        source_url=source_url,
        uv=uv,
        environ=env,
    )
    try:
        activation = activate_candidate(
            staged,
            canonical=canonical,
            tool_dir=tool_dir,
            bin_dir=bin_dir,
            environ=env,
        )
        activation.commit()
    finally:
        staged.cleanup()

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
