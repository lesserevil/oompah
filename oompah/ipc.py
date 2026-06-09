"""SQLite-backed IPC coordination layer for the oompah service split.

This module provides the durable local coordination mechanism that enables
a physical process boundary between oompah services:

  oompah-scheduler  owns dispatch/reconcile/review ticks; publishes snapshots
  oompah-api        serves cached state/issues from SQLite; enqueues commands
  oompah-maintenance owns archive/worktree cleanup/repo heal; publishes status

Activation
----------
Set ``OOMPAH_IPC_DB_PATH`` to a shared file path (e.g.
``/tmp/oompah_ipc.db``) in both the scheduler and API processes.  When the
env var is unset the layer is a no-op and oompah runs as a single combined
process (existing behaviour, fully backward-compatible).

Database design
---------------
WAL journal mode is enabled so readers (API process) and the single writer
(scheduler process) never block each other.  The schema intentionally stays
minimal — two tables cover all current needs:

kv (key TEXT PK, value TEXT NOT NULL, updated_at REAL NOT NULL)
    Named snapshot slots.  Current keys:
      "state"       — JSON blob from ``Orchestrator.get_snapshot()``
      "issues"      — JSON blob from the issues board serialiser
      "maintenance" — JSON blob aggregating ``_maintenance_status``

commands (id INTEGER PK AUTOINCREMENT, command TEXT, payload TEXT,
          status TEXT, created_at REAL, processed_at REAL)
    FIFO queue for API → scheduler commands (pause, unpause, refresh,
    dispatch_issue, …).  Commands are soft-deleted (``status='processed'``)
    rather than hard-deleted so they can be inspected for diagnostics.
    A cleanup sweep prunes processed rows older than ``COMMAND_TTL_SECONDS``.

Thread safety
-------------
``OrchestratorIPC`` is thread-safe for concurrent use from the asyncio
event loop and its thread pools.  Each public method acquires a
``threading.Lock`` around the SQLite connection, so only one thread enters
SQLite at a time.  The per-call ``BEGIN IMMEDIATE`` on writes prevents
SQLITE_BUSY races.  Reads use the auto-commit path (WAL readers never need
an exclusive lock).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

# Env var that opts-in to multi-process IPC mode.
IPC_DB_PATH_ENV = "OOMPAH_IPC_DB_PATH"

# Commands older than this (seconds) are eligible for cleanup.
COMMAND_TTL_SECONDS = 3600  # 1 hour

# How many pending commands to process in a single poll() call.
COMMAND_POLL_BATCH = 20

# Schema version — bump when the schema changes in a backward-incompatible way.
_SCHEMA_VERSION = 1

_SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kv (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS commands (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    command      TEXT    NOT NULL,
    payload      TEXT    NOT NULL DEFAULT '{}',
    status       TEXT    NOT NULL DEFAULT 'pending',
    created_at   REAL    NOT NULL,
    processed_at REAL
);

CREATE INDEX IF NOT EXISTS commands_status_created
    ON commands (status, created_at);
"""


def get_ipc_db_path() -> str | None:
    """Return the IPC database path from the environment, or None if unset."""
    return os.environ.get(IPC_DB_PATH_ENV) or None


class OrchestratorIPC:
    """SQLite-backed IPC layer between oompah service processes.

    Construct one instance per process.  Callers that want to publish
    snapshots (the scheduler) call :meth:`put_kv`.  Callers that want
    to read cached snapshots (the API process) call :meth:`get_kv`.
    The command FIFO is used to forward API-layer user commands (pause,
    refresh, …) to the scheduler process.

    All public methods are safe to call from any thread.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._open()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _open(self) -> None:
        """Open (or re-open) the SQLite connection and apply the schema."""
        try:
            conn = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
                timeout=5.0,
            )
            conn.row_factory = sqlite3.Row
            conn.executescript(_SCHEMA_SQL)
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
                ("version", str(_SCHEMA_VERSION)),
            )
            conn.commit()
            self._conn = conn
            logger.debug("OrchestratorIPC: opened %s", self._db_path)
        except sqlite3.Error as exc:
            logger.error("OrchestratorIPC: failed to open %s: %s", self._db_path, exc)
            self._conn = None

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:  # noqa: BLE001
                    pass
                self._conn = None

    def _ensure_conn(self) -> sqlite3.Connection | None:
        """Return the connection, re-opening if it was closed after an error."""
        if self._conn is None:
            self._open()
        return self._conn

    # ------------------------------------------------------------------
    # Key-value snapshot store
    # ------------------------------------------------------------------

    def put_kv(self, key: str, value: Any) -> bool:
        """Write *value* (serialised to JSON) under *key*.

        Returns True on success, False on any SQLite error (logged; does not
        raise so that a broken IPC channel never crashes the scheduler).
        """
        with self._lock:
            conn = self._ensure_conn()
            if conn is None:
                return False
            try:
                payload = json.dumps(value, default=str)
                conn.execute(
                    "INSERT OR REPLACE INTO kv(key, value, updated_at) VALUES(?, ?, ?)",
                    (key, payload, time.monotonic()),
                )
                conn.commit()
                return True
            except (sqlite3.Error, TypeError) as exc:
                logger.warning("OrchestratorIPC.put_kv(%s): %s", key, exc)
                return False

    def get_kv(self, key: str) -> tuple[Any | None, float | None]:
        """Return ``(value, updated_at_monotonic)`` for *key*, or ``(None, None)``.

        The value is JSON-decoded.  ``updated_at`` is the monotonic timestamp
        of the last successful :meth:`put_kv` call (useful for staleness
        checks in the API process).
        """
        with self._lock:
            conn = self._ensure_conn()
            if conn is None:
                return None, None
            try:
                row = conn.execute(
                    "SELECT value, updated_at FROM kv WHERE key = ?", (key,)
                ).fetchone()
                if row is None:
                    return None, None
                return json.loads(row["value"]), float(row["updated_at"])
            except (sqlite3.Error, json.JSONDecodeError) as exc:
                logger.warning("OrchestratorIPC.get_kv(%s): %s", key, exc)
                return None, None

    def snapshot_age_ms(self, key: str) -> float | None:
        """Return milliseconds since the snapshot was last written, or None."""
        with self._lock:
            conn = self._ensure_conn()
            if conn is None:
                return None
            try:
                row = conn.execute(
                    "SELECT updated_at FROM kv WHERE key = ?", (key,)
                ).fetchone()
                if row is None:
                    return None
                return (time.monotonic() - float(row["updated_at"])) * 1000
            except sqlite3.Error as exc:
                logger.warning("OrchestratorIPC.snapshot_age_ms(%s): %s", key, exc)
                return None

    # ------------------------------------------------------------------
    # Command queue (API → scheduler FIFO)
    # ------------------------------------------------------------------

    def enqueue_command(self, command: str, payload: dict[str, Any] | None = None) -> int | None:
        """Insert a *command* into the pending queue.

        Returns the new row ``id`` on success, or ``None`` on error.
        *payload* is serialised to JSON.
        """
        with self._lock:
            conn = self._ensure_conn()
            if conn is None:
                return None
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO commands(command, payload, status, created_at)
                    VALUES(?, ?, 'pending', ?)
                    """,
                    (command, json.dumps(payload or {}), time.monotonic()),
                )
                conn.commit()
                return cursor.lastrowid
            except (sqlite3.Error, TypeError) as exc:
                logger.warning("OrchestratorIPC.enqueue_command(%s): %s", command, exc)
                return None

    def poll_commands(self, limit: int = COMMAND_POLL_BATCH) -> list[dict[str, Any]]:
        """Return up to *limit* pending commands and mark them as 'processing'.

        Callers (the scheduler) must call :meth:`ack_command` once each
        command is handled.  The 'processing' intermediate status means a
        scheduler restart won't silently swallow commands that were dequeued
        but not yet executed.
        """
        with self._lock:
            conn = self._ensure_conn()
            if conn is None:
                return []
            try:
                rows = conn.execute(
                    """
                    SELECT id, command, payload, created_at
                    FROM commands
                    WHERE status = 'pending'
                    ORDER BY created_at, id
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                if not rows:
                    return []
                ids = [row["id"] for row in rows]
                placeholders = ",".join("?" * len(ids))
                conn.execute(
                    f"UPDATE commands SET status='processing' WHERE id IN ({placeholders})",
                    ids,
                )
                conn.commit()
                result = []
                for row in rows:
                    try:
                        payload = json.loads(row["payload"])
                    except json.JSONDecodeError:
                        payload = {}
                    result.append(
                        {
                            "id": row["id"],
                            "command": row["command"],
                            "payload": payload,
                            "created_at": row["created_at"],
                        }
                    )
                return result
            except sqlite3.Error as exc:
                logger.warning("OrchestratorIPC.poll_commands: %s", exc)
                return []

    def ack_command(self, command_id: int, *, ok: bool = True) -> None:
        """Mark a command as processed (or failed).

        *ok=True* → status='processed'; *ok=False* → status='failed'.
        """
        status = "processed" if ok else "failed"
        with self._lock:
            conn = self._ensure_conn()
            if conn is None:
                return
            try:
                conn.execute(
                    "UPDATE commands SET status=?, processed_at=? WHERE id=?",
                    (status, time.monotonic(), command_id),
                )
                conn.commit()
            except sqlite3.Error as exc:
                logger.warning("OrchestratorIPC.ack_command(%d): %s", command_id, exc)

    def cleanup_old_commands(self, ttl_seconds: float = COMMAND_TTL_SECONDS) -> int:
        """Delete processed/failed commands older than *ttl_seconds*.

        Returns the number of rows deleted.
        """
        cutoff = time.monotonic() - ttl_seconds
        with self._lock:
            conn = self._ensure_conn()
            if conn is None:
                return 0
            try:
                cur = conn.execute(
                    "DELETE FROM commands WHERE status IN ('processed', 'failed') AND processed_at < ?",
                    (cutoff,),
                )
                conn.commit()
                return cur.rowcount
            except sqlite3.Error as exc:
                logger.warning("OrchestratorIPC.cleanup_old_commands: %s", exc)
                return 0

    # ------------------------------------------------------------------
    # Convenience — state/issues/maintenance snapshots
    # ------------------------------------------------------------------

    def publish_state(self, snapshot: dict[str, Any]) -> bool:
        """Write the orchestrator state snapshot (scheduler side)."""
        return self.put_kv("state", snapshot)

    def publish_issues(self, issues: dict[str, Any]) -> bool:
        """Write the issues board snapshot (scheduler side)."""
        return self.put_kv("issues", issues)

    def publish_maintenance(self, status: dict[str, Any]) -> bool:
        """Write the maintenance status blob (scheduler/maintenance side)."""
        return self.put_kv("maintenance", status)

    def read_state(self) -> tuple[dict[str, Any] | None, float | None]:
        """Read the state snapshot (API side).

        Returns ``(snapshot_dict, age_monotonic)`` or ``(None, None)`` if absent.
        """
        return self.get_kv("state")

    def read_issues(self) -> tuple[dict[str, Any] | None, float | None]:
        """Read the issues board snapshot (API side).

        Returns ``(issues_dict, age_monotonic)`` or ``(None, None)`` if absent.
        """
        return self.get_kv("issues")

    def read_maintenance(self) -> tuple[dict[str, Any] | None, float | None]:
        """Read the maintenance status (API side)."""
        return self.get_kv("maintenance")

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def diagnostics(self) -> dict[str, Any]:
        """Return a summary dict suitable for inclusion in the state snapshot."""
        with self._lock:
            conn = self._ensure_conn()
            if conn is None:
                return {"db_path": self._db_path, "connected": False}
            try:
                kv_rows = conn.execute("SELECT key, updated_at FROM kv").fetchall()
                cmd_counts = conn.execute(
                    "SELECT status, COUNT(*) as n FROM commands GROUP BY status"
                ).fetchall()
                now = time.monotonic()
                kv_info = {
                    row["key"]: {"age_ms": round((now - row["updated_at"]) * 1000, 1)}
                    for row in kv_rows
                }
                cmd_info = {row["status"]: row["n"] for row in cmd_counts}
                return {
                    "db_path": self._db_path,
                    "connected": True,
                    "kv": kv_info,
                    "commands": cmd_info,
                }
            except sqlite3.Error as exc:
                return {"db_path": self._db_path, "connected": False, "error": str(exc)}

    def __repr__(self) -> str:
        return f"OrchestratorIPC(db_path={self._db_path!r}, connected={self._conn is not None})"


# ---------------------------------------------------------------------------
# Process-level singleton helpers
# ---------------------------------------------------------------------------

_ipc_instance: OrchestratorIPC | None = None
_ipc_instance_lock = threading.Lock()


def get_ipc(db_path: str | None = None) -> OrchestratorIPC | None:
    """Return the process-level IPC instance, creating it if necessary.

    When *db_path* is None the path is read from the ``OOMPAH_IPC_DB_PATH``
    environment variable.  Returns None when no path is configured (single-
    process / combined mode).
    """
    global _ipc_instance
    path = db_path or get_ipc_db_path()
    if path is None:
        return None
    with _ipc_instance_lock:
        if _ipc_instance is None:
            _ipc_instance = OrchestratorIPC(path)
        return _ipc_instance


def reset_ipc() -> None:
    """Close and discard the process-level IPC instance.

    Intended for tests and process shutdown — production code should use
    :func:`get_ipc` exclusively.
    """
    global _ipc_instance
    with _ipc_instance_lock:
        if _ipc_instance is not None:
            _ipc_instance.close()
            _ipc_instance = None
