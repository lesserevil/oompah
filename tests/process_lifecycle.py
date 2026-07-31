"""Ownership-aware subprocess helpers used by process-global tests."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from oompah.agent import (
    ProcessIdentity,
    capture_workspace_processes,
    terminate_captured_processes,
)
from scripts.process_identity import read_identity


@dataclass
class OwnedProcess:
    """A subprocess plus the identity and workspace that the test owns."""

    process: subprocess.Popen
    identity: ProcessIdentity
    workspace: Path


def _as_identity(raw: dict[str, object]) -> ProcessIdentity:
    return ProcessIdentity(
        pid=int(raw["pid"]),
        starttime=int(raw["start_time"]),
        process_group=int(raw["process_group"]),
        session=int(raw["session"]),
        cwd=str(raw["cwd"]),
    )


def start_owned_process(
    argv: Sequence[str],
    *,
    workspace: Path,
    env: Mapping[str, str] | None = None,
) -> OwnedProcess:
    """Start a new-session child and capture its complete identity."""

    workspace.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        list(argv),
        cwd=workspace,
        env=dict(env) if env is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=(os.name == "posix"),
    )
    deadline = time.monotonic() + 2
    identity: ProcessIdentity | None = None
    while time.monotonic() < deadline:
        raw = read_identity(process.pid)
        if raw is not None and raw["cwd"] == str(workspace.resolve()):
            identity = _as_identity(raw)
            break
        if process.poll() is not None:
            break
        time.sleep(0.01)
    if identity is None:
        process.kill()
        process.wait()
        raise RuntimeError(f"could not capture owned process identity for {argv!r}")
    return OwnedProcess(process=process, identity=identity, workspace=workspace)


def stop_owned_process(owner: OwnedProcess, *, timeout_s: float = 2) -> set[int]:
    """Reap only the captured process tree if its identity still matches."""

    current = read_identity(owner.identity.pid)
    if current is None or _as_identity(current) != owner.identity:
        # A reused PID is not ours.  Deliberately do not signal it.
        return {owner.identity.pid}

    captured: dict[int, ProcessIdentity] = {owner.identity.pid: owner.identity}
    captured.update(
        capture_workspace_processes(
            str(owner.workspace),
            ancestor_pid=owner.identity.pid,
        )
    )
    survivors = terminate_captured_processes(captured, timeout_s=timeout_s)
    try:
        owner.process.wait(timeout=max(timeout_s, 0.1))
    except subprocess.TimeoutExpired:
        # The identity-aware function has already made its final attempt.  Do
        # not fall back to a raw PID or process-group signal here.
        pass
    return survivors
