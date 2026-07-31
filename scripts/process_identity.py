#!/usr/bin/env python3
"""Read and validate Linux process identities for lifecycle cleanup.

The PID alone is not an ownership proof: a process can exit and its PID can be
reused before a delayed cleanup runs.  This helper records the PID together
with the kernel start time, process group, session, and exact working
directory so a cleanup caller can refuse to signal an unrelated process.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def read_identity(pid: int) -> dict[str, Any] | None:
    """Return the current identity for *pid*, or ``None`` if it is gone."""

    if os.name != "posix" or not Path("/proc").is_dir():
        return None
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        tail = stat[stat.rfind(")") + 2 :].split()
        cwd = os.path.realpath(os.readlink(f"/proc/{pid}/cwd"))
        return {
            "pid": int(pid),
            "start_time": int(tail[19]),
            "process_group": int(tail[2]),
            "session": int(tail[3]),
            "cwd": cwd,
        }
    except (OSError, ValueError, IndexError):
        return None


def identity_matches(
    expected: dict[str, Any],
    *,
    pid: int | None = None,
    workspace: str | None = None,
) -> bool:
    """Return whether the live process still has the recorded identity."""

    expected_pid = int(expected.get("pid", -1))
    actual_pid = expected_pid if pid is None else int(pid)
    if actual_pid != expected_pid:
        return False
    actual = read_identity(actual_pid)
    if actual is None:
        return False
    for key in ("pid", "start_time", "process_group", "session"):
        try:
            if int(actual[key]) != int(expected[key]):
                return False
        except (KeyError, TypeError, ValueError):
            return False
    raw_expected_cwd = expected.get("cwd")
    if not isinstance(raw_expected_cwd, str) or not raw_expected_cwd:
        return False
    expected_cwd = os.path.realpath(raw_expected_cwd)
    if actual["cwd"] != expected_cwd:
        return False
    if workspace is not None and actual["cwd"] != os.path.realpath(workspace):
        return False
    return True


def _main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in {"capture", "verify"}:
        print(
            "usage: process_identity.py capture PID WORKSPACE | "
            "verify PID WORKSPACE META",
            file=sys.stderr,
        )
        return 2
    pid = int(argv[2])
    workspace = argv[3]
    if argv[1] == "capture":
        if len(argv) != 4:
            return 2
        identity = read_identity(pid)
        if identity is None or identity["cwd"] != os.path.realpath(workspace):
            return 1
        print(json.dumps(identity, sort_keys=True))
        return 0

    if len(argv) != 5:
        return 2
    try:
        expected = json.loads(Path(argv[4]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 1
    return 0 if identity_matches(expected, pid=pid, workspace=workspace) else 1


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
