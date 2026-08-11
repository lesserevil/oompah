"""Protect the service virtualenv from linked task worktrees.

Managed workers normally receive a checkout-private ``OOMPAH_TASK_VENV``.
This module is the last mutation boundary: it resolves Git's primary
worktree, rejects aliases of that worktree's live ``.venv``, and serializes
editable-install inspection and repair across every linked worktree.

The command-line entry point intentionally uses only the standard library so
``make setup`` can invoke it before the requested virtualenv exists.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import os
from pathlib import Path
import subprocess
import sys
from typing import Iterator, Sequence


class VenvSafetyError(RuntimeError):
    """Raised before a task checkout can mutate a shared service runtime."""


@dataclass(frozen=True, slots=True)
class WorktreeVenvContext:
    """Resolved checkout and virtualenv authority for one setup command."""

    checkout: Path
    git_common_dir: Path | None
    git_primary_checkout: Path
    service_checkout: Path
    requested_venv: Path
    service_venv: Path
    protected_service_venvs: tuple[Path, ...]

    @property
    def is_service_checkout(self) -> bool:
        return _same_path(
            self.checkout,
            self.git_primary_checkout,
        ) and _same_path(self.checkout, self.service_checkout)


def _same_path(left: Path, right: Path) -> bool:
    """Compare path aliases by resolution and, when available, inode."""

    resolved_left = left.resolve(strict=False)
    resolved_right = right.resolve(strict=False)
    if resolved_left == resolved_right:
        return True
    try:
        return os.path.samefile(resolved_left, resolved_right)
    except OSError:
        return False


def _worktree_git_common_dir(checkout: Path) -> Path | None:
    """Return Git's shared metadata directory without executing candidate Git."""

    dot_git = checkout / ".git"
    if dot_git.is_dir():
        return dot_git.resolve()
    if not dot_git.is_file():
        return None
    try:
        marker = dot_git.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise VenvSafetyError(f"cannot read linked-worktree metadata: {exc}") from exc
    prefix = "gitdir:"
    if not marker.lower().startswith(prefix):
        raise VenvSafetyError("linked-worktree .git metadata is malformed")
    git_dir = Path(marker[len(prefix) :].strip())
    if not git_dir.is_absolute():
        git_dir = dot_git.parent / git_dir
    git_dir = git_dir.resolve(strict=False)
    common_marker = git_dir / "commondir"
    try:
        common_value = common_marker.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise VenvSafetyError(
            f"cannot resolve linked-worktree common metadata: {exc}"
        ) from exc
    if not common_value:
        raise VenvSafetyError("linked-worktree common metadata is empty")
    common_dir = Path(common_value)
    if not common_dir.is_absolute():
        common_dir = git_dir / common_dir
    return common_dir.resolve(strict=False)


def resolve_worktree_venv_context(
    checkout: str | os.PathLike[str],
    requested_venv: str | os.PathLike[str],
    *,
    service_checkout: str | os.PathLike[str] | None = None,
    service_venv: str | os.PathLike[str] | None = None,
) -> WorktreeVenvContext:
    """Resolve the primary checkout and requested runtime, including aliases."""

    checkout_path = Path(checkout).resolve(strict=False)
    common_dir = _worktree_git_common_dir(checkout_path)
    derived_service_checkout = checkout_path
    if common_dir is not None:
        if common_dir.name != ".git":
            raise VenvSafetyError(
                f"Git common metadata {common_dir} does not identify a primary checkout"
            )
        derived_service_checkout = common_dir.parent.resolve(strict=False)
    explicit_service_checkout = (
        Path(service_checkout).expanduser().resolve(strict=False)
        if str(service_checkout or "").strip()
        else None
    )
    is_linked_worktree = not _same_path(checkout_path, derived_service_checkout)
    if (
        is_linked_worktree
        and explicit_service_checkout is not None
        and not _same_path(explicit_service_checkout, derived_service_checkout)
    ):
        raise VenvSafetyError(
            "service checkout marker conflicts with Git-derived primary checkout: "
            f"marker={explicit_service_checkout}, primary={derived_service_checkout}"
        )
    service_checkout_path = explicit_service_checkout or derived_service_checkout
    service_venv_path = (
        Path(service_venv).expanduser().resolve(strict=False)
        if str(service_venv or "").strip()
        else service_checkout_path / ".venv"
    )
    protected_service_venvs = [service_venv_path]
    conventional_service_venv = service_checkout_path / ".venv"
    if not any(
        _same_path(conventional_service_venv, protected)
        for protected in protected_service_venvs
    ):
        # The explicit marker may name a non-conventional operator runtime,
        # but it is additive authority: it cannot erase the conventional
        # runtime belonging to the separately identified service checkout.
        # This matters for task workspaces in unrelated repositories, where
        # Git has no shared common directory from which to rediscover it.
        protected_service_venvs.append(conventional_service_venv)
    derived_service_venv = derived_service_checkout / ".venv"
    if is_linked_worktree and not any(
        _same_path(derived_service_venv, protected)
        for protected in protected_service_venvs
    ):
        # An explicit service-venv marker can protect a non-conventional
        # operator runtime, but it cannot erase the conventional runtime
        # belonging to this linked worktree's Git primary checkout.
        protected_service_venvs.append(derived_service_venv)
    requested_path = Path(requested_venv).expanduser()
    if not requested_path.is_absolute():
        requested_path = checkout_path / requested_path
    requested_path = requested_path.absolute()
    return WorktreeVenvContext(
        checkout=checkout_path,
        git_common_dir=common_dir,
        git_primary_checkout=derived_service_checkout,
        service_checkout=service_checkout_path,
        requested_venv=requested_path,
        service_venv=service_venv_path,
        protected_service_venvs=tuple(protected_service_venvs),
    )


def validate_worktree_venv_target(context: WorktreeVenvContext) -> None:
    """Fail before mutation when a task worktree targets the service venv."""

    if context.is_service_checkout:
        return
    for protected in context.protected_service_venvs:
        if _same_path(context.requested_venv, protected):
            raise VenvSafetyError(
                "task worktree virtualenv resolves to the live service virtualenv "
                f"{protected}; use {context.checkout / '.oompah' / 'task-venv'}"
            )


def _setup_lock_path(context: WorktreeVenvContext) -> Path | None:
    if context.git_common_dir is None:
        return None
    return context.git_common_dir / "oompah-venv-setup.lock"


@contextmanager
def worktree_venv_lock(
    checkout: str | os.PathLike[str],
    *,
    exclusive: bool,
) -> Iterator[None]:
    """Serialize service-runtime inspection and setup across linked worktrees."""

    checkout_path = Path(checkout).resolve(strict=False)
    common_dir = _worktree_git_common_dir(checkout_path)
    if common_dir is None:
        yield
        return
    context = WorktreeVenvContext(
        checkout=checkout_path,
        git_common_dir=common_dir,
        git_primary_checkout=common_dir.parent.resolve(strict=False),
        service_checkout=common_dir.parent.resolve(strict=False),
        requested_venv=checkout_path / ".venv",
        service_venv=common_dir.parent.resolve(strict=False) / ".venv",
        protected_service_venvs=(
            common_dir.parent.resolve(strict=False) / ".venv",
        ),
    )
    lock_path = _setup_lock_path(context)
    assert lock_path is not None
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(
            descriptor,
            fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH,
        )
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=cwd,
        text=True,
        capture_output=capture_output,
        check=False,
    )


def _interpreter_prefix(interpreter: Path, checkout: Path) -> Path | None:
    result = _run(
        [str(interpreter), "-I", "-c", "import sys; print(sys.prefix)"],
        cwd=checkout,
        capture_output=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return Path(result.stdout.strip()).resolve(strict=False)


def _editable_checkout(interpreter: Path, venv: Path) -> Path | None:
    probe = (
        "import importlib.util, pathlib; "
        "spec = importlib.util.find_spec('oompah'); "
        "print(pathlib.Path(spec.origin).resolve().parent.parent "
        "if spec and spec.origin else '')"
    )
    result = _run(
        [str(interpreter), "-I", "-c", probe],
        cwd=venv,
        capture_output=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return Path(result.stdout.strip()).resolve(strict=False)


def _validate_real_venv(context: WorktreeVenvContext) -> Path:
    requested = context.requested_venv
    if requested.is_symlink() or not (requested / "pyvenv.cfg").is_file():
        raise VenvSafetyError(
            f"{requested} is not a real task-private virtualenv; "
            "refusing to run uv against a wrapper or alias"
        )
    interpreter = requested / "bin" / "python"
    prefix = _interpreter_prefix(interpreter, context.checkout)
    if prefix is None or not _same_path(prefix, requested):
        raise VenvSafetyError(
            f"{requested} interpreter resolves to {prefix or 'unavailable'}, "
            f"not the requested runtime {requested}; refusing to run uv"
        )
    if not context.is_service_checkout:
        for protected in context.protected_service_venvs:
            if _same_path(prefix, protected):
                raise VenvSafetyError(
                    "task worktree interpreter resolves to the live service "
                    "virtualenv; "
                    f"use {context.checkout / '.oompah' / 'task-venv'}"
                )
    return interpreter


def ensure_worktree_venv(
    *,
    checkout: str | os.PathLike[str],
    requested_venv: str | os.PathLike[str],
    uv: str,
    extra: str,
    service_checkout: str | os.PathLike[str] | None = None,
    service_venv: str | os.PathLike[str] | None = None,
) -> None:
    """Provision and verify one editable checkout under the shared setup lock."""

    if extra not in {"server", "dev"}:
        raise ValueError("extra must be 'server' or 'dev'")
    context = resolve_worktree_venv_context(
        checkout,
        requested_venv,
        service_checkout=service_checkout,
        service_venv=service_venv,
    )
    with worktree_venv_lock(context.checkout, exclusive=True):
        # Resolve again after lock acquisition so an alias changed by a
        # concurrent worktree cannot pass a stale pre-lock observation.
        context = resolve_worktree_venv_context(
            checkout,
            requested_venv,
            service_checkout=service_checkout,
            service_venv=service_venv,
        )
        validate_worktree_venv_target(context)
        if not context.requested_venv.exists():
            created = _run(
                [uv, "venv", str(context.requested_venv)],
                cwd=context.checkout,
            )
            if created.returncode != 0:
                raise VenvSafetyError(
                    f"failed to create task-private virtualenv {context.requested_venv}"
                )
        # A path can be replaced between creation and validation by another
        # process; repeat both the alias and interpreter checks before uv pip.
        validate_worktree_venv_target(context)
        interpreter = _validate_real_venv(context)
        stamp = context.requested_venv / (
            ".uv-setup" if extra == "server" else ".uv-test-setup"
        )
        project_file = context.checkout / "pyproject.toml"
        stamp_current = bool(
            stamp.is_file()
            and project_file.is_file()
            and stamp.stat().st_mtime_ns >= project_file.stat().st_mtime_ns
        )
        actual_checkout = _editable_checkout(interpreter, context.requested_venv)
        needs_install = not stamp_current or actual_checkout is None or not _same_path(
            actual_checkout, context.checkout
        )
        if needs_install:
            if actual_checkout is not None and not _same_path(
                actual_checkout, context.checkout
            ):
                print(
                    "Refreshing editable oompah install for "
                    f"{context.checkout} (was {actual_checkout})."
                )
            installed = _run(
                [
                    uv,
                    "pip",
                    "install",
                    "--python",
                    str(interpreter),
                    "-e",
                    f".[{extra}]",
                ],
                cwd=context.checkout,
            )
            if installed.returncode != 0:
                raise VenvSafetyError(
                    f"failed to refresh editable oompah install for {context.checkout}"
                )
            actual_checkout = _editable_checkout(interpreter, context.requested_venv)
            if actual_checkout is None or not _same_path(
                actual_checkout, context.checkout
            ):
                raise VenvSafetyError(
                    "editable oompah install resolves to "
                    f"{actual_checkout or 'unavailable'}, not the invoking checkout "
                    f"{context.checkout}"
                )
            stamp.touch()
            print(
                "Setup complete. Run 'make start' to launch oompah."
                if extra == "server"
                else "Test dependencies installed."
            )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    ensure = subparsers.add_parser("ensure")
    ensure.add_argument("--checkout", required=True)
    ensure.add_argument("--venv", required=True)
    ensure.add_argument("--uv", default="uv")
    ensure.add_argument("--extra", choices=("server", "dev"), required=True)
    ensure.add_argument("--service-checkout")
    ensure.add_argument("--service-venv")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        ensure_worktree_venv(
            checkout=args.checkout,
            requested_venv=args.venv,
            uv=args.uv,
            extra=args.extra,
            service_checkout=args.service_checkout,
            service_venv=args.service_venv,
        )
    except (OSError, VenvSafetyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
