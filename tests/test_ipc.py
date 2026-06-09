"""Tests for the SQLite-backed IPC coordination layer (TASK-469.5.1).

Covers:
- OrchestratorIPC construction and WAL mode
- put_kv / get_kv round-trip
- publish_state / read_state convenience wrappers
- publish_issues / read_issues convenience wrappers
- publish_maintenance / read_maintenance convenience wrappers
- snapshot_age_ms reflects elapsed time
- enqueue_command / poll_commands / ack_command flow
- Multiple pending commands; ordering by (created_at, id)
- poll_commands marks rows as 'processing', ack_command marks as 'processed'
- Unknown command type acked as 'failed'
- cleanup_old_commands prunes old processed rows
- diagnostics() returns expected structure
- get_ipc() process-level singleton (with env var)
- reset_ipc() clears singleton
- Concurrent put_kv / get_kv from multiple threads (no data corruption)
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time

import pytest

from oompah.ipc import (
    COMMAND_TTL_SECONDS,
    OrchestratorIPC,
    get_ipc,
    get_ipc_db_path,
    reset_ipc,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ipc(tmp_path):
    """A fresh OrchestratorIPC instance backed by a tmp file."""
    db = OrchestratorIPC(str(tmp_path / "test_ipc.db"))
    yield db
    db.close()


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_ipc_opens_and_creates_tables(tmp_path):
    db_path = str(tmp_path / "oompah_ipc.db")
    ipc = OrchestratorIPC(db_path)
    assert os.path.exists(db_path)
    # WAL mode should be active
    conn = sqlite3.connect(db_path)
    row = conn.execute("PRAGMA journal_mode").fetchone()
    conn.close()
    assert row[0] == "wal"
    ipc.close()


def test_ipc_repr(ipc):
    r = repr(ipc)
    assert "OrchestratorIPC" in r
    assert "connected=True" in r


# ---------------------------------------------------------------------------
# Key-value store
# ---------------------------------------------------------------------------


def test_put_kv_and_get_kv_round_trip(ipc):
    ok = ipc.put_kv("state", {"foo": "bar", "n": 42})
    assert ok is True
    value, updated_at = ipc.get_kv("state")
    assert value == {"foo": "bar", "n": 42}
    assert updated_at is not None
    assert updated_at > 0.0


def test_get_kv_missing_key_returns_none(ipc):
    value, updated_at = ipc.get_kv("nonexistent")
    assert value is None
    assert updated_at is None


def test_put_kv_overwrites_existing(ipc):
    ipc.put_kv("state", {"v": 1})
    ipc.put_kv("state", {"v": 2})
    value, _ = ipc.get_kv("state")
    assert value["v"] == 2


def test_put_kv_stores_list(ipc):
    ipc.put_kv("issues", [1, 2, 3])
    value, _ = ipc.get_kv("issues")
    assert value == [1, 2, 3]


def test_snapshot_age_ms_increases(ipc):
    ipc.put_kv("state", {"x": 1})
    time.sleep(0.01)
    age_ms = ipc.snapshot_age_ms("state")
    assert age_ms is not None
    assert age_ms >= 5  # at least 5 ms elapsed


def test_snapshot_age_ms_missing_key(ipc):
    assert ipc.snapshot_age_ms("missing") is None


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------


def test_publish_state_read_state(ipc):
    state = {"paused": False, "counts": {"running": 3}}
    ok = ipc.publish_state(state)
    assert ok is True
    val, ts = ipc.read_state()
    assert val == state
    assert ts is not None


def test_publish_issues_read_issues(ipc):
    issues = {"Open": [{"id": "T1"}], "Done": []}
    ipc.publish_issues(issues)
    val, _ = ipc.read_issues()
    assert val == issues


def test_publish_maintenance_read_maintenance(ipc):
    status = {"auto_archive": {"status": "idle"}}
    ipc.publish_maintenance(status)
    val, _ = ipc.read_maintenance()
    assert val == status


def test_read_state_missing_returns_none(ipc):
    val, ts = ipc.read_state()
    assert val is None
    assert ts is None


# ---------------------------------------------------------------------------
# Command queue
# ---------------------------------------------------------------------------


def test_enqueue_and_poll_basic(ipc):
    cmd_id = ipc.enqueue_command("pause")
    assert isinstance(cmd_id, int)
    assert cmd_id > 0

    commands = ipc.poll_commands()
    assert len(commands) == 1
    cmd = commands[0]
    assert cmd["command"] == "pause"
    assert cmd["payload"] == {}
    assert cmd["id"] == cmd_id


def test_enqueue_with_payload(ipc):
    ipc.enqueue_command("dispatch_issue", {"identifier": "TASK-123"})
    commands = ipc.poll_commands()
    assert commands[0]["payload"] == {"identifier": "TASK-123"}


def test_poll_commands_ordering(ipc):
    """Commands should come back in (created_at, id) order."""
    ipc.enqueue_command("first")
    time.sleep(0.001)
    ipc.enqueue_command("second")
    commands = ipc.poll_commands()
    assert [c["command"] for c in commands] == ["first", "second"]


def test_poll_commands_marks_processing(ipc, tmp_path):
    """After poll_commands, rows are 'processing' and not re-polled."""
    ipc.enqueue_command("pause")
    commands = ipc.poll_commands()
    assert len(commands) == 1

    # A second poll should return nothing while the first is still 'processing'
    commands2 = ipc.poll_commands()
    assert len(commands2) == 0


def test_ack_command_marks_processed(ipc):
    cmd_id = ipc.enqueue_command("unpause")
    ipc.poll_commands()  # moves to 'processing'
    ipc.ack_command(cmd_id, ok=True)

    # Verify row status in the DB directly
    conn = sqlite3.connect(ipc._db_path)
    row = conn.execute("SELECT status FROM commands WHERE id=?", (cmd_id,)).fetchone()
    conn.close()
    assert row[0] == "processed"


def test_ack_command_marks_failed(ipc):
    cmd_id = ipc.enqueue_command("request_refresh")
    ipc.poll_commands()
    ipc.ack_command(cmd_id, ok=False)

    conn = sqlite3.connect(ipc._db_path)
    row = conn.execute("SELECT status FROM commands WHERE id=?", (cmd_id,)).fetchone()
    conn.close()
    assert row[0] == "failed"


def test_poll_commands_limit(ipc):
    for i in range(15):
        ipc.enqueue_command(f"cmd_{i}")
    commands = ipc.poll_commands(limit=5)
    assert len(commands) == 5


def test_cleanup_old_commands(ipc):
    cmd_id = ipc.enqueue_command("pause")
    ipc.poll_commands()
    ipc.ack_command(cmd_id, ok=True)

    # Artificially back-date the processed_at timestamp
    conn = sqlite3.connect(ipc._db_path)
    conn.execute(
        "UPDATE commands SET processed_at=? WHERE id=?",
        (time.monotonic() - COMMAND_TTL_SECONDS - 1, cmd_id),
    )
    conn.commit()
    conn.close()

    deleted = ipc.cleanup_old_commands()
    assert deleted == 1

    # Ensure the row is gone
    conn = sqlite3.connect(ipc._db_path)
    row = conn.execute("SELECT id FROM commands WHERE id=?", (cmd_id,)).fetchone()
    conn.close()
    assert row is None


def test_cleanup_does_not_delete_pending(ipc):
    ipc.enqueue_command("pause")
    deleted = ipc.cleanup_old_commands(ttl_seconds=0)  # 0-second TTL
    # Pending commands should NOT be deleted regardless of TTL
    assert deleted == 0

    commands = ipc.poll_commands()
    assert len(commands) == 1


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def test_diagnostics_structure(ipc):
    ipc.publish_state({"paused": False})
    ipc.enqueue_command("pause")
    d = ipc.diagnostics()
    assert d["connected"] is True
    assert "db_path" in d
    assert "kv" in d
    assert "state" in d["kv"]
    assert "commands" in d
    assert "pending" in d["commands"]


def test_diagnostics_when_disconnected(tmp_path):
    ipc = OrchestratorIPC(str(tmp_path / "disc.db"))
    ipc.close()
    ipc._conn = None  # simulate disconnection without re-opening
    # We need to prevent _open from being called again; patch the method
    original_open = ipc._open
    ipc._open = lambda: None  # no-op
    d = ipc.diagnostics()
    ipc._open = original_open
    assert d["connected"] is False


# ---------------------------------------------------------------------------
# Process-level singleton
# ---------------------------------------------------------------------------


def test_get_ipc_returns_none_when_env_unset(monkeypatch):
    monkeypatch.delenv("OOMPAH_IPC_DB_PATH", raising=False)
    reset_ipc()
    result = get_ipc()
    assert result is None


def test_get_ipc_creates_singleton_from_env(monkeypatch, tmp_path):
    db_path = str(tmp_path / "singleton.db")
    monkeypatch.setenv("OOMPAH_IPC_DB_PATH", db_path)
    reset_ipc()
    try:
        ipc1 = get_ipc()
        ipc2 = get_ipc()
        assert ipc1 is ipc2
        assert ipc1 is not None
        assert os.path.exists(db_path)
    finally:
        reset_ipc()
        monkeypatch.delenv("OOMPAH_IPC_DB_PATH", raising=False)


def test_get_ipc_with_explicit_path(tmp_path):
    db_path = str(tmp_path / "explicit.db")
    reset_ipc()
    try:
        ipc = get_ipc(db_path=db_path)
        assert ipc is not None
        assert os.path.exists(db_path)
    finally:
        reset_ipc()


def test_reset_ipc_closes_instance(monkeypatch, tmp_path):
    db_path = str(tmp_path / "reset_test.db")
    monkeypatch.setenv("OOMPAH_IPC_DB_PATH", db_path)
    reset_ipc()
    ipc = get_ipc()
    assert ipc is not None
    reset_ipc()
    # After reset, a new call creates a new instance
    ipc2 = get_ipc()
    assert ipc2 is not ipc
    reset_ipc()
    monkeypatch.delenv("OOMPAH_IPC_DB_PATH", raising=False)


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


def test_concurrent_put_get_no_corruption(ipc):
    """Multiple threads writing different keys shouldn't corrupt each other."""
    errors: list[str] = []
    iterations = 50

    def writer(key: str, val: dict) -> None:
        for _ in range(iterations):
            ok = ipc.put_kv(key, val)
            if not ok:
                errors.append(f"put_kv failed for key={key}")

    def reader(key: str, expected: dict) -> None:
        for _ in range(iterations):
            value, _ = ipc.get_kv(key)
            if value is not None and value != expected:
                errors.append(f"read corruption: key={key} got {value!r}")

    threads = [
        threading.Thread(target=writer, args=("a", {"v": 1})),
        threading.Thread(target=writer, args=("b", {"v": 2})),
        threading.Thread(target=reader, args=("a", {"v": 1})),
        threading.Thread(target=reader, args=("b", {"v": 2})),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Concurrency errors: {errors}"


def test_concurrent_enqueue_poll_no_loss(ipc):
    """Two writers enqueueing concurrently; all commands must be visible."""
    n = 20

    def enqueue_batch(prefix: str) -> None:
        for i in range(n):
            ipc.enqueue_command(f"{prefix}_{i}")

    t1 = threading.Thread(target=enqueue_batch, args=("x",))
    t2 = threading.Thread(target=enqueue_batch, args=("y",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    all_cmds: list[dict] = []
    while True:
        batch = ipc.poll_commands(limit=50)
        if not batch:
            break
        for cmd in batch:
            ipc.ack_command(cmd["id"])
        all_cmds.extend(batch)

    assert len(all_cmds) == 2 * n


# ---------------------------------------------------------------------------
# Orchestrator integration: IPC publishing on notify_observers
# ---------------------------------------------------------------------------


def test_orchestrator_publishes_to_ipc_on_notify(tmp_path, monkeypatch):
    """When an Orchestrator has an IPC instance, _notify_observers publishes state."""
    from unittest.mock import MagicMock

    from oompah.config import ServiceConfig
    from oompah.orchestrator import Orchestrator

    db_path = str(tmp_path / "orch_ipc.db")
    test_ipc = OrchestratorIPC(db_path)

    # Create a minimal orchestrator with the test IPC
    cfg = ServiceConfig()
    state_path = str(tmp_path / "state.json")
    orch = Orchestrator(
        cfg,
        workflow_path=str(tmp_path / "WORKFLOW.md"),
        ipc=test_ipc,
        state_path=state_path,
    )

    # Patch get_snapshot to return a simple dict
    orch.get_snapshot = MagicMock(return_value={"paused": False, "test": True})

    orch._notify_observers()

    state, _ = test_ipc.read_state()
    assert state == {"paused": False, "test": True}

    test_ipc.close()


def test_orchestrator_no_ipc_when_path_unset(tmp_path, monkeypatch):
    """When OOMPAH_IPC_DB_PATH is unset, orchestrator._ipc is None."""
    monkeypatch.delenv("OOMPAH_IPC_DB_PATH", raising=False)
    reset_ipc()

    from oompah.config import ServiceConfig
    from oompah.orchestrator import Orchestrator

    cfg = ServiceConfig()
    state_path = str(tmp_path / "state.json")
    orch = Orchestrator(
        cfg,
        workflow_path=str(tmp_path / "WORKFLOW.md"),
        state_path=state_path,
    )
    assert orch._ipc is None


# ---------------------------------------------------------------------------
# Server IPC integration: api_state reads from IPC in API-only mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_state_reads_from_ipc_when_no_orchestrator(tmp_path, monkeypatch):
    """api_state() should return the IPC snapshot when _orchestrator is None."""
    from oompah import server as server_module

    db_path = str(tmp_path / "server_ipc.db")
    test_ipc = OrchestratorIPC(db_path)
    test_ipc.publish_state({"paused": True, "counts": {"running": 0}})

    original_orch = server_module._orchestrator
    original_ipc = server_module._ipc
    try:
        server_module._orchestrator = None
        server_module._ipc = test_ipc

        response = await server_module.api_state()
        import json as _json
        data = _json.loads(response.body)

        assert data.get("paused") is True
        assert "api_metrics" in data
    finally:
        server_module._orchestrator = original_orch
        server_module._ipc = original_ipc
        test_ipc.close()


@pytest.mark.asyncio
async def test_api_state_returns_503_when_ipc_empty(tmp_path, monkeypatch):
    """api_state() returns 503 when no orchestrator and IPC has no snapshot."""
    from oompah import server as server_module

    db_path = str(tmp_path / "empty_ipc.db")
    test_ipc = OrchestratorIPC(db_path)

    original_orch = server_module._orchestrator
    original_ipc = server_module._ipc
    try:
        server_module._orchestrator = None
        server_module._ipc = test_ipc

        response = await server_module.api_state()
        assert response.status_code == 503
    finally:
        server_module._orchestrator = original_orch
        server_module._ipc = original_ipc
        test_ipc.close()


# ---------------------------------------------------------------------------
# Server IPC integration: pause/resume/dispatch enqueue commands
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_pause_enqueues_ipc_command(tmp_path):
    """api_orchestrator_pause() enqueues 'pause' when orchestrator is absent."""
    from oompah import server as server_module

    db_path = str(tmp_path / "pause_ipc.db")
    test_ipc = OrchestratorIPC(db_path)

    original_orch = server_module._orchestrator
    original_ipc = server_module._ipc
    try:
        server_module._orchestrator = None
        server_module._ipc = test_ipc

        import json as _json
        response = await server_module.api_orchestrator_pause()
        data = _json.loads(response.body)

        assert data["ok"] is True
        assert "ipc_command_id" in data

        commands = test_ipc.poll_commands()
        assert len(commands) == 1
        assert commands[0]["command"] == "pause"
    finally:
        server_module._orchestrator = original_orch
        server_module._ipc = original_ipc
        test_ipc.close()


@pytest.mark.asyncio
async def test_api_resume_enqueues_ipc_command(tmp_path):
    """api_orchestrator_resume() enqueues 'unpause' when orchestrator is absent."""
    from oompah import server as server_module

    db_path = str(tmp_path / "resume_ipc.db")
    test_ipc = OrchestratorIPC(db_path)

    original_orch = server_module._orchestrator
    original_ipc = server_module._ipc
    try:
        server_module._orchestrator = None
        server_module._ipc = test_ipc

        import json as _json
        response = await server_module.api_orchestrator_resume()
        data = _json.loads(response.body)

        assert data["ok"] is True
        commands = test_ipc.poll_commands()
        assert commands[0]["command"] == "unpause"
    finally:
        server_module._orchestrator = original_orch
        server_module._ipc = original_ipc
        test_ipc.close()


@pytest.mark.asyncio
async def test_api_dispatch_enqueues_ipc_command(tmp_path):
    """api_orchestrator_dispatch() enqueues 'dispatch_issue' when orch is absent."""
    from oompah import server as server_module

    db_path = str(tmp_path / "dispatch_ipc.db")
    test_ipc = OrchestratorIPC(db_path)

    original_orch = server_module._orchestrator
    original_ipc = server_module._ipc
    try:
        server_module._orchestrator = None
        server_module._ipc = test_ipc

        import json as _json
        response = await server_module.api_orchestrator_dispatch("TASK-42")
        data = _json.loads(response.body)

        assert data["ok"] is True
        assert data["dispatched"] == "TASK-42"

        commands = test_ipc.poll_commands()
        assert commands[0]["command"] == "dispatch_issue"
        assert commands[0]["payload"]["identifier"] == "TASK-42"
    finally:
        server_module._orchestrator = original_orch
        server_module._ipc = original_ipc
        test_ipc.close()


# ---------------------------------------------------------------------------
# Orchestrator: process_ipc_commands integration
# ---------------------------------------------------------------------------


def test_process_ipc_commands_pause(tmp_path):
    """_process_ipc_commands processes a 'pause' command correctly."""
    from oompah.config import ServiceConfig
    from oompah.orchestrator import Orchestrator

    db_path = str(tmp_path / "cmd_pause.db")
    test_ipc = OrchestratorIPC(db_path)
    cfg = ServiceConfig()
    state_path = str(tmp_path / "state.json")
    orch = Orchestrator(
        cfg,
        workflow_path=str(tmp_path / "WORKFLOW.md"),
        ipc=test_ipc,
        state_path=state_path,
    )

    # Force unpaused state (state file doesn't exist so _load_paused_state returns False)
    orch._paused = False
    test_ipc.enqueue_command("pause")
    orch._process_ipc_commands()
    assert orch._paused

    # Verify command was ACKed
    import sqlite3 as _sql
    conn = _sql.connect(db_path)
    row = conn.execute("SELECT status FROM commands").fetchone()
    conn.close()
    assert row[0] == "processed"

    test_ipc.close()


def test_process_ipc_commands_unpause(tmp_path):
    """_process_ipc_commands processes an 'unpause' command."""
    from oompah.config import ServiceConfig
    from oompah.orchestrator import Orchestrator

    db_path = str(tmp_path / "cmd_unpause.db")
    test_ipc = OrchestratorIPC(db_path)
    cfg = ServiceConfig()
    state_path = str(tmp_path / "state.json")
    orch = Orchestrator(
        cfg,
        workflow_path=str(tmp_path / "WORKFLOW.md"),
        ipc=test_ipc,
        state_path=state_path,
    )

    # Pause first
    orch._paused = True
    test_ipc.enqueue_command("unpause")
    orch._process_ipc_commands()
    assert not orch._paused
    test_ipc.close()


def test_process_ipc_commands_unknown_type(tmp_path):
    """Unknown command types are ACKed as 'failed' and don't raise."""
    from oompah.config import ServiceConfig
    from oompah.orchestrator import Orchestrator

    db_path = str(tmp_path / "cmd_unknown.db")
    test_ipc = OrchestratorIPC(db_path)
    cfg = ServiceConfig()
    state_path = str(tmp_path / "state.json")
    orch = Orchestrator(
        cfg,
        workflow_path=str(tmp_path / "WORKFLOW.md"),
        ipc=test_ipc,
        state_path=state_path,
    )

    cmd_id = test_ipc.enqueue_command("totally_unknown_command_xyz")
    orch._process_ipc_commands()  # must not raise

    import sqlite3 as _sql
    conn = _sql.connect(db_path)
    row = conn.execute("SELECT status FROM commands WHERE id=?", (cmd_id,)).fetchone()
    conn.close()
    assert row[0] == "failed"

    test_ipc.close()


def test_process_ipc_commands_no_ipc(tmp_path):
    """_process_ipc_commands is a no-op when _ipc is None."""
    from oompah.config import ServiceConfig
    from oompah.orchestrator import Orchestrator

    cfg = ServiceConfig()
    state_path = str(tmp_path / "state.json")
    orch = Orchestrator(
        cfg,
        workflow_path=str(tmp_path / "WORKFLOW.md"),
        ipc=None,
        state_path=state_path,
    )
    # Ensure no IPC from env either
    orch._ipc = None

    # Should not raise
    orch._process_ipc_commands()
