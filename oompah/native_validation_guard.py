"""Command-scoped validation leases for native agent shell surfaces.

Native Codex sessions execute commands below the SDK-owned CLI process, so
the service cannot pass a lease descriptor directly to those grandchildren.
This module installs small PATH shims for known validation launchers.  A shim
classifies the *actual command invocation*, acquires capacity only for a heavy
invocation, attaches the durable record to its own exact process identity,
and then ``exec``s the real executable while retaining the flock descriptor.

The resulting kernel ownership is independent of the oompah service process:
if the service or Codex launcher crashes, a still-running validation command
continues to own its slot until it exits or its recorded deadline expires.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Mapping

from oompah.validation_resource_lease import (
    ValidationLeaseOwner,
    ValidationResourceLease,
    is_heavyweight_validation_command,
)


_CONFIG_NAME = "validation-guard.json"
_GUARD_ENV = "OOMPAH_NATIVE_VALIDATION_GUARD"
_WRAPPED_COMMANDS = frozenset(
    {
        "bash",
        "cargo",
        "dash",
        "make",
        "node",
        "nox",
        "npm",
        "pnpm",
        "py.test",
        "pytest",
        "perl",
        "ruby",
        "sh",
        "tox",
        "uv",
        "yarn",
        "zsh",
    }
)


def _python_command_names(search_path: str) -> set[str]:
    """Return interpreter names present on PATH that the classifier knows."""

    names = {"python", "python3"}
    for raw_directory in search_path.split(os.pathsep):
        directory = Path(raw_directory or ".")
        try:
            entries = tuple(directory.iterdir())
        except OSError:
            # PATH commonly retains optional package-manager directories that
            # are absent on a particular host (for example /snap/bin on a
            # GitHub runner).  Command discovery must tolerate those stale
            # entries just like shutil.which does.
            continue
        for entry in entries:
            name = entry.name
            suffix = name[6:] if name.startswith("python") else ""
            if suffix and suffix.replace(".", "").isdigit():
                names.add(name)
    return names


def install_native_validation_guard(
    environment: Mapping[str, str],
    *,
    runtime_root: str | os.PathLike[str],
    validation_lease: ValidationResourceLease,
    owner: ValidationLeaseOwner,
    timeout_seconds: float,
    provider_bootstrap_entrypoint: str | os.PathLike[str] | None = None,
    provider_bootstrap_interpreter: str | os.PathLike[str] | None = None,
    provider_bootstrap_entrypoint_identity: tuple[int, int] | None = None,
    provider_untrusted_roots: tuple[str | os.PathLike[str], ...] = (),
) -> tuple[dict[str, str], Path]:
    """Return an environment whose validation launchers are command guarded.

    Configuration is stored beside the shims in an operator-created directory
    rather than trusted from shell-set environment fields.  The sole marker in
    the environment names the guard directory; every shim derives the config
    path from its own invocation path and fails closed if it is unavailable.
    """

    guarded = dict(environment)
    original_path = str(guarded.get("PATH") or os.defpath)
    root = Path(runtime_root).resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    guard_bin = root / "validation-guard-bin"
    guard_bin.mkdir(mode=0o700, parents=True, exist_ok=False)

    config = {
        "state_path": str(validation_lease.state_path),
        "capacity": validation_lease.capacity,
        "aging_seconds": validation_lease.aging_seconds,
        "poll_seconds": validation_lease.poll_seconds,
        # The runtime clock begins only after the command owns capacity.  Guard
        # installation happens before model reasoning and must not consume it.
        "timeout_seconds": max(float(timeout_seconds), 1.0),
        "path": original_path,
        "shell": str(guarded.get("SHELL") or "/bin/sh"),
        "cancellation_path": str(root / "cancelled"),
        "owner": {
            "kind": owner.kind,
            "project_id": owner.project_id,
            "task_id": owner.task_id,
            "authority_generation": owner.authority_generation,
            "priority": owner.priority,
        },
    }
    if (provider_bootstrap_entrypoint is None) != (
        provider_bootstrap_interpreter is None
    ):
        raise RuntimeError(
            "native provider bootstrap entrypoint and interpreter must be paired"
        )
    if (
        provider_bootstrap_entrypoint is None
        and provider_bootstrap_entrypoint_identity is not None
    ):
        raise RuntimeError(
            "native provider bootstrap identity requires an entrypoint"
        )
    if provider_bootstrap_entrypoint is not None:
        assert provider_bootstrap_interpreter is not None
        entrypoint = Path(provider_bootstrap_entrypoint).resolve(strict=True)
        interpreter = Path(provider_bootstrap_interpreter).resolve(strict=True)
        untrusted_roots = tuple(
            Path(candidate).resolve(strict=True) for candidate in provider_untrusted_roots
        )
        for trusted_path in (entrypoint, interpreter):
            if any(
                trusted_path == untrusted_root
                or untrusted_root in trusted_path.parents
                for untrusted_root in untrusted_roots
            ):
                raise RuntimeError(
                    "native provider bootstrap executable is task-writable"
                )
        entrypoint_stat = entrypoint.stat()
        interpreter_stat = interpreter.stat()
        if (
            provider_bootstrap_entrypoint_identity is not None
            and (
                int(entrypoint_stat.st_dev),
                int(entrypoint_stat.st_ino),
            )
            != tuple(int(value) for value in provider_bootstrap_entrypoint_identity)
        ):
            raise RuntimeError(
                "native provider bootstrap entrypoint identity changed"
            )
        parent_pid = os.getpid()
        parent_start_ticks = _process_start_ticks(parent_pid)
        if parent_start_ticks is None:
            raise RuntimeError("cannot fence native provider bootstrap parent")
        config["provider_bootstrap"] = {
            # The Codex npm launcher uses ``#!/usr/bin/env node``.  Its first
            # process therefore resolves through the guarded PATH before the
            # provider has started.  Permit only that exact operator-installed
            # entrypoint, only for the ``exec`` provider subcommand, and only
            # when it is spawned directly by this exact service process.
            "command": "node",
            "entrypoint": str(entrypoint),
            "entrypoint_device": int(entrypoint_stat.st_dev),
            "entrypoint_inode": int(entrypoint_stat.st_ino),
            "interpreter": str(interpreter),
            "interpreter_device": int(interpreter_stat.st_dev),
            "interpreter_inode": int(interpreter_stat.st_ino),
            "parent_pid": parent_pid,
            "parent_start_ticks": parent_start_ticks,
            "subcommand": "exec",
        }
    config_path = root / _CONFIG_NAME
    config_path.write_text(json.dumps(config, sort_keys=True), encoding="utf-8")
    config_path.chmod(0o400)

    launcher = guard_bin / "oompah-validation-guard"
    trusted_source_root = str(Path(__file__).resolve().parents[1])
    launcher.write_text(
        # Isolated mode ignores PYTHONPATH and the candidate working directory.
        # Insert only the deployed package root before importing the guard.
        f"#!{sys.executable} -I\n"
        "import sys\n"
        f"sys.path.insert(0, {trusted_source_root!r})\n"
        "from oompah.native_validation_guard import main\n"
        "raise SystemExit(main())\n",
        encoding="utf-8",
    )
    launcher.chmod(stat.S_IRUSR | stat.S_IXUSR)
    for command in sorted(_WRAPPED_COMMANDS | _python_command_names(original_path)):
        (guard_bin / command).symlink_to(launcher.name)

    guarded["PATH"] = f"{guard_bin}{os.pathsep}{original_path}"
    # Codex's native command runner consults SHELL for compound invocations.
    # Pointing it at the trusted wrapper lets the wrapper classify the complete
    # shell program before any absolute/project-local child can bypass PATH.
    guarded["SHELL"] = str(guard_bin / "bash")
    guarded[_GUARD_ENV] = str(guard_bin)
    return guarded, root


def _load_invocation_config(argv0: str) -> tuple[dict[str, object], Path]:
    guard_bin = Path(os.path.abspath(argv0)).parent
    config_path = guard_bin.parent / _CONFIG_NAME
    # Reject a shell-selected lookalike config.  The service creates this file
    # owner-readable and immutable to the sandboxed agent.
    mode = stat.S_IMODE(config_path.stat().st_mode)
    if mode != stat.S_IRUSR:
        raise RuntimeError("native validation guard configuration has unsafe permissions")
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError("native validation guard configuration is invalid")
    return raw, guard_bin


def _real_executable(command: str, search_path: str, guard_bin: Path) -> str:
    clean_path = os.pathsep.join(
        part
        for part in search_path.split(os.pathsep)
        if Path(part or ".").resolve() != guard_bin.resolve()
    )
    resolved = shutil.which(command, path=clean_path)
    if not resolved:
        raise RuntimeError(f"guarded executable is unavailable: {command}")
    return resolved


def _process_start_ticks(pid: int) -> int | None:
    """Return Linux process start ticks for exact bootstrap-parent fencing."""

    try:
        raw = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8")
        return int(raw[raw.rfind(")") + 2 :].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _trusted_provider_bootstrap_interpreter(
    command: str,
    arguments: list[str],
    config: Mapping[str, object],
) -> str | None:
    """Recognize only the exact service-launched Codex npm bootstrap.

    A path/argv match alone would let a task launch the installed Codex entry
    point and escape command-scoped validation.  The direct parent PID and
    Linux start ticks bind this exception to the service process that created
    the read-only guard configuration.  All provider descendants and
    task-controlled lookalikes continue through normal heavyweight
    classification.
    """

    raw = config.get("provider_bootstrap")
    if not isinstance(raw, dict) or command != str(raw.get("command") or ""):
        return None
    if len(arguments) < 2 or arguments[1] != str(raw.get("subcommand") or ""):
        return None
    try:
        expected_parent = int(raw["parent_pid"])
        expected_ticks = int(raw["parent_start_ticks"])
        expected_device = int(raw["entrypoint_device"])
        expected_inode = int(raw["entrypoint_inode"])
        expected_entrypoint = Path(str(raw["entrypoint"])).resolve(strict=True)
        expected_interpreter = Path(str(raw["interpreter"])).resolve(strict=True)
        invoked_entrypoint = Path(arguments[0]).resolve(strict=True)
        invoked_stat = invoked_entrypoint.stat()
        interpreter_stat = expected_interpreter.stat()
        expected_interpreter_device = int(raw["interpreter_device"])
        expected_interpreter_inode = int(raw["interpreter_inode"])
    except (KeyError, OSError, TypeError, ValueError):
        return None
    parent_pid = os.getppid()
    trusted = (
        parent_pid == expected_parent
        and _process_start_ticks(parent_pid) == expected_ticks
        and invoked_entrypoint == expected_entrypoint
        and int(invoked_stat.st_dev) == expected_device
        and int(invoked_stat.st_ino) == expected_inode
        and int(interpreter_stat.st_dev) == expected_interpreter_device
        and int(interpreter_stat.st_ino) == expected_interpreter_inode
    )
    return str(expected_interpreter) if trusted else None


def main() -> int:
    """Shim entry point.  Successful execution never returns."""

    command = Path(sys.argv[0]).name
    invocation = " ".join([command, *(str(value) for value in sys.argv[1:])])
    config, guard_bin = _load_invocation_config(sys.argv[0])
    search_path = str(config.get("path") or os.defpath)
    child_env = dict(os.environ)

    bootstrap_interpreter = _trusted_provider_bootstrap_interpreter(
        command,
        sys.argv[1:],
        config,
    )
    if bootstrap_interpreter is not None:
        # Keep the guarded PATH/SHELL in the provider environment: only its
        # bootstrap is exempt.  Genuine commands launched by the provider must
        # still resolve through these shims and acquire capacity themselves.
        # Execute the pre-resolved operator interpreter, never a PATH-selected
        # task lookalike.
        os.execve(bootstrap_interpreter, [command, *sys.argv[1:]], child_env)

    executable = _real_executable(command, search_path, guard_bin)

    if not is_heavyweight_validation_command(invocation):
        os.execve(executable, [command, *sys.argv[1:]], child_env)

    # The outer heavy launcher owns capacity for its whole process tree. Strip
    # the shim directory only now so make/tox/npm descendants cannot queue
    # recursively behind their own parent's lease.
    child_env["PATH"] = search_path
    child_env["SHELL"] = str(config.get("shell") or "/bin/sh")
    child_env.pop(_GUARD_ENV, None)

    owner_raw = config.get("owner")
    if not isinstance(owner_raw, dict):
        raise RuntimeError("native validation guard owner is invalid")
    owner = ValidationLeaseOwner(
        kind=str(owner_raw.get("kind") or ""),
        project_id=str(owner_raw.get("project_id") or ""),
        task_id=str(owner_raw.get("task_id") or ""),
        authority_generation=str(owner_raw.get("authority_generation") or ""),
        priority=int(owner_raw.get("priority") or 0),
    )
    timeout_seconds = max(float(config.get("timeout_seconds") or 0.0), 1.0)
    cancellation_raw = str(config.get("cancellation_path") or "").strip()
    if not cancellation_raw:
        raise RuntimeError("native validation cancellation fence is unavailable")
    cancellation_path = Path(cancellation_raw)

    def _cancelled() -> bool:
        return cancellation_path.exists() or os.getppid() == 1

    lease = ValidationResourceLease(
        str(config.get("state_path") or ""),
        capacity=int(config.get("capacity") or 1),
        aging_seconds=float(config.get("aging_seconds") or 30.0),
        poll_seconds=float(config.get("poll_seconds") or 0.05),
    )
    handle = lease.acquire(
        owner,
        is_cancelled=_cancelled,
    )
    if _cancelled():
        handle.release()
        raise RuntimeError("native validation authority was withdrawn before launch")
    if os.name == "posix":
        # Some native runners already launch each command as a process-group
        # leader.  That is sufficient for ownership-scoped killpg; calling
        # setsid from an existing group leader would fail with EPERM.
        if os.getpgrp() != os.getpid():
            try:
                os.setsid()
            except PermissionError as exc:
                handle.release()
                raise RuntimeError(
                    "native validation command could not create a dedicated "
                    "process group"
                ) from exc
        if os.getpgrp() != os.getpid():
            handle.release()
            raise RuntimeError(
                "native validation command lacks a dedicated process group"
            )
    handle.attach_process(
        SimpleNamespace(pid=os.getpid()),
        timeout_seconds=timeout_seconds,
    )
    if _cancelled():
        # This wrapper is now the attached process. Calling cancel_owner here
        # would pidfd-stop our own process before it could resume or release
        # the fence. Exiting before exec is already the complete cancellation
        # action; the backend's independent cancellation records the durable
        # authority tombstone for any concurrent invocation.
        handle.release()
        raise RuntimeError("native validation authority was withdrawn before exec")
    for descriptor in handle.pass_fds:
        os.set_inheritable(descriptor, True)
    os.execve(executable, [command, *sys.argv[1:]], child_env)
    return 1  # pragma: no cover - os.execve replaces this process


__all__ = ["install_native_validation_guard", "main"]
