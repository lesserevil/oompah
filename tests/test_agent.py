"""Tests for CLI agent subprocess lifecycle management."""

from __future__ import annotations

import asyncio
from contextlib import ExitStack
import os
import shlex
import signal
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.agent import (
    MAX_LINE_SIZE,
    AgentError,
    AgentSession,
    ProcessIdentity,
    _ProcessRecord,
    _capture_linux_descendants,
    _linux_process_record,
    capture_workspace_processes,
    terminate_captured_processes,
)


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
    assert create_process.await_args.kwargs["limit"] == MAX_LINE_SIZE
    child_env = create_process.await_args.kwargs["env"]
    assert "OOMPAH_SERVER_USERNAME" not in child_env
    assert "OOMPAH_SERVER_PASSWORD" not in child_env
    assert "OOMPAH_SERVER_PASSWORD_FILE" not in child_env
    assert child_env["OOMPAH_TASK_VENV"] == str(tmp_path / ".oompah" / "task-venv")


@pytest.mark.asyncio
async def test_start_binds_transient_missing_cwd_before_contact(tmp_path):
    process = MagicMock(pid=12345, returncode=None)
    observed = _ProcessRecord(
        ppid=1,
        identity=ProcessIdentity(
            pid=12345,
            starttime=321,
            process_group=12345,
            session=12345,
            cwd=None,
        ),
        argv=(),
    )
    session: AgentSession

    def _contacted():
        assert session._process is process
        assert session._stderr_task is not None
        assert session._process_identity is not None

    session = AgentSession("agent", str(tmp_path), on_transport_contact=_contacted)
    session._drain_stderr = AsyncMock()
    with (
        patch(
            "oompah.agent.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=process),
        ),
        patch("oompah.agent._linux_process_record", return_value=observed),
    ):
        await session.start()
        await asyncio.sleep(0)

    assert session._process_identity == ProcessIdentity(
        pid=12345,
        starttime=321,
        process_group=12345,
        session=12345,
        cwd=str(tmp_path),
    )


@pytest.mark.asyncio
async def test_epic_rebase_session_rejects_unbridged_cli_transport(tmp_path, monkeypatch):
    """A CLI's provider transport and native shell cannot be separated."""
    session = AgentSession("agent", str(tmp_path), isolate_remote_write=True)
    monkeypatch.setenv("HOME", "/operator/home")
    monkeypatch.setenv("SSH_AUTH_SOCK", "/run/ssh-agent.sock")
    monkeypatch.setenv("GITHUB_TOKEN", "forge-secret")

    with patch(
        "oompah.agent.asyncio.create_subprocess_exec",
        new=AsyncMock(),
    ) as create_process:
        with pytest.raises(AgentError, match="API/ACP bridged provider") as exc:
            await session.start()

    assert exc.value.error_class == "isolated_cli_unavailable"
    create_process.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_admits_immediately_before_subprocess_and_marks_contact(tmp_path):
    events: list[str] = []

    def _admit():
        events.append("permit")
        return None

    session = AgentSession(
        "agent",
        str(tmp_path),
        before_transport_contact=_admit,
        on_transport_contact=lambda: events.append("contacted"),
        on_precontact_admission_cancelled=lambda: events.append("rollback"),
    )
    process = MagicMock(pid=None)
    session._drain_stderr = AsyncMock()

    async def _spawn(*_args, **_kwargs):
        events.append("popen")
        return process

    with patch(
        "oompah.agent.asyncio.create_subprocess_exec",
        side_effect=_spawn,
    ):
        await session.start()
        await asyncio.sleep(0)

    assert events == ["permit", "popen", "contacted"]
    assert session.transport_contacted is True


@pytest.mark.asyncio
async def test_start_rolls_back_unused_permit_when_local_popen_fails(tmp_path):
    events: list[str] = []
    session = AgentSession(
        "missing-agent",
        str(tmp_path),
        before_transport_contact=lambda: events.append("permit") or None,
        on_transport_contact=lambda: events.append("contacted"),
        on_precontact_admission_cancelled=lambda: events.append("rollback"),
    )

    with patch(
        "oompah.agent.asyncio.create_subprocess_exec",
        new=AsyncMock(side_effect=FileNotFoundError("missing bash")),
    ):
        with pytest.raises(AgentError, match="Agent command not found"):
            await session.start()

    assert events == ["permit", "rollback"]
    assert session.transport_contacted is False


@pytest.mark.asyncio
async def test_stop_before_start_prevents_permit_and_subprocess(tmp_path):
    admit = MagicMock(return_value=None)
    rollback = MagicMock()
    session = AgentSession(
        "agent",
        str(tmp_path),
        before_transport_contact=admit,
        on_precontact_admission_cancelled=rollback,
    )

    await session.stop()
    with patch(
        "oompah.agent.asyncio.create_subprocess_exec",
        new=AsyncMock(),
    ) as create_process:
        with pytest.raises(AgentError, match="cancelled before subprocess"):
            await session.start()

    admit.assert_not_called()
    rollback.assert_not_called()
    create_process.assert_not_awaited()
    assert session.transport_contacted is False


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
async def test_concurrent_stop_callers_serialize_cleanup(tmp_path):
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
        process.returncode = 0

    with patch("oompah.agent.os.killpg", side_effect=_killpg):
        await asyncio.gather(
            session.stop(timeout_s=0.1),
            session.stop(timeout_s=0.1),
        )

    assert sent_signals == [signal.SIGTERM]


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
@pytest.mark.skipif(
    os.name != "posix" or not os.path.isdir("/proc"),
    reason="requires Linux procfs",
)
async def test_stop_refuses_reused_or_reassigned_process_identity(tmp_path):
    """A changed start-time/session identity must never receive a signal."""

    session = AgentSession("sleep 60", str(tmp_path))
    await session.start()
    process = session._process
    assert process is not None
    assert session._process_identity is not None
    original = session._process_identity
    session._process_identity = ProcessIdentity(
        pid=original.pid,
        starttime=original.starttime + 1,
        process_group=original.process_group,
        session=original.session,
        cwd=original.cwd,
    )

    try:
        with patch("oompah.agent.os.killpg") as killpg:
            await session.stop(timeout_s=0.1)
        killpg.assert_not_called()
        assert process.returncode is None
    finally:
        process.kill()
        await process.wait()
        assert session._stderr_task is not None
        await asyncio.wait_for(session._stderr_task, timeout=1.0)
        await asyncio.sleep(0)


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name != "posix" or not os.path.isdir("/proc"),
    reason="requires Linux procfs",
)
async def test_stop_tolerates_disappearing_procfs_cwd(tmp_path):
    """A missing cwd after stable identity capture remains owned."""

    session = AgentSession("sleep 60", str(tmp_path))
    await session.start()
    process = session._process
    assert process is not None
    assert session._process_identity is not None
    real_killpg = os.killpg
    signals: list[signal.Signals] = []

    def _record_without_root_cwd(pid):
        record = _linux_process_record(pid)
        if record is None or pid != process.pid:
            return record
        current = record.identity
        return _ProcessRecord(
            ppid=record.ppid,
            identity=ProcessIdentity(
                pid=current.pid,
                starttime=current.starttime,
                process_group=current.process_group,
                session=current.session,
                cwd=None,
            ),
            argv=record.argv,
        )

    def _killpg(pid, sig):
        signals.append(sig)
        return real_killpg(pid, sig)

    try:
        with (
            patch(
                "oompah.agent._linux_process_record",
                side_effect=_record_without_root_cwd,
            ),
            patch("oompah.agent.os.killpg", side_effect=_killpg),
        ):
            await session.stop(timeout_s=0.2)
        assert signals == [signal.SIGTERM]
        assert process.returncode is not None
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        if session._stderr_task is not None and not session._stderr_task.done():
            await asyncio.wait_for(session._stderr_task, timeout=1.0)


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name != "posix" or not os.path.isdir("/proc"),
    reason="requires Linux procfs",
)
async def test_stop_total_identity_capture_failure_is_fail_closed(tmp_path):
    session = AgentSession("sleep 60", str(tmp_path))
    await session.start()
    process = session._process
    assert process is not None
    assert session._process_identity is not None
    session._process_identity = None

    try:
        with (
            patch("oompah.agent.os.killpg") as killpg,
            patch("oompah.agent.os.kill") as kill_process,
        ):
            await session.stop(timeout_s=0.05)
        killpg.assert_not_called()
        kill_process.assert_not_called()
        assert process.returncode is None
    finally:
        process.kill()
        await process.wait()
        assert session._stderr_task is not None
        await asyncio.wait_for(session._stderr_task, timeout=1.0)


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name != "posix" or not os.path.isdir("/proc"),
    reason="requires Linux procfs",
)
async def test_stop_bounds_slow_descendant_capture(tmp_path, caplog):
    session = AgentSession("sleep 60", str(tmp_path))
    await session.start()
    process = session._process
    assert process is not None

    def _slow_capture(*_args, **_kwargs):
        time.sleep(0.25)
        return {}, True

    try:
        with (
            patch(
                "oompah.agent._capture_linux_descendants",
                side_effect=_slow_capture,
            ),
            patch("oompah.agent.os.killpg") as killpg,
            patch("oompah.agent.os.kill") as kill_process,
            caplog.at_level("INFO", logger="oompah.agent"),
        ):
            started = asyncio.get_running_loop().time()
            await session.stop(timeout_s=0.05)
            elapsed = asyncio.get_running_loop().time() - started
        assert elapsed < 0.15
        assert process.returncode is None
        assert "descendant capture was incomplete" in caplog.text
        assert "Agent process stopped" not in caplog.text
        killpg.assert_not_called()
        kill_process.assert_not_called()
        await asyncio.sleep(0.25)
    finally:
        process.kill()
        await process.wait()
        assert session._stderr_task is not None
        await asyncio.wait_for(session._stderr_task, timeout=1.0)


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name != "posix" or not os.path.isdir("/proc"),
    reason="requires Linux procfs",
)
async def test_stop_bounds_slow_live_identity_read(tmp_path, caplog):
    session = AgentSession("sleep 60", str(tmp_path))
    await session.start()
    process = session._process
    assert process is not None
    root_record = _linux_process_record(process.pid)
    assert root_record is not None

    def _slow_live(*_args, **_kwargs):
        time.sleep(0.25)
        return {process.pid: root_record}, True

    try:
        with (
            patch(
                "oompah.agent._bounded_descendant_capture",
                new=AsyncMock(return_value=({process.pid: root_record}, True)),
            ),
            patch(
                "oompah.agent._capture_live_processes",
                side_effect=_slow_live,
            ),
            patch("oompah.agent.os.killpg") as killpg,
            patch("oompah.agent.os.kill") as kill_process,
            caplog.at_level("INFO", logger="oompah.agent"),
        ):
            started = asyncio.get_running_loop().time()
            await session.stop(timeout_s=0.05)
            elapsed = asyncio.get_running_loop().time() - started
        assert elapsed < 0.15
        assert process.returncode is None
        assert "descendant capture was incomplete" in caplog.text
        assert "Agent process stopped" not in caplog.text
        killpg.assert_not_called()
        kill_process.assert_not_called()
        await asyncio.sleep(0.25)
    finally:
        process.kill()
        await process.wait()
        assert session._stderr_task is not None
        await asyncio.wait_for(session._stderr_task, timeout=1.0)


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name != "posix" or not os.path.isdir("/proc"),
    reason="requires Linux procfs",
)
async def test_stop_bounds_slow_individual_proc_reads(tmp_path):
    session = AgentSession("sleep 60", str(tmp_path))
    await session.start()
    process = session._process
    assert process is not None

    def _slow_record(pid):
        time.sleep(0.03)
        return _linux_process_record(pid)

    try:
        with (
            patch(
                "oompah.agent._linux_process_record",
                side_effect=_slow_record,
            ),
            patch("oompah.agent.os.killpg") as killpg,
            patch("oompah.agent.os.kill") as kill_process,
        ):
            started = asyncio.get_running_loop().time()
            await session.stop(timeout_s=0.05)
            elapsed = asyncio.get_running_loop().time() - started
        assert elapsed < 0.15
        assert process.returncode is None
        killpg.assert_not_called()
        kill_process.assert_not_called()
        await asyncio.sleep(0.05)
    finally:
        process.kill()
        await process.wait()
        assert session._stderr_task is not None
        await asyncio.wait_for(session._stderr_task, timeout=1.0)


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name != "posix" or not os.path.isdir("/proc"),
    reason="requires Linux procfs",
)
async def test_truncated_capture_cannot_report_retirement_complete(tmp_path, caplog):
    session = AgentSession("sleep 60", str(tmp_path))
    await session.start()
    process = session._process
    assert process is not None
    assert session._process_identity is not None
    root_record = _linux_process_record(process.pid)
    assert root_record is not None

    with (
        patch(
            "oompah.agent._bounded_descendant_capture",
            new=AsyncMock(return_value=({process.pid: root_record}, False)),
        ),
        caplog.at_level("INFO", logger="oompah.agent"),
    ):
        await session.stop(timeout_s=0.2)

    assert process.returncode is not None
    assert "descendant capture was incomplete" in caplog.text
    assert "Agent process stopped" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name != "posix" or not os.path.isdir("/proc"),
    reason="requires Linux procfs",
)
async def test_replaced_expected_root_capture_is_empty_and_fail_closed(tmp_path):
    session = AgentSession("sleep 60", str(tmp_path))
    await session.start()
    process = session._process
    assert process is not None
    assert session._process_identity is not None
    expected = session._process_identity
    replacement = _ProcessRecord(
        ppid=1,
        identity=ProcessIdentity(
            pid=expected.pid,
            starttime=expected.starttime + 1,
            process_group=expected.process_group,
            session=expected.session,
            cwd=expected.cwd,
        ),
        argv=(),
    )

    try:
        with (
            patch("oompah.agent._linux_process_record", return_value=replacement),
            patch("oompah.agent.os.killpg") as killpg,
            patch("oompah.agent.os.kill") as kill_process,
        ):
            await session.stop(timeout_s=0.05)
        assert process.returncode is None
        killpg.assert_not_called()
        kill_process.assert_not_called()
    finally:
        process.kill()
        await process.wait()
        assert session._stderr_task is not None
        await asyncio.wait_for(session._stderr_task, timeout=1.0)


def test_descendant_capture_rejects_reparented_child_without_signal():
    expected = ProcessIdentity(
        pid=123,
        starttime=10,
        process_group=123,
        session=123,
        cwd="/workspace",
    )
    root = _ProcessRecord(ppid=1, identity=expected, argv=())
    unrelated = _ProcessRecord(
        ppid=777,
        identity=ProcessIdentity(
            pid=456,
            starttime=20,
            process_group=456,
            session=456,
            cwd="/other",
        ),
        argv=(),
    )

    with (
        patch(
            "oompah.agent._linux_process_record",
            side_effect=[root, root, unrelated],
        ),
        patch("oompah.agent.os.listdir", return_value=["123"]),
        patch("oompah.agent.Path.read_text", return_value="456"),
        patch("oompah.agent.os.kill") as kill_process,
        patch("oompah.agent.os.killpg") as killpg,
    ):
        records, complete = _capture_linux_descendants(
            expected,
            deadline=time.monotonic() + 1.0,
        )

    assert records == {123: root}
    assert complete is False
    kill_process.assert_not_called()
    killpg.assert_not_called()


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

        assert session._stderr_task is not None
        assert session._stderr_task.done()

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


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name != "posix" or not os.path.isdir("/proc"),
    reason="requires Linux process groups and procfs",
)
async def test_stop_kills_term_resistant_descendant_after_leader_exit(tmp_path):
    ready_file = tmp_path / "resistant.ready"
    child_code = (
        "import os,pathlib,signal,time;"
        "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
        f"pathlib.Path({str(ready_file)!r}).write_text(str(os.getpid()));"
        "time.sleep(60)"
    )
    command = (
        "trap 'exit 0' TERM; "
        f"{shlex.quote(sys.executable)} -c {shlex.quote(child_code)} & wait"
    )
    session = AgentSession(command, str(tmp_path))
    await session.start()
    parent_pid = int(session.pid)
    child_pid = await _wait_pid_file(ready_file)

    try:
        await asyncio.wait_for(session.stop(timeout_s=0.4), timeout=1.0)
        await _wait_pids_gone(parent_pid, child_pid)
        assert session._stderr_task is not None
        assert session._stderr_task.done()
    finally:
        await _cleanup_session(session, parent_pid, child_pid)


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name != "posix" or not os.path.isdir("/proc"),
    reason="requires Linux process groups and procfs",
)
async def test_stop_exactly_kills_descendant_that_setsid_on_term(tmp_path):
    ready_file = tmp_path / "setsid.ready"
    escaped_file = tmp_path / "setsid.escaped"
    child_code = (
        "import os,pathlib,signal,time;"
        f"escaped=pathlib.Path({str(escaped_file)!r});"
        "signal.signal(signal.SIGTERM,lambda *_:(os.setsid(),escaped.touch()));"
        f"pathlib.Path({str(ready_file)!r}).write_text(str(os.getpid()));"
        "time.sleep(60)"
    )
    command = (
        "trap 'exit 0' TERM; "
        f"{shlex.quote(sys.executable)} -c {shlex.quote(child_code)} & wait"
    )
    session = AgentSession(command, str(tmp_path))
    await session.start()
    parent_pid = int(session.pid)
    child_pid = await _wait_pid_file(ready_file)

    try:
        await asyncio.wait_for(session.stop(timeout_s=0.4), timeout=1.0)
        await _wait_pids_gone(parent_pid, child_pid)
        assert escaped_file.exists()
    finally:
        await _cleanup_session(session, parent_pid, child_pid)


async def _exercise_setsid_term_handler_fork(
    tmp_path,
    *,
    inject_incomplete_observation: bool,
) -> None:
    import oompah.agent as agent_module

    ready_file = tmp_path / "fork.ready"
    forked_file = tmp_path / "fork.child"
    child_code = (
        "import os,pathlib,signal,time\n"
        f"forked=pathlib.Path({str(forked_file)!r})\n"
        "def on_term(*_):\n"
        " os.setsid()\n"
        " child=os.fork()\n"
        " if child == 0:\n"
        "  signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
        "  forked.write_text(str(os.getpid()))\n"
        "  time.sleep(60)\n"
        "  os._exit(0)\n"
        " os.waitpid(child,0)\n"
        "signal.signal(signal.SIGTERM,on_term)\n"
        f"pathlib.Path({str(ready_file)!r}).write_text(str(os.getpid()))\n"
        "time.sleep(60)\n"
    )
    command = (
        "trap 'exit 0' TERM; "
        f"{shlex.quote(sys.executable)} -c {shlex.quote(child_code)} & wait"
    )
    session = AgentSession(command, str(tmp_path))
    await session.start()
    parent_pid = int(session.pid)
    child_pid: int | None = None
    forked_pid: int | None = None
    descendant_capture = agent_module._bounded_descendant_capture
    live_capture = agent_module._bounded_live_capture
    descendant_calls = 0
    live_calls = 0
    injected_incomplete_snapshot = False

    async def _observe_descendant_capture(*args, **kwargs):
        nonlocal descendant_calls
        result = await descendant_capture(*args, **kwargs)
        descendant_calls += 1
        return result

    async def _inject_incomplete_post_term_snapshot(*args, **kwargs):
        nonlocal live_calls, injected_incomplete_snapshot
        live_calls += 1
        # The first snapshot authorizes SIGTERM.  Simulate its immediately
        # following observation crossing the read deadline without seeing a
        # live identity.  Incomplete empty data must trigger escalation, not
        # falsely prove that the process tree stopped.
        if live_calls == 2:
            await _wait_pid_file(forked_file)
            for _ in range(100):
                if session._process is not None and (
                    session._process.returncode is not None
                ):
                    break
                await asyncio.sleep(0.005)
            assert session._process is not None
            assert session._process.returncode is not None
            injected_incomplete_snapshot = True
            return {}, False
        return await live_capture(*args, **kwargs)

    try:
        child_pid = await _wait_pid_file(ready_file)
        # This adversarial handler creates a new session, forks, and blocks in
        # waitpid while the bounded stop path revalidates the changing tree in
        # worker threads.  Keep the assertion well below the five-second
        # production default while still allowing the handler, refresh,
        # escalation, and observation phases to complete under CI jitter.
        with ExitStack() as patches:
            if inject_incomplete_observation:
                patches.enter_context(
                    patch(
                        "oompah.agent._bounded_descendant_capture",
                        new=_observe_descendant_capture,
                    )
                )
                patches.enter_context(
                    patch(
                        "oompah.agent._bounded_live_capture",
                        new=_inject_incomplete_post_term_snapshot,
                    )
                )
            await asyncio.wait_for(session.stop(timeout_s=1.0), timeout=2.0)
        forked_pid = await _wait_pid_file(forked_file)
        await _wait_pids_gone(parent_pid, child_pid, forked_pid)
        if inject_incomplete_observation:
            assert injected_incomplete_snapshot is True
            assert descendant_calls >= 2
    finally:
        cleanup_pids = [parent_pid]
        if child_pid is not None:
            cleanup_pids.append(child_pid)
        if forked_pid is None and forked_file.exists():
            try:
                forked_pid = int(forked_file.read_text())
            except (FileNotFoundError, ValueError):
                pass
        if forked_pid is not None:
            cleanup_pids.append(forked_pid)
        await _cleanup_session(session, *cleanup_pids)


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name != "posix" or not os.path.isdir("/proc"),
    reason="requires Linux process groups and procfs",
)
async def test_stop_refreshes_setsid_term_handler_fork_before_kill(tmp_path):
    await _exercise_setsid_term_handler_fork(
        tmp_path,
        inject_incomplete_observation=False,
    )


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name != "posix" or not os.path.isdir("/proc"),
    reason="requires Linux process groups and procfs",
)
async def test_incomplete_empty_post_term_observation_escalates(tmp_path):
    await _exercise_setsid_term_handler_fork(
        tmp_path,
        inject_incomplete_observation=True,
    )


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name != "posix" or not os.path.isdir("/proc"),
    reason="requires Linux process groups and procfs",
)
async def test_preexited_leader_reports_incomplete_without_pipe_leak(
    tmp_path,
    caplog,
):
    ready_file = tmp_path / "orphan.ready"
    child_code = (
        "import os,pathlib,signal,time;"
        "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
        f"pathlib.Path({str(ready_file)!r}).write_text(str(os.getpid()));"
        "time.sleep(60)"
    )
    command = (
        f"{shlex.quote(sys.executable)} -c {shlex.quote(child_code)} & exit 0"
    )
    session = AgentSession(command, str(tmp_path))
    await session.start()
    parent_pid = int(session.pid)
    child_pid = await _wait_pid_file(ready_file)
    for _ in range(100):
        if session._process is not None and session._process.returncode is not None:
            break
        await asyncio.sleep(0.01)
    assert session._process is not None
    assert session._process.returncode == 0

    try:
        with caplog.at_level("INFO", logger="oompah.agent"):
            await asyncio.wait_for(session.stop(timeout_s=0.2), timeout=1.0)

        assert _pid_exists(child_pid)
        assert session._stderr_task is not None
        assert session._stderr_task.done()
        assert "Agent process retirement incomplete" in caplog.text
        assert "Agent process stopped" not in caplog.text
    finally:
        await _cleanup_session(session, parent_pid, child_pid)


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name != "posix" or not os.path.isdir("/proc"),
    reason="requires Linux process groups and procfs",
)
async def test_cancelled_stop_returns_after_bounded_hard_cleanup(tmp_path):
    ready_file = tmp_path / "cancel.ready"
    child_code = (
        "import os,pathlib,signal,time;"
        "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
        f"pathlib.Path({str(ready_file)!r}).write_text(str(os.getpid()));"
        "time.sleep(60)"
    )
    command = (
        "trap '' TERM; "
        f"{shlex.quote(sys.executable)} -c {shlex.quote(child_code)} & wait"
    )
    session = AgentSession(command, str(tmp_path))
    await session.start()
    parent_pid = int(session.pid)
    child_pid = await _wait_pid_file(ready_file)

    try:
        waiter = asyncio.create_task(session.stop(timeout_s=2.0))
        await asyncio.sleep(0.05)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(waiter, timeout=1.0)

        await _wait_pids_gone(parent_pid, child_pid)
        assert session._stderr_task is not None
        assert session._stderr_task.done()
    finally:
        await _cleanup_session(session, parent_pid, child_pid)


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name != "posix" or not os.path.isdir("/proc"),
    reason="requires Linux procfs",
)
async def test_workspace_capture_kills_reparentable_subprocess_tree(tmp_path):
    """Owned-tree cleanup never requires a host-wide procfs scan."""

    process = await asyncio.create_subprocess_exec(
        "bash",
        "-c",
        "sleep 60 & wait",
        cwd=tmp_path,
    )
    try:
        captured: dict[int, int] = {}
        with patch(
            "oompah.agent._linux_process_snapshot",
            side_effect=AssertionError("host-wide procfs scan is forbidden"),
        ):
            for _ in range(100):
                captured = capture_workspace_processes(str(tmp_path))
                if process.pid in captured and len(captured) >= 2:
                    break
                await asyncio.sleep(0.01)
            assert process.pid in captured
            assert len(captured) >= 2

            survivors = await asyncio.to_thread(
                terminate_captured_processes,
                captured,
                timeout_s=0.2,
            )
        await asyncio.wait_for(process.wait(), timeout=1)

        assert survivors == set()
        assert all(not _pid_exists(pid) for pid in captured)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


async def _wait_pid_file(path) -> int:
    for _ in range(200):
        if path.exists():
            try:
                return int(path.read_text())
            except (FileNotFoundError, ValueError):
                # pathlib.write_text creates/truncates before writing.  A
                # concurrent reader can briefly observe an empty file.
                pass
        await asyncio.sleep(0.01)
    raise AssertionError(f"PID file was not created: {path}")


async def _wait_pids_gone(*pids: int) -> None:
    for _ in range(100):
        if all(not _pid_exists(pid) for pid in pids):
            return
        await asyncio.sleep(0.01)
    survivors = [pid for pid in pids if _pid_exists(pid)]
    assert not survivors, f"processes survived cleanup: {survivors}"


async def _cleanup_session(session: AgentSession, *pids: int) -> None:
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if session._process is not None and session._process.returncode is None:
        await asyncio.wait_for(session._process.wait(), timeout=1.0)
    if session._stderr_task is not None and not session._stderr_task.done():
        session._stderr_task.cancel()
        await asyncio.gather(session._stderr_task, return_exceptions=True)
