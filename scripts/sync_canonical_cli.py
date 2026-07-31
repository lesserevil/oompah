#!/usr/bin/env python3
"""Install the exact source revision into the canonical user CLI location.

This helper deliberately performs all validation before changing the canonical
launcher.  Each verified tool environment is published under a new immutable,
revision-addressed directory.  Activation is one atomic launcher replacement,
so concurrent invocations always see a complete old or new environment.
"""

from __future__ import annotations

import argparse
import fcntl
import functools
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import uuid
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, ParamSpec, TypeVar


DEFAULT_SOURCE_URL = "https://github.com/lesserevil/oompah"
_REVISION_RE = re.compile(r"revision\s+([0-9a-fA-F]{7,64})\b")
_PUBLISHED_ROOT_RE = re.compile(r"[0-9a-f]{7,64}-[0-9a-f]{32}")
DEFAULT_RETAINED_REVISION_ROOTS = 4
_LIFECYCLE_LOCK_NAME = ".oompah-cli-lifecycle.lock"

_P = ParamSpec("_P")
_R = TypeVar("_R")


class SyncError(RuntimeError):
    """Raised when canonical CLI synchronization cannot be completed safely."""


@dataclass
class _LifecycleLockState:
    """In-process half of the host-wide lifecycle serialization lock."""

    mutex: Any
    depth: int = 0
    fd: int | None = None


_LIFECYCLE_LOCK_STATES: dict[Path, _LifecycleLockState] = {}
_LIFECYCLE_LOCK_STATES_GUARD = threading.Lock()


def lifecycle_lock_path(canonical: Path) -> Path:
    """Return the stable host-scoped lock used by every CLI cutover path."""
    parent = canonical.expanduser().parent.resolve(strict=False)
    return parent / _LIFECYCLE_LOCK_NAME


def _lifecycle_lock_state(lock_path: Path) -> _LifecycleLockState:
    with _LIFECYCLE_LOCK_STATES_GUARD:
        state = _LIFECYCLE_LOCK_STATES.get(lock_path)
        if state is None:
            state = _LifecycleLockState(mutex=threading.RLock())
            _LIFECYCLE_LOCK_STATES[lock_path] = state
        return state


@contextmanager
def canonical_cli_lifecycle_lock(canonical: Path):
    """Serialize selection, activation, rollback, and pruning across the host.

    ``flock`` protects separate lifecycle processes.  The per-path ``RLock``
    both serializes threads in one process and makes nested helpers reentrant,
    avoiding a self-deadlock when a cutover calls another protected helper.
    The persistent lock file is outside revision and rollback roots, so neither
    activation nor pruning can replace or delete it.
    """
    lock_path = lifecycle_lock_path(canonical)
    state = _lifecycle_lock_state(lock_path)
    state.mutex.acquire()
    try:
        if state.depth == 0:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            flags = os.O_CREAT | os.O_RDWR
            flags |= getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            fd: int | None = None
            try:
                fd = os.open(lock_path, flags, 0o600)
                metadata = os.fstat(fd)
                if not stat.S_ISREG(metadata.st_mode):
                    raise OSError("lifecycle lock is not a regular file")
                os.fchmod(fd, 0o600)
                fcntl.flock(fd, fcntl.LOCK_EX)
            except OSError as exc:
                if fd is not None:
                    os.close(fd)
                raise SyncError(
                    f"cannot acquire canonical CLI lifecycle lock {lock_path}: {exc}"
                ) from exc
            state.fd = fd
        state.depth += 1
        try:
            yield lock_path
        finally:
            state.depth -= 1
            if state.depth == 0:
                fd = state.fd
                state.fd = None
                if fd is not None:
                    try:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                    finally:
                        os.close(fd)
    finally:
        state.mutex.release()


def serialized_cli_lifecycle(
    *, error_type: type[Exception] = SyncError
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Decorate a keyword-only lifecycle entry point with the shared lock."""

    def decorate(function: Callable[_P, _R]) -> Callable[_P, _R]:
        @functools.wraps(function)
        def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            canonical = kwargs.get("canonical")
            if canonical is None:
                raise TypeError("serialized lifecycle call requires canonical=")
            try:
                with canonical_cli_lifecycle_lock(Path(canonical)):
                    return function(*args, **kwargs)
            except SyncError as exc:
                if error_type is SyncError:
                    raise
                raise error_type(str(exc)) from exc

        return wrapped

    return decorate


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
    backup_root: Path
    launcher_backup: Path | None
    published_tool: Path
    revisions_dir: Path
    _closed: bool = False

    def _prune(self) -> None:
        """Best-effort cleanup which can never invalidate the live pair."""
        try:
            prune_revision_roots(
                self.revisions_dir,
                canonical=self.canonical,
                backup_launchers=(self.launcher_backup,)
                if self.launcher_backup
                else (),
            )
        except OSError as exc:
            # Cleanup failure is operationally useful to report, but it must
            # not turn an already-safe activation/rollback into a failed
            # lifecycle transaction.
            print(
                f"WARNING: could not prune obsolete canonical CLI roots: {exc}",
                file=sys.stderr,
            )

    def rollback(self) -> None:
        """Atomically restore the launcher from before activation.

        Published tool roots are immutable and deliberately retained.  A CLI
        process that crossed the activation point may still be using either
        root, so deleting one here would reintroduce the invocation race this
        journal exists to prevent.
        """
        if self._closed:
            return
        _restore_launcher_atomically(self.canonical, self.launcher_backup)
        self._prune()
        shutil.rmtree(self.backup_root, ignore_errors=True)
        self._closed = True

    def commit(self) -> None:
        """Discard rollback material after the new service is healthy."""
        if self._closed:
            return
        self._prune()
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


def _operator_path(environ: dict[str, str], operator_path: str | None) -> str:
    """Return the caller's PATH used for canonical CLI validation.

    Lifecycle recipes intentionally prepend their virtualenv to the process
    PATH so internal Python and UV commands are available.  That path is not
    the operator's command-resolution contract, however: a local virtualenv
    launcher must not hide the canonical user launcher.  Direct Python callers
    retain the historical behavior by falling back to their supplied PATH.
    """
    return environ.get("PATH", "") if operator_path is None else operator_path


def _snapshot_launcher(path: Path, root: Path) -> Path | None:
    """Copy the exact canonical launcher into a rollback directory."""
    if not os.path.lexists(path):
        return None
    root.mkdir(parents=True, exist_ok=True)
    backup = root / path.name
    if path.is_symlink():
        backup.symlink_to(os.readlink(path))
    else:
        shutil.copy2(path, backup)
    return backup


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def _published_revision_roots(revisions_dir: Path) -> list[Path]:
    """Return complete immutable roots, excluding in-progress publications."""
    if not revisions_dir.is_dir():
        return []
    roots = [
        path
        for path in revisions_dir.iterdir()
        if path.is_dir()
        and not path.is_symlink()
        and _PUBLISHED_ROOT_RE.fullmatch(path.name)
    ]
    return sorted(
        roots,
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )


def _launcher_references(
    launcher: Path,
    roots: Iterable[Path],
) -> set[Path]:
    """Find immutable roots referenced by a live or rollback launcher."""
    if not os.path.lexists(launcher):
        return set()
    chunks: list[bytes] = []
    try:
        if launcher.is_symlink():
            target = os.readlink(launcher)
            chunks.append(target.encode(errors="surrogateescape"))
            resolved = (launcher.parent / target).resolve()
            chunks.append(str(resolved).encode())
        elif launcher.is_file():
            chunks.append(launcher.read_bytes())
    except OSError:
        # A concurrent launcher replacement is safe: the replacement itself
        # is examined by the caller on the next deployment.  Conservatively
        # skip pruning whenever any live/rollback launcher cannot be read.
        return set(roots)
    payload = b"\0".join(chunks)
    return {root for root in roots if str(root).encode() in payload}


def _active_revision_roots(
    roots: Iterable[Path],
    *,
    proc_root: Path = Path("/proc"),
) -> set[Path]:
    """Return roots referenced by currently running processes.

    After launcher activation, no new normal invocation can enter an old
    root.  Scanning ``exe``, ``cwd``, and ``cmdline`` protects invocations
    that crossed the launcher before activation and are still using it.
    Permission races and processes exiting during the scan are ignored.
    """
    candidates = list(roots)
    if not candidates or not proc_root.is_dir():
        return set()
    encoded = {root: str(root).encode() for root in candidates}
    active: set[Path] = set()
    for process_dir in proc_root.iterdir():
        if not process_dir.name.isdigit():
            continue
        chunks: list[bytes] = []
        for link_name in ("exe", "cwd"):
            try:
                chunks.append(os.readlink(process_dir / link_name).encode())
            except OSError:
                pass
        try:
            chunks.append((process_dir / "cmdline").read_bytes())
        except OSError:
            pass
        payload = b"\0".join(chunks)
        for root, marker in encoded.items():
            if marker in payload:
                active.add(root)
        if len(active) == len(candidates):
            break
    return active


def prune_revision_roots(
    revisions_dir: Path,
    *,
    canonical: Path,
    backup_launchers: Iterable[Path] = (),
    max_roots: int = DEFAULT_RETAINED_REVISION_ROOTS,
    proc_root: Path = Path("/proc"),
) -> list[Path]:
    """Remove obsolete immutable roots without racing live invocations.

    The newest ``max_roots`` are retained as a recovery window.  Older roots
    are removed only when no canonical/rollback launcher and no active process
    references them.  Rollback launchers left by an interrupted activation are
    discovered as well as those explicitly supplied by the current journal.
    """
    roots = _published_revision_roots(revisions_dir)
    if len(roots) <= max(max_roots, 0):
        return []

    launchers = [canonical, *backup_launchers]
    launchers.extend(
        path
        for backup_root in canonical.parent.glob(".oompah-cli-activation-*")
        for path in backup_root.glob(f"launcher/{canonical.name}")
    )
    protected: set[Path] = set(roots[: max(max_roots, 0)])
    for launcher in launchers:
        protected.update(_launcher_references(launcher, roots))
    protected.update(_active_revision_roots(roots, proc_root=proc_root))

    removed: list[Path] = []
    for root in roots:
        if root in protected:
            continue
        _remove_path(root)
        removed.append(root)
    return removed


def _restore_launcher_atomically(path: Path, backup: Path | None) -> None:
    """Restore *backup* with one same-directory launcher replacement."""
    if backup is None:
        _remove_path(path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    replacement = path.parent / f".{path.name}.rollback-{uuid.uuid4().hex}"
    if backup.is_symlink():
        replacement.symlink_to(os.readlink(backup))
    else:
        shutil.copy2(backup, replacement)
    try:
        os.replace(replacement, path)
    finally:
        _remove_path(replacement)


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
    operator_path: str | None = None,
) -> StagedCLI:
    """Build and verify a CLI in an isolated tree without touching the live CLI.

    The staged launcher is verified with the exact same PATH check used for
    activation.  Keeping both UV directories below ``stage_dir`` means a
    failed download, build, or version check cannot alter the known-good
    canonical launcher or its tool environment.
    """
    env = dict(os.environ if environ is None else environ)
    validation_path = _operator_path(env, operator_path)
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
    path = os.pathsep.join(part for part in (str(bin_dir), validation_path) if part)
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


def _relocate_launcher(
    launcher: Path,
    old_tool: Path,
    new_tool: Path,
    *,
    destination_dir: Path,
) -> Path:
    """Make a staged UV launcher refer to its immutable published tool root.

    UV launchers normally contain an absolute interpreter path.  Staging in a
    temporary UV root is therefore not enough by itself: copy the launcher to
    the canonical launcher's filesystem and rewrite the staged tool path before
    activation.
    """
    data = launcher.read_bytes()
    old = str(old_tool).encode()
    new = str(new_tool).encode()
    if old in data:
        data = data.replace(old, new)
    relocated = destination_dir / f".oompah-candidate-{uuid.uuid4().hex}"
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
    operator_path: str | None = None,
) -> Activation:
    """Atomically publish a staged CLI and return a rollback journal.

    The old launcher and its tool root remain untouched while the candidate is
    copied to a new revision-addressed root.  Only one ``os.replace`` of the
    launcher activates the candidate.  Callers must retain the returned journal
    until the paired server cutover has passed its health/build-id check.
    """
    env = dict(os.environ if environ is None else environ)
    validation_path = _operator_path(env, operator_path)
    canonical = canonical.expanduser()
    tool_dir = tool_dir.expanduser()
    bin_dir = bin_dir.expanduser()
    canonical.parent.mkdir(parents=True, exist_ok=True)
    backup_root = Path(
        tempfile.mkdtemp(prefix=".oompah-cli-activation-", dir=canonical.parent)
    )
    launcher_backup = _snapshot_launcher(canonical, backup_root / "launcher")
    revisions_dir = tool_dir / ".oompah-revisions"
    published_tool = revisions_dir / f"{staged.revision.lower()}-{uuid.uuid4().hex}"
    candidate_tool = revisions_dir / f".{published_tool.name}.publishing"
    candidate_launcher = None
    activation = Activation(
        canonical=canonical,
        backup_root=backup_root,
        launcher_backup=launcher_backup,
        published_tool=published_tool,
        revisions_dir=revisions_dir,
    )
    try:
        tool_dir.mkdir(parents=True, exist_ok=True)
        revisions_dir.mkdir(parents=True, exist_ok=True)
        bin_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staged.tool, candidate_tool, symlinks=True)
        # Publication cannot affect the live launcher.  The path is unique and
        # never mutated after this rename, so old and new processes can safely
        # overlap for any duration.
        os.replace(candidate_tool, published_tool)
        candidate_launcher = _relocate_launcher(
            staged.launcher,
            staged.tool,
            published_tool,
            destination_dir=canonical.parent,
        )
        # This is the only activation point visible to concurrent invocations.
        os.replace(candidate_launcher, canonical)
        candidate_launcher = None
        # Verify the operator's real PATH, not a synthetic path that happens
        # to include the destination.  This catches a project virtualenv or
        # another stale executable winning command resolution.
        _verify(canonical, staged.revision, path=validation_path, environ=env)
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


@serialized_cli_lifecycle()
def synchronize(
    *,
    repo: Path,
    canonical: Path,
    source_url: str = DEFAULT_SOURCE_URL,
    uv: str = "uv",
    tool_dir: Path | None = None,
    bin_dir: Path | None = None,
    environ: dict[str, str] | None = None,
    operator_path: str | None = None,
) -> bool:
    """Synchronize the canonical CLI and return whether an install occurred."""
    env = dict(os.environ if environ is None else environ)
    validation_path = _operator_path(env, operator_path)
    home = Path(env.get("HOME", str(Path.home())))
    tool_dir = tool_dir or Path(env.get("UV_TOOL_DIR", home / ".local/share/uv/tools"))
    bin_dir = bin_dir or Path(env.get("UV_TOOL_BIN_DIR", canonical.parent))
    canonical = canonical.expanduser()
    revision = selected_revision(repo)

    # Validate PATH even for a no-op. A stale local virtualenv must never win
    # command resolution after deployment.
    if os.path.lexists(canonical) and not _command_resolves_to(
        canonical, path=validation_path
    ):
        actual = shutil.which("oompah", path=validation_path) or "not found"
        raise SyncError(
            f"refusing CLI synchronization: command -v oompah resolves to {actual!r}; "
            f"expected {str(canonical)!r}"
        )
    if os.path.lexists(canonical) and _command_resolves_to(
        canonical, path=validation_path
    ):
        current = _run(
            [str(canonical), "--version"],
            env={**env, "PATH": validation_path},
        )
        if (
            current.returncode == 0
            and _version_revision(current.stdout + current.stderr) == revision.lower()
        ):
            try:
                prune_revision_roots(
                    tool_dir / ".oompah-revisions",
                    canonical=canonical,
                )
            except OSError as exc:
                print(
                    f"WARNING: could not prune obsolete canonical CLI roots: {exc}",
                    file=sys.stderr,
                )
            print(f"Canonical oompah already matches revision {revision}.")
            return False

    staged = stage_candidate(
        repo=repo,
        source_url=source_url,
        uv=uv,
        environ=env,
        operator_path=operator_path,
    )
    try:
        activation = activate_candidate(
            staged,
            canonical=canonical,
            tool_dir=tool_dir,
            bin_dir=bin_dir,
            environ=env,
            operator_path=operator_path,
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
    parser.add_argument(
        "--operator-path",
        help="PATH from the operator shell for canonical CLI validation",
    )
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
            operator_path=args.operator_path,
        )
    except SyncError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
