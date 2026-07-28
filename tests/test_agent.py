"""Tests for CLI agent subprocess lifecycle management."""

from __future__ import annotations

import asyncio
import os
import shlex
import signal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.agent import AgentSession


@pytest.mark.asyncio
async def test_start_creates_dedicated_posix_session(tmp_path, monkeypatch):
    session = AgentSession("agent", str(tmp_path))
    process = MagicMock()
    session._drain_stderr = AsyncMock()
    monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "client-secret")
    monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", "/run/secrets/client-pass")
    monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "operator")

    with patch(
        "oompah.agent.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=process),
    ) as create_process:
        await session.start()
        await asyncio.sleep(0)

    assert create_process.await_args.kwargs["start_new_session"] is (
        os.name == "posix"
    )
    child_env = create_process.await_args.kwargs["env"]
    assert "OOMPAH_SERVER_USERNAME" not in child_env
    assert "OOMPAH_SERVER_PASSWORD" not in child_env
    assert "OOMPAH_SERVER_PASSWORD_FILE" not in child_env


@pytest.mark.asyncio
@pytest.mark.skipif(os.name != "posix", reason="requires POSIX process groups")
async def test_stop_uses_sigterm_for_graceful_process_group_exit(tmp_path):
    session = AgentSession("agent", str(tmp_path))
    process = MagicMock(pid=12345, returncode=None)
    session._process = process
    sent_signals: list[signal.Signals] = []

    def _killpg(_pid, sig):
        if sig == 0:
            if process.returncode is not None:
                raise ProcessLookupError
            return
        sent_signals.append(sig)
        if sig == signal.SIGTERM:
            process.returncode = 0

    with patch("oompah.agent.os.killpg", side_effect=_killpg):
        await session.stop(timeout_s=0.1)

    assert sent_signals == [signal.SIGTERM]
    process.terminate.assert_not_called()
    process.kill.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.skipif(os.name != "posix", reason="requires POSIX process groups")
async def test_stop_escalates_stubborn_process_group_to_sigkill(tmp_path):
    session = AgentSession("agent", str(tmp_path))
    process = MagicMock(pid=12345, returncode=None)
    session._process = process
    sent_signals: list[signal.Signals] = []
    killed = False

    def _killpg(_pid, sig):
        nonlocal killed
        if sig == 0:
            if killed:
                raise ProcessLookupError
            return
        sent_signals.append(sig)
        if sig == signal.SIGKILL:
            killed = True
            process.returncode = -signal.SIGKILL

    with patch("oompah.agent.os.killpg", side_effect=_killpg):
        await session.stop(timeout_s=0.03)

    assert sent_signals == [signal.SIGTERM, signal.SIGKILL]
    process.terminate.assert_not_called()
    process.kill.assert_not_called()


@pytest.mark.asyncio
async def test_stop_has_safe_non_posix_fallback(tmp_path):
    session = AgentSession("agent", str(tmp_path))
    process = MagicMock(pid=12345, returncode=None)
    process.terminate.side_effect = lambda: setattr(process, "returncode", 0)
    session._process = process

    with patch("oompah.agent.os.name", "nt"):
        await session.stop(timeout_s=0.1)

    process.terminate.assert_called_once_with()
    process.kill.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.skipif(os.name != "posix", reason="requires POSIX process groups")
async def test_stop_kills_spawned_descendant(tmp_path):
    pid_file = tmp_path / "child.pid"
    command = (
        f"sleep 60 & echo $! > {shlex.quote(str(pid_file))}; "
        "wait"
    )
    session = AgentSession(command, str(tmp_path))
    await session.start()
    parent_pid = int(session.pid)
    child_pid: int | None = None

    try:
        for _ in range(100):
            if pid_file.exists():
                child_pid = int(pid_file.read_text().strip())
                break
            await asyncio.sleep(0.01)
        assert child_pid is not None

        await session.stop(timeout_s=0.5)

        for _ in range(100):
            if not _pid_exists(parent_pid) and not _pid_exists(child_pid):
                break
            await asyncio.sleep(0.01)
        assert not _pid_exists(parent_pid)
        assert not _pid_exists(child_pid)
    finally:
        if session._process and session._process.returncode is None:
            try:
                os.killpg(parent_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await session._process.wait()


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True
