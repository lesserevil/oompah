"""Tests for PID-reuse-safe lifecycle identity checks."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.process_identity import identity_matches, read_identity


@pytest.mark.skipif(
    os.name != "posix" or not Path("/proc").is_dir(),
    reason="requires Linux procfs",
)
def test_identity_matches_pid_start_group_session_and_workspace(tmp_path):
    identity = read_identity(os.getpid())
    assert identity is not None

    assert identity_matches(identity, workspace=os.getcwd())

    changed_pid = {**identity, "pid": identity["pid"] + 1}
    assert not identity_matches(changed_pid, pid=os.getpid(), workspace=os.getcwd())

    changed_start = {**identity, "start_time": identity["start_time"] + 1}
    assert not identity_matches(changed_start, workspace=os.getcwd())

    changed_group = {**identity, "process_group": identity["process_group"] + 1}
    assert not identity_matches(changed_group, workspace=os.getcwd())

    changed_session = {**identity, "session": identity["session"] + 1}
    assert not identity_matches(changed_session, workspace=os.getcwd())

    changed_cwd = {**identity, "cwd": str(tmp_path)}
    assert not identity_matches(changed_cwd, workspace=os.getcwd())

    assert not identity_matches(identity, workspace=str(tmp_path))


def test_read_identity_returns_none_for_missing_pid():
    assert read_identity(999_999_999) is None
