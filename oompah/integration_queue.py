"""Restart-safe per-epic integration queue with expiring leases."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import sqlite3
import threading
import time
from typing import Callable, Mapping, Sequence


INTEGRATION_QUEUE_SCHEMA_VERSION = 6
_INITIALIZE_LOCK = threading.Lock()
STANDALONE_RECLASSIFICATION_REASON = "delivery_reclassified:standalone"


@dataclass(frozen=True)
class IntegrationQueueItem:
    project_id: str
    epic_id: str
    task_id: str
    task_branch: str
    head_sha: str
    base_sha: str | None
    priority: int
    submitted_at: str
    state: str
    attempts: int
    lease_owner: str | None
    lease_expires_at: float | None
    updated_at: str
    last_error: str | None = None
    retry_forced: bool = False
    next_retry_at: float | None = None
    rebased_from_head_sha: str | None = None
    integrated_sha: str | None = None
    # Durable intent written before the executor mutates the private branch
    # with ``git rebase``.  If the process exits before the rebased head can be
    # checkpointed, the surviving clean local head is known to be
    # executor-owned and may be adopted by the replacement workflow attempt.
    rebase_intent_pending: bool = False
    rebased_publication_pending: bool = False
    # Monotonic integration-event identity used by durable historical replay.
    # Unlike epic/priority/submitted fields it never moves behind a cursor.
    history_sequence: int = 0
    # Ephemeral one-shot authority returned only by ``claim_next``.  It is
    # deliberately excluded from durable snapshots and authority generations.
    claimed_retry_forced: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            key: getattr(self, key)
            for key in self.__dataclass_fields__
            if key != "claimed_retry_forced"
        }

    def authority_generation(self) -> str:
        """Return a stable token for this exact durable row generation."""

        payload = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS integration_queue (
    project_id TEXT NOT NULL,
    epic_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    task_branch TEXT NOT NULL,
    head_sha TEXT NOT NULL,
    base_sha TEXT,
    priority INTEGER NOT NULL DEFAULT 999,
    submitted_at TEXT NOT NULL,
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    lease_owner TEXT,
    lease_expires_at REAL,
    updated_at TEXT NOT NULL,
    last_error TEXT,
    retry_forced INTEGER NOT NULL DEFAULT 0,
    next_retry_at REAL,
    rebased_from_head_sha TEXT,
    integrated_sha TEXT,
    rebase_intent_pending INTEGER NOT NULL DEFAULT 0,
    rebased_publication_pending INTEGER NOT NULL DEFAULT 0,
    history_sequence INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(project_id, task_id)
);
CREATE INDEX IF NOT EXISTS integration_epic_ready_idx
    ON integration_queue(project_id, epic_id, state, priority, submitted_at, task_id);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IntegrationQueueStore:
    """SQLite queue whose lease claim is a single immediate transaction."""

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            self.path,
            check_same_thread=False,
            timeout=10,
        )
        self._conn.row_factory = sqlite3.Row
        with _INITIALIZE_LOCK, self._lock:
            self._conn.execute("PRAGMA busy_timeout=10000")
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)
            # Migrate retry_forced column if it doesn't exist
            try:
                self._conn.execute("SELECT retry_forced FROM integration_queue LIMIT 0")
            except sqlite3.OperationalError:
                self._conn.execute(
                    "ALTER TABLE integration_queue ADD COLUMN retry_forced INTEGER NOT NULL DEFAULT 0"
                )
            try:
                self._conn.execute("SELECT next_retry_at FROM integration_queue LIMIT 0")
            except sqlite3.OperationalError:
                self._conn.execute(
                    "ALTER TABLE integration_queue ADD COLUMN next_retry_at REAL"
                )
            try:
                self._conn.execute(
                    "SELECT rebased_from_head_sha FROM integration_queue LIMIT 0"
                )
            except sqlite3.OperationalError:
                self._conn.execute(
                    "ALTER TABLE integration_queue "
                    "ADD COLUMN rebased_from_head_sha TEXT"
                )
            try:
                self._conn.execute(
                    "SELECT integrated_sha FROM integration_queue LIMIT 0"
                )
            except sqlite3.OperationalError:
                self._conn.execute(
                    "ALTER TABLE integration_queue ADD COLUMN integrated_sha TEXT"
                )
            try:
                self._conn.execute(
                    "SELECT rebase_intent_pending "
                    "FROM integration_queue LIMIT 0"
                )
            except sqlite3.OperationalError:
                self._conn.execute(
                    "ALTER TABLE integration_queue ADD COLUMN "
                    "rebase_intent_pending INTEGER NOT NULL DEFAULT 0"
                )
            try:
                self._conn.execute(
                    "SELECT rebased_publication_pending "
                    "FROM integration_queue LIMIT 0"
                )
            except sqlite3.OperationalError:
                self._conn.execute(
                    "ALTER TABLE integration_queue ADD COLUMN "
                    "rebased_publication_pending INTEGER NOT NULL DEFAULT 0"
                )
            try:
                self._conn.execute(
                    "SELECT history_sequence FROM integration_queue LIMIT 0"
                )
            except sqlite3.OperationalError:
                self._conn.execute(
                    "ALTER TABLE integration_queue ADD COLUMN "
                    "history_sequence INTEGER NOT NULL DEFAULT 0"
                )
            # Give pre-v5 integrated rows a stable monotonic history position.
            # The migration is idempotent and preserves already-assigned values.
            counter_row = self._conn.execute(
                "SELECT COALESCE(MAX(history_sequence), 0) AS value "
                "FROM integration_queue"
            ).fetchone()
            stored_counter_row = self._conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key = 'integration_history_sequence'"
            ).fetchone()
            history_counter = max(
                int(counter_row["value"] if counter_row else 0),
                int(stored_counter_row["value"] if stored_counter_row else 0),
            )
            legacy_rows = self._conn.execute(
                "SELECT project_id, task_id FROM integration_queue "
                "WHERE state = 'integrated' AND history_sequence = 0 "
                "ORDER BY project_id, task_id"
            ).fetchall()
            for legacy in legacy_rows:
                history_counter += 1
                self._conn.execute(
                    "UPDATE integration_queue SET history_sequence = ? "
                    "WHERE project_id = ? AND task_id = ?",
                    (
                        history_counter,
                        legacy["project_id"],
                        legacy["task_id"],
                    ),
                )
            self._conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
                ("integration_history_sequence", str(history_counter)),
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
                ("version", str(INTEGRATION_QUEUE_SCHEMA_VERSION)),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _from_row(row: sqlite3.Row) -> IntegrationQueueItem:
        # Handle retry_forced column which may not exist in older databases
        try:
            retry_forced_val = int(row["retry_forced"] or 0)
        except (IndexError, TypeError):
            retry_forced_val = 0
        try:
            next_retry_at = row["next_retry_at"]
        except (IndexError, KeyError):
            next_retry_at = None
        try:
            rebased_from_head_sha = row["rebased_from_head_sha"]
        except (IndexError, KeyError):
            rebased_from_head_sha = None
        try:
            integrated_sha = row["integrated_sha"]
        except (IndexError, KeyError):
            integrated_sha = None
        try:
            rebase_intent_pending = bool(row["rebase_intent_pending"])
        except (IndexError, KeyError):
            rebase_intent_pending = False
        try:
            rebased_publication_pending = bool(
                row["rebased_publication_pending"]
            )
        except (IndexError, KeyError):
            rebased_publication_pending = False
        try:
            history_sequence = int(row["history_sequence"] or 0)
        except (IndexError, KeyError, TypeError, ValueError):
            history_sequence = 0
        
        return IntegrationQueueItem(
            project_id=row["project_id"],
            epic_id=row["epic_id"],
            task_id=row["task_id"],
            task_branch=row["task_branch"],
            head_sha=row["head_sha"],
            base_sha=row["base_sha"],
            priority=int(row["priority"]),
            submitted_at=row["submitted_at"],
            state=row["state"],
            attempts=int(row["attempts"]),
            lease_owner=row["lease_owner"],
            lease_expires_at=row["lease_expires_at"],
            updated_at=row["updated_at"],
            last_error=row["last_error"],
            retry_forced=bool(retry_forced_val),
            next_retry_at=(
                float(next_retry_at) if next_retry_at is not None else None
            ),
            rebased_from_head_sha=(
                str(rebased_from_head_sha).strip()
                if rebased_from_head_sha is not None
                else None
            ),
            integrated_sha=(
                str(integrated_sha).strip() if integrated_sha is not None else None
            ),
            rebase_intent_pending=rebase_intent_pending,
            rebased_publication_pending=rebased_publication_pending,
            history_sequence=history_sequence,
        )

    def _next_history_sequence_locked(self) -> int:
        row = self._conn.execute(
            "SELECT value FROM schema_meta "
            "WHERE key = 'integration_history_sequence'"
        ).fetchone()
        value = int(row["value"] if row is not None else 0) + 1
        self._conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
            ("integration_history_sequence", str(value)),
        )
        return value

    def enqueue(
        self,
        *,
        project_id: str,
        epic_id: str,
        task_id: str,
        task_branch: str,
        head_sha: str,
        base_sha: str | None = None,
        priority: int | None = None,
        submitted_at: str | None = None,
        explicit_retry: bool = False,
        rearm_integrated: bool = False,
        retry_at: float | None = None,
        preserve_attempts: bool = False,
    ) -> IntegrationQueueItem:
        """Insert or refresh a submission; identical resubmits are idempotent.

        ``explicit_retry`` revives an identical blocked or cancelled submission.
        ``rearm_integrated`` additionally revives an identical integrated row
        when the explicit submission carries a fresh canonical ``ready``
        integration record. Ready and integrating rows remain idempotent so
        an operator retry cannot reset active integration.
        """

        values = {
            "project_id": str(project_id).strip(),
            "epic_id": str(epic_id).strip(),
            "task_id": str(task_id).strip(),
            "task_branch": str(task_branch).strip(),
            "head_sha": str(head_sha).strip(),
        }
        missing = [key for key, value in values.items() if not value]
        if missing:
            raise ValueError(f"{', '.join(missing)} required")
        now = _now_iso()
        with self._lock:
            existing = self._conn.execute(
                """
                SELECT * FROM integration_queue
                WHERE project_id = ? AND task_id = ?
                """,
                (values["project_id"], values["task_id"]),
            ).fetchone()
            identical = (
                existing is not None
                and existing["head_sha"] == values["head_sha"]
                and existing["task_branch"] == values["task_branch"]
                and existing["epic_id"] == values["epic_id"]
            )
            retry_inactive = bool(
                identical
                and explicit_retry
                and existing["state"] in {"blocked", "cancelled"}
            )
            retry_integrated = bool(
                identical
                and explicit_retry
                and rearm_integrated
                and existing["state"] == "integrated"
            )
            if identical and not retry_inactive and not retry_integrated:
                return self._from_row(existing)
            # Preserve that a human/durable retry reset an inactive row.
            retry_forced_val = 1 if retry_inactive else 0
            attempts_value = (
                int(existing["attempts"])
                if existing is not None and preserve_attempts
                else 0
            )
            next_retry_value = (
                float(retry_at)
                if retry_at is not None
                else (
                    existing["next_retry_at"]
                    if existing is not None and preserve_attempts
                    else None
                )
            )
            self._conn.execute(
                """
                INSERT INTO integration_queue(
                    project_id, epic_id, task_id, task_branch, head_sha,
                    base_sha, priority, submitted_at, state, attempts,
                    lease_owner, lease_expires_at, updated_at, last_error,
                    retry_forced, next_retry_at, rebased_from_head_sha,
                    integrated_sha, rebase_intent_pending,
                    rebased_publication_pending,
                    history_sequence
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, NULL, NULL, ?, NULL, ?, ?, NULL, NULL, 0, 0, 0)
                ON CONFLICT(project_id, task_id) DO UPDATE SET
                    epic_id = excluded.epic_id,
                    task_branch = excluded.task_branch,
                    head_sha = excluded.head_sha,
                    base_sha = excluded.base_sha,
                    priority = excluded.priority,
                    submitted_at = excluded.submitted_at,
                    state = 'ready',
                    attempts = excluded.attempts,
                    lease_owner = NULL,
                    lease_expires_at = NULL,
                    updated_at = excluded.updated_at,
                    last_error = NULL,
                    retry_forced = excluded.retry_forced,
                    next_retry_at = excluded.next_retry_at,
                    rebased_from_head_sha = NULL,
                    integrated_sha = NULL,
                    rebase_intent_pending = 0,
                    rebased_publication_pending = 0,
                    history_sequence = 0
                """,
                (
                    values["project_id"],
                    values["epic_id"],
                    values["task_id"],
                    values["task_branch"],
                    values["head_sha"],
                    str(base_sha or "").strip() or None,
                    int(priority if priority is not None else 999),
                    submitted_at or now,
                    attempts_value,
                    now,
                    retry_forced_val,
                    next_retry_value,
                ),
            )
            self._conn.commit()
            row = self._conn.execute(
                """
                SELECT * FROM integration_queue
                WHERE project_id = ? AND task_id = ?
                """,
                (values["project_id"], values["task_id"]),
            ).fetchone()
        assert row is not None
        return self._from_row(row)

    def enqueue_if_absent(
        self,
        *,
        project_id: str,
        epic_id: str,
        task_id: str,
        task_branch: str,
        head_sha: str,
        base_sha: str | None = None,
        priority: int | None = None,
        submitted_at: str | None = None,
    ) -> IntegrationQueueItem | None:
        """Insert one recovery generation without adopting a concurrent row."""

        values = {
            "project_id": str(project_id).strip(),
            "epic_id": str(epic_id).strip(),
            "task_id": str(task_id).strip(),
            "task_branch": str(task_branch).strip(),
            "head_sha": str(head_sha).strip(),
        }
        missing = [key for key, value in values.items() if not value]
        if missing:
            raise ValueError(f"{', '.join(missing)} required")
        now = _now_iso()
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                inserted = self._conn.execute(
                    """
                    INSERT OR IGNORE INTO integration_queue(
                        project_id, epic_id, task_id, task_branch, head_sha,
                        base_sha, priority, submitted_at, state, attempts,
                        lease_owner, lease_expires_at, updated_at, last_error,
                        retry_forced, next_retry_at, rebased_from_head_sha,
                        integrated_sha, rebase_intent_pending,
                        rebased_publication_pending,
                        history_sequence
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'ready', 0, NULL, NULL,
                             ?, NULL, 0, NULL, NULL, NULL, 0, 0, 0)
                    """,
                    (
                        values["project_id"],
                        values["epic_id"],
                        values["task_id"],
                        values["task_branch"],
                        values["head_sha"],
                        str(base_sha or "").strip() or None,
                        int(priority if priority is not None else 999),
                        submitted_at or now,
                        now,
                    ),
                )
                if inserted.rowcount != 1:
                    self._conn.rollback()
                    return None
                row = self._conn.execute(
                    "SELECT * FROM integration_queue "
                    "WHERE project_id = ? AND task_id = ?",
                    (values["project_id"], values["task_id"]),
                ).fetchone()
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self._from_row(row) if row is not None else None

    def replace_task_identity(
        self,
        project_id: str,
        task_id: str,
        *,
        expected_generation: str,
        epic_id: str,
        task_branch: str,
        head_sha: str,
        base_sha: str | None = None,
        priority: int | None = None,
        submitted_at: str | None = None,
    ) -> IntegrationQueueItem | None:
        """Replace one stale unleased row with the current tracker identity.

        Reparenting is a change of integration authority even when the private
        branch and accepted head are unchanged.  This CAS prevents a workflow
        job from silently retaining the former parent epic while also refusing
        to disturb a live legacy queue lease.
        """

        expected = str(expected_generation or "").strip().lower()
        parent = str(epic_id or "").strip()
        branch = str(task_branch or "").strip()
        head = str(head_sha or "").strip()
        if not all((expected, parent, branch, head)):
            return None
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT * FROM integration_queue "
                    "WHERE project_id = ? AND task_id = ?",
                    (str(project_id), str(task_id)),
                ).fetchone()
                if row is None:
                    self._conn.rollback()
                    return None
                item = self._from_row(row)
                if (
                    item.authority_generation() != expected
                    or item.lease_owner is not None
                    or item.task_branch != branch
                    or item.head_sha != head
                ):
                    self._conn.rollback()
                    return None
                self._conn.execute(
                    """
                    UPDATE integration_queue
                       SET epic_id = ?, base_sha = ?, priority = ?,
                           submitted_at = ?, state = 'ready', attempts = 0,
                           lease_owner = NULL, lease_expires_at = NULL,
                           updated_at = ?, last_error = NULL,
                           retry_forced = 0, next_retry_at = NULL,
                           rebased_from_head_sha = NULL, integrated_sha = NULL,
                           rebase_intent_pending = 0,
                           rebased_publication_pending = 0,
                           history_sequence = 0
                     WHERE project_id = ? AND task_id = ?
                       AND lease_owner IS NULL
                    """,
                    (
                        parent,
                        str(base_sha or "").strip() or None,
                        int(priority if priority is not None else 999),
                        submitted_at or item.submitted_at,
                        _now_iso(),
                        str(project_id),
                        str(task_id),
                    ),
                )
                current = self._conn.execute(
                    "SELECT * FROM integration_queue "
                    "WHERE project_id = ? AND task_id = ?",
                    (str(project_id), str(task_id)),
                ).fetchone()
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self._from_row(current) if current is not None else None

    def retire_task_generation(
        self,
        project_id: str,
        task_id: str,
        *,
        expected_generation: str,
        reason: str,
        action: Callable[[IntegrationQueueItem], bool] | None = None,
    ) -> IntegrationQueueItem | None:
        """Retire one exact unleased delivery generation.

        The optional callback runs inside the queue transaction after the exact
        generation check and before retirement.  This is used when a tracker
        parent removal changes a queued submission to standalone delivery: the
        tracker mode is written while replacement queue generations remain
        fenced.  If the process exits after the tracker write but before this
        transaction commits, standalone apply repairs the surviving exact row.
        """

        expected = str(expected_generation or "").strip().lower()
        message = str(reason or "").strip()
        if not expected or not message:
            return None
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT * FROM integration_queue "
                    "WHERE project_id = ? AND task_id = ?",
                    (str(project_id), str(task_id)),
                ).fetchone()
                if row is None:
                    self._conn.rollback()
                    return None
                item = self._from_row(row)
                if (
                    item.authority_generation() != expected
                    or (
                        item.state != "ready"
                        and not (
                            item.state == "cancelled"
                            and item.last_error == message
                        )
                    )
                    or item.lease_owner is not None
                    or item.rebase_intent_pending
                    or item.rebased_publication_pending
                ):
                    self._conn.rollback()
                    return None
                if action is not None and not action(item):
                    self._conn.rollback()
                    return None
                self._conn.execute(
                    """
                    UPDATE integration_queue
                       SET state = 'cancelled', lease_owner = NULL,
                           lease_expires_at = NULL, updated_at = ?,
                           last_error = ?, retry_forced = 0,
                           next_retry_at = NULL,
                           rebase_intent_pending = 0,
                           rebased_publication_pending = 0
                     WHERE project_id = ? AND task_id = ?
                       AND state IN ('ready', 'cancelled')
                       AND lease_owner IS NULL
                    """,
                    (_now_iso(), message, str(project_id), str(task_id)),
                )
                current = self._conn.execute(
                    "SELECT * FROM integration_queue "
                    "WHERE project_id = ? AND task_id = ?",
                    (str(project_id), str(task_id)),
                ).fetchone()
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        retired = self._from_row(current) if current is not None else None
        if (
            retired is None
            or retired.state != "cancelled"
            or retired.last_error != message
        ):
            return None
        return retired

    def prepare_task_rebase(
        self,
        project_id: str,
        task_id: str,
        *,
        expected_generation: str,
        base_sha: str,
    ) -> IntegrationQueueItem | None:
        """Checkpoint executor ownership before mutating a private branch."""

        expected = str(expected_generation or "").strip().lower()
        base = str(base_sha or "").strip().lower()
        if not expected or not base:
            return None
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT * FROM integration_queue "
                    "WHERE project_id = ? AND task_id = ?",
                    (str(project_id), str(task_id)),
                ).fetchone()
                if row is None:
                    self._conn.rollback()
                    return None
                item = self._from_row(row)
                if (
                    item.authority_generation() != expected
                    or item.state != "ready"
                    or item.lease_owner is not None
                    or item.rebased_publication_pending
                ):
                    self._conn.rollback()
                    return None
                if item.rebase_intent_pending:
                    self._conn.commit()
                    return item
                self._conn.execute(
                    """
                    UPDATE integration_queue
                       SET base_sha = ?, rebased_from_head_sha = ?,
                           rebase_intent_pending = 1, updated_at = ?
                     WHERE project_id = ? AND task_id = ?
                       AND state = 'ready' AND lease_owner IS NULL
                       AND rebase_intent_pending = 0
                       AND rebased_publication_pending = 0
                    """,
                    (
                        base,
                        item.head_sha,
                        _now_iso(),
                        str(project_id),
                        str(task_id),
                    ),
                )
                current = self._conn.execute(
                    "SELECT * FROM integration_queue "
                    "WHERE project_id = ? AND task_id = ?",
                    (str(project_id), str(task_id)),
                ).fetchone()
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self._from_row(current) if current is not None else None

    def abort_task_rebase(
        self,
        project_id: str,
        task_id: str,
        *,
        expected_generation: str,
    ) -> IntegrationQueueItem | None:
        """Clear one exact pre-publication intent after a safe Git rollback."""

        expected = str(expected_generation or "").strip().lower()
        if not expected:
            return None
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT * FROM integration_queue "
                    "WHERE project_id = ? AND task_id = ?",
                    (str(project_id), str(task_id)),
                ).fetchone()
                if row is None:
                    self._conn.rollback()
                    return None
                item = self._from_row(row)
                if (
                    item.authority_generation() != expected
                    or item.state != "ready"
                    or item.lease_owner is not None
                    or not item.rebase_intent_pending
                    or item.rebased_publication_pending
                ):
                    self._conn.rollback()
                    return None
                self._conn.execute(
                    """
                    UPDATE integration_queue
                       SET rebase_intent_pending = 0,
                           rebased_from_head_sha = NULL, updated_at = ?
                     WHERE project_id = ? AND task_id = ?
                       AND state = 'ready' AND lease_owner IS NULL
                       AND rebase_intent_pending = 1
                       AND rebased_publication_pending = 0
                    """,
                    (_now_iso(), str(project_id), str(task_id)),
                )
                current = self._conn.execute(
                    "SELECT * FROM integration_queue "
                    "WHERE project_id = ? AND task_id = ?",
                    (str(project_id), str(task_id)),
                ).fetchone()
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self._from_row(current) if current is not None else None

    def prepare_task_publication(
        self,
        project_id: str,
        task_id: str,
        *,
        expected_generation: str,
        head_sha: str,
        base_sha: str | None = None,
    ) -> IntegrationQueueItem | None:
        """Durably prepare one executor-owned private-head publication.

        The intent is written before the remote ref mutation.  A restart may
        therefore finish only this exact old-head -> rebased-head publication;
        an unrelated remote advance is never inferred from an executor status.
        """

        expected = str(expected_generation or "").strip().lower()
        replacement = str(head_sha or "").strip().lower()
        if not expected or not replacement:
            return None
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    """
                    SELECT * FROM integration_queue
                    WHERE project_id = ? AND task_id = ?
                    """,
                    (str(project_id), str(task_id)),
                ).fetchone()
                if row is None:
                    self._conn.rollback()
                    return None
                item = self._from_row(row)
                if (
                    item.authority_generation() != expected
                    or item.state != "ready"
                    or item.lease_owner is not None
                ):
                    self._conn.rollback()
                    return None
                if (
                    item.head_sha.lower() == replacement
                    and item.rebased_publication_pending
                ):
                    self._conn.commit()
                    return item
                if item.rebased_publication_pending:
                    self._conn.rollback()
                    return None
                predecessor = item.rebased_from_head_sha or item.head_sha
                self._conn.execute(
                    """
                    UPDATE integration_queue
                    SET head_sha = ?, base_sha = ?, updated_at = ?,
                        rebased_from_head_sha = ?,
                        rebase_intent_pending = 0,
                        rebased_publication_pending = 1
                    WHERE project_id = ? AND task_id = ?
                      AND state = 'ready' AND lease_owner IS NULL
                    """,
                    (
                        replacement,
                        str(base_sha or "").strip() or item.base_sha,
                        _now_iso(),
                        predecessor,
                        str(project_id),
                        str(task_id),
                    ),
                )
                current = self._conn.execute(
                    """
                    SELECT * FROM integration_queue
                    WHERE project_id = ? AND task_id = ?
                    """,
                    (str(project_id), str(task_id)),
                ).fetchone()
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self._from_row(current) if current is not None else None

    def complete_task_publication(
        self,
        project_id: str,
        task_id: str,
        *,
        expected_generation: str,
        head_sha: str,
    ) -> IntegrationQueueItem | None:
        """Mark one exact prepared private-head publication observable."""

        expected = str(expected_generation or "").strip().lower()
        published = str(head_sha or "").strip().lower()
        if not expected or not published:
            return None
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    """
                    SELECT * FROM integration_queue
                    WHERE project_id = ? AND task_id = ?
                    """,
                    (str(project_id), str(task_id)),
                ).fetchone()
                if row is None:
                    self._conn.rollback()
                    return None
                item = self._from_row(row)
                if (
                    item.authority_generation() != expected
                    or item.state != "ready"
                    or item.lease_owner is not None
                    or not item.rebased_publication_pending
                    or item.rebase_intent_pending
                    or item.head_sha.lower() != published
                    or not item.rebased_from_head_sha
                ):
                    self._conn.rollback()
                    return None
                self._conn.execute(
                    """
                    UPDATE integration_queue
                    SET rebased_publication_pending = 0, updated_at = ?
                    WHERE project_id = ? AND task_id = ?
                      AND state = 'ready' AND lease_owner IS NULL
                      AND head_sha = ? AND rebased_publication_pending = 1
                    """,
                    (_now_iso(), str(project_id), str(task_id), item.head_sha),
                )
                current = self._conn.execute(
                    """
                    SELECT * FROM integration_queue
                    WHERE project_id = ? AND task_id = ?
                    """,
                    (str(project_id), str(task_id)),
                ).fetchone()
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self._from_row(current) if current is not None else None

    # Compatibility name retained for callers/tests that prepare a publication.
    advance_task_generation = prepare_task_publication

    def consume_retry_generation(
        self,
        project_id: str,
        task_id: str,
        *,
        expected_generation: str,
    ) -> tuple[IntegrationQueueItem | None, bool]:
        """Consume one durable forced retry by exact unleased-row CAS.

        Durable workflow jobs do not take the legacy queue lease, so they need
        the same one-shot semantic at their own effect boundary.  The returned
        boolean is ephemeral executor authority; the durable row is already
        clear before the gate can start.
        """

        expected = str(expected_generation or "").strip().lower()
        if not expected:
            return None, False
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    """
                    SELECT * FROM integration_queue
                    WHERE project_id = ? AND task_id = ?
                    """,
                    (str(project_id), str(task_id)),
                ).fetchone()
                if row is None:
                    self._conn.rollback()
                    return None, False
                item = self._from_row(row)
                if (
                    item.authority_generation() != expected
                    or item.state != "ready"
                    or item.lease_owner is not None
                    or item.rebased_publication_pending
                    or item.rebase_intent_pending
                ):
                    self._conn.rollback()
                    return None, False
                consumed = bool(item.retry_forced)
                if consumed:
                    self._conn.execute(
                        """
                        UPDATE integration_queue
                        SET retry_forced = 0, updated_at = ?
                        WHERE project_id = ? AND task_id = ?
                          AND state = 'ready' AND lease_owner IS NULL
                        """,
                        (_now_iso(), str(project_id), str(task_id)),
                    )
                    row = self._conn.execute(
                        """
                        SELECT * FROM integration_queue
                        WHERE project_id = ? AND task_id = ?
                        """,
                        (str(project_id), str(task_id)),
                    ).fetchone()
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return (self._from_row(row) if row is not None else None), consumed

    def recover_expired(self, *, now: float | None = None) -> int:
        timestamp = time.time() if now is None else float(now)
        with self._lock:
            result = self._conn.execute(
                """
                UPDATE integration_queue
                SET state = 'ready', lease_owner = NULL,
                    lease_expires_at = NULL, updated_at = ?
                WHERE state = 'integrating'
                  AND lease_expires_at IS NOT NULL
                  AND lease_expires_at <= ?
                """,
                (_now_iso(), timestamp),
            )
            self._conn.commit()
        return int(result.rowcount)

    def recover_task_generation(
        self,
        project_id: str,
        task_id: str,
        *,
        expected_generation: str,
        now: float | None = None,
    ) -> IntegrationQueueItem | None:
        """Recover one expired legacy lease without claiming a second lease.

        Durable workflow jobs own their own lease.  During the enforce-mode
        migration they may encounter a queue row left in ``integrating`` by a
        legacy process.  This compare-and-swap releases only the exact expired
        row observed by the job; it never performs the project-wide recovery
        sweep and never manufactures integration authority from a live lease.
        """

        expected = str(expected_generation or "").strip().lower()
        if not expected:
            return None
        timestamp = time.time() if now is None else float(now)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    """
                    SELECT * FROM integration_queue
                    WHERE project_id = ? AND task_id = ?
                    """,
                    (str(project_id), str(task_id)),
                ).fetchone()
                if row is None:
                    self._conn.rollback()
                    return None
                item = self._from_row(row)
                if (
                    item.authority_generation() != expected
                    or item.state != "integrating"
                    or item.lease_expires_at is None
                    or item.lease_expires_at > timestamp
                ):
                    self._conn.rollback()
                    return None
                self._conn.execute(
                    """
                    UPDATE integration_queue
                    SET state = 'ready', lease_owner = NULL,
                        lease_expires_at = NULL, updated_at = ?
                    WHERE project_id = ? AND task_id = ?
                      AND state = 'integrating' AND lease_owner = ?
                    """,
                    (
                        _now_iso(),
                        str(project_id),
                        str(task_id),
                        item.lease_owner,
                    ),
                )
                current = self._conn.execute(
                    """
                    SELECT * FROM integration_queue
                    WHERE project_id = ? AND task_id = ?
                    """,
                    (str(project_id), str(task_id)),
                ).fetchone()
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self._from_row(current) if current is not None else None

    def finish_task_generation(
        self,
        project_id: str,
        task_id: str,
        *,
        expected_generation: str,
        state: str,
        error: str | None = None,
        retry_at: float | None = None,
        integrated_sha: str | None = None,
    ) -> IntegrationQueueItem | None:
        """Finish one unleased row by exact observed generation.

        This is the queue evidence checkpoint used by the durable workflow
        worker.  It deliberately accepts only an unleased ``ready`` row: a
        live legacy queue lease remains authoritative until it expires, while
        a replacement submission changes the generation and loses the CAS.
        """

        expected = str(expected_generation or "").strip().lower()
        normalized_state = str(state or "").strip().lower()
        if not expected or normalized_state not in {
            "ready",
            "blocked",
            "integrated",
            "cancelled",
        }:
            return None
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    """
                    SELECT * FROM integration_queue
                    WHERE project_id = ? AND task_id = ?
                    """,
                    (str(project_id), str(task_id)),
                ).fetchone()
                if row is None:
                    self._conn.rollback()
                    return None
                item = self._from_row(row)
                if (
                    item.authority_generation() != expected
                    or item.state != "ready"
                    or item.lease_owner is not None
                    or item.rebased_publication_pending
                    or item.rebase_intent_pending
                ):
                    self._conn.rollback()
                    return None
                history_sequence = (
                    self._next_history_sequence_locked()
                    if normalized_state == "integrated"
                    else 0
                )
                self._conn.execute(
                    """
                    UPDATE integration_queue
                    SET state = ?, lease_owner = NULL, lease_expires_at = NULL,
                        attempts = attempts + 1, updated_at = ?, last_error = ?,
                        retry_forced = 0, next_retry_at = ?,
                        integrated_sha = ?, rebase_intent_pending = 0,
                        rebased_publication_pending = 0,
                        history_sequence = ?
                    WHERE project_id = ? AND task_id = ?
                      AND state = 'ready' AND lease_owner IS NULL
                    """,
                    (
                        normalized_state,
                        _now_iso(),
                        str(error) if error is not None else None,
                        float(retry_at) if retry_at is not None else None,
                        (
                            str(integrated_sha or "").strip() or None
                            if normalized_state == "integrated"
                            else None
                        ),
                        history_sequence,
                        str(project_id),
                        str(task_id),
                    ),
                )
                current = self._conn.execute(
                    """
                    SELECT * FROM integration_queue
                    WHERE project_id = ? AND task_id = ?
                    """,
                    (str(project_id), str(task_id)),
                ).fetchone()
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self._from_row(current) if current is not None else None

    def checkpoint_legacy_integration(
        self,
        project_id: str,
        task_id: str,
        *,
        lease_owner: str,
        expected_task_branch: str,
        expected_head_sha: str,
        rebased_head_sha: str,
        integrated_sha: str,
        base_sha: str | None = None,
    ) -> IntegrationQueueItem | None:
        """Write the legacy executor result queue-first under its exact lease.

        The old path wrote rebased tracker metadata and only then flipped the
        queue state, leaving two irreconcilable heads across either crash gap.
        This single CAS records the old head as predecessor and the landed head
        as both queue authority and replayable integration evidence.
        """

        owner = str(lease_owner or "").strip()
        branch = str(expected_task_branch or "").strip()
        predecessor = str(expected_head_sha or "").strip()
        rebased = str(rebased_head_sha or "").strip()
        landed = str(integrated_sha or "").strip()
        if not all((owner, branch, predecessor, rebased, landed)):
            return None
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT * FROM integration_queue "
                    "WHERE project_id = ? AND task_id = ?",
                    (str(project_id), str(task_id)),
                ).fetchone()
                if row is None:
                    self._conn.rollback()
                    return None
                item = self._from_row(row)
                if (
                    item.state != "integrating"
                    or item.lease_owner != owner
                    or item.task_branch != branch
                    or item.head_sha != predecessor
                ):
                    self._conn.rollback()
                    return None
                history_sequence = self._next_history_sequence_locked()
                self._conn.execute(
                    """
                    UPDATE integration_queue
                       SET state = 'integrated', head_sha = ?, base_sha = ?,
                           rebased_from_head_sha = ?, integrated_sha = ?,
                           history_sequence = ?, lease_owner = NULL,
                           lease_expires_at = NULL, updated_at = ?,
                           last_error = NULL, retry_forced = 0,
                           next_retry_at = NULL,
                           rebase_intent_pending = 0,
                           rebased_publication_pending = 0
                     WHERE project_id = ? AND task_id = ?
                       AND state = 'integrating' AND lease_owner = ?
                       AND task_branch = ? AND head_sha = ?
                    """,
                    (
                        rebased,
                        str(base_sha or "").strip() or item.base_sha,
                        predecessor if predecessor != rebased else item.rebased_from_head_sha,
                        landed,
                        history_sequence,
                        _now_iso(),
                        str(project_id),
                        str(task_id),
                        owner,
                        branch,
                        predecessor,
                    ),
                )
                current = self._conn.execute(
                    "SELECT * FROM integration_queue "
                    "WHERE project_id = ? AND task_id = ?",
                    (str(project_id), str(task_id)),
                ).fetchone()
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self._from_row(current) if current is not None else None

    def normalize_legacy_tracker_checkpoint(
        self,
        project_id: str,
        task_id: str,
        *,
        expected_generation: str,
        task_branch: str,
        head_sha: str,
        integrated_sha: str,
        base_sha: str | None = None,
    ) -> IntegrationQueueItem | None:
        """CAS an exact tracker-first legacy checkpoint into v5 queue form."""

        expected = str(expected_generation or "").strip()
        branch = str(task_branch or "").strip()
        replacement = str(head_sha or "").strip()
        landed = str(integrated_sha or "").strip()
        if not all((expected, branch, replacement, landed)):
            return None
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT * FROM integration_queue "
                    "WHERE project_id = ? AND task_id = ?",
                    (str(project_id), str(task_id)),
                ).fetchone()
                if row is None:
                    self._conn.rollback()
                    return None
                item = self._from_row(row)
                if (
                    item.authority_generation() != expected
                    or item.state not in {"ready", "integrated"}
                    or item.lease_owner is not None
                    or item.task_branch != branch
                    or item.rebased_publication_pending
                    or item.rebase_intent_pending
                ):
                    self._conn.rollback()
                    return None
                # Normalization changes the immutable landing checkpoint. Give
                # it a fresh event position even when a legacy integrated row
                # already had a cursor, otherwise a previously advanced replay
                # cursor could hide the repaired head forever.
                history_sequence = self._next_history_sequence_locked()
                self._conn.execute(
                    """
                    UPDATE integration_queue
                       SET state = 'integrated', head_sha = ?, base_sha = ?,
                           rebased_from_head_sha = ?, integrated_sha = ?,
                           history_sequence = ?, updated_at = ?,
                           last_error = NULL, retry_forced = 0,
                           next_retry_at = NULL,
                           rebase_intent_pending = 0,
                           rebased_publication_pending = 0
                     WHERE project_id = ? AND task_id = ?
                       AND state IN ('ready', 'integrated')
                       AND lease_owner IS NULL
                    """,
                    (
                        replacement,
                        str(base_sha or "").strip() or item.base_sha,
                        item.head_sha if item.head_sha != replacement else item.rebased_from_head_sha,
                        landed,
                        history_sequence,
                        _now_iso(),
                        str(project_id),
                        str(task_id),
                    ),
                )
                current = self._conn.execute(
                    "SELECT * FROM integration_queue "
                    "WHERE project_id = ? AND task_id = ?",
                    (str(project_id), str(task_id)),
                ).fetchone()
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self._from_row(current) if current is not None else None

    def recover_abandoned(self) -> int:
        """Recover all integrating leases as abandoned (e.g., after restart).

        Called at orchestrator startup to clear any integrating rows that
        were left behind by a crashed or shutdown service instance.
        """
        with self._lock:
            result = self._conn.execute(
                """
                UPDATE integration_queue
                SET state = 'ready', lease_owner = NULL,
                    lease_expires_at = NULL, updated_at = ?
                WHERE state = 'integrating'
                """,
                (_now_iso(),),
            )
            self._conn.commit()
        return int(result.rowcount)

    def claim_next(
        self,
        *,
        project_id: str,
        epic_id: str,
        lease_owner: str,
        dependency_map: Mapping[str, Sequence[str]],
        satisfied: set[str],
        lease_seconds: int = 3600,
        now: float | None = None,
        max_attempts: int | None = None,
    ) -> IntegrationQueueItem | None:
        """Claim the first deterministic dependency-ready item."""

        timestamp = time.time() if now is None else float(now)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute(
                    """
                    UPDATE integration_queue
                    SET state = 'ready', lease_owner = NULL,
                        lease_expires_at = NULL, updated_at = ?
                    WHERE state = 'integrating'
                      AND lease_expires_at IS NOT NULL
                      AND lease_expires_at <= ?
                    """,
                    (_now_iso(), timestamp),
                )
                rows = self._conn.execute(
                    """
                    SELECT * FROM integration_queue
                    WHERE project_id = ? AND epic_id = ? AND state = 'ready'
                      AND (next_retry_at IS NULL OR next_retry_at <= ?)
                    ORDER BY priority, submitted_at, task_id
                    """,
                    (project_id, epic_id, timestamp),
                ).fetchall()
                selected = next(
                    (
                        row
                        for row in rows
                        if max_attempts is None
                        or int(row["attempts"]) < max(1, int(max_attempts))
                        if set(dependency_map.get(row["task_id"], ()))
                        <= satisfied
                    ),
                    None,
                )
                if selected is None:
                    self._conn.commit()
                    return None
                expires = timestamp + max(1, int(lease_seconds))
                updated_at = _now_iso()
                result = self._conn.execute(
                    """
                    UPDATE integration_queue
                    SET state = 'integrating', lease_owner = ?,
                        lease_expires_at = ?, attempts = attempts + 1,
                        updated_at = ?, retry_forced = 0, next_retry_at = NULL
                    WHERE project_id = ? AND task_id = ? AND state = 'ready'
                    """,
                    (
                        lease_owner,
                        expires,
                        updated_at,
                        project_id,
                        selected["task_id"],
                    ),
                )
                if result.rowcount != 1:
                    self._conn.rollback()
                    return None
                row = self._conn.execute(
                    """
                    SELECT * FROM integration_queue
                    WHERE project_id = ? AND task_id = ?
                    """,
                    (project_id, selected["task_id"]),
                ).fetchone()
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        if row is None:
            return None
        claimed = self._from_row(row)
        # Preserve OOMPAH-838 exactly: consume retry_forced atomically with the
        # claim, returning its pre-claim value only to this executor.
        if bool(selected["retry_forced"]):
            claimed = replace(claimed, claimed_retry_forced=True)
        return claimed

    def complete(
        self,
        project_id: str,
        task_id: str,
        *,
        lease_owner: str,
    ) -> bool:
        return self._finish(
            project_id,
            task_id,
            lease_owner=lease_owner,
            state="integrated",
            last_error=None,
        )

    def fail(
        self,
        project_id: str,
        task_id: str,
        *,
        lease_owner: str,
        error: str,
        retryable: bool = False,
        retry_at: float | None = None,
    ) -> bool:
        return self._finish(
            project_id,
            task_id,
            lease_owner=lease_owner,
            state="ready" if retryable else "blocked",
            last_error=str(error),
            next_retry_at=(float(retry_at) if retryable and retry_at is not None else None),
        )

    def cancel(
        self,
        project_id: str,
        task_id: str,
        *,
        reason: str | None = None,
        expected_head_sha: str | None = None,
        expected_state: str | None = None,
    ) -> bool:
        """Retire a stale nonterminal row and invalidate any active lease.

        Keeping the row as ``cancelled`` preserves delivery history while the
        state predicate prevents a late executor from completing or failing
        the invalidated lease.
        """

        with self._lock:
            result = self._conn.execute(
                """
                UPDATE integration_queue
                SET state = 'cancelled', lease_owner = NULL,
                    lease_expires_at = NULL, updated_at = ?, last_error = ?,
                    next_retry_at = NULL
                WHERE project_id = ? AND task_id = ?
                  AND state IN ('ready', 'integrating', 'blocked')
                  AND (? IS NULL OR head_sha = ?)
                  AND (? IS NULL OR state = ?)
                """,
                (
                    _now_iso(),
                    str(reason or "").strip() or None,
                    project_id,
                    task_id,
                    expected_head_sha,
                    expected_head_sha,
                    expected_state,
                    expected_state,
                ),
            )
            self._conn.commit()
        return bool(result.rowcount)

    def restore_cancelled(
        self,
        project_id: str,
        task_id: str,
        *,
        expected_head_sha: str,
        expected_task_branch: str,
        expected_epic_id: str | None = None,
        expected_generation: str | None = None,
    ) -> bool:
        """Rearm one exact cycle-fenced row with a compare-and-swap.

        A normal ``enqueue(..., explicit_retry=True)`` is intentionally
        allowed to replace an inactive row during a fresh submission.  Repair
        reconciliation has a narrower contract: it may only restore the row
        it fenced, and must not overwrite a new private head that won a race
        while Git was being repaired.
        """

        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT * FROM integration_queue "
                    "WHERE project_id = ? AND task_id = ?",
                    (project_id, task_id),
                ).fetchone()
                item = self._from_row(row) if row is not None else None
                if (
                    item is None
                    or item.state != "cancelled"
                    or item.task_branch != expected_task_branch
                    or item.head_sha != expected_head_sha
                    or (
                        expected_epic_id is not None
                        and item.epic_id != expected_epic_id
                    )
                    or (
                        expected_generation is not None
                        and item.authority_generation() != expected_generation
                    )
                ):
                    self._conn.rollback()
                    return False
                result = self._conn.execute(
                    """
                    UPDATE integration_queue
                    SET state = 'ready', lease_owner = NULL,
                        lease_expires_at = NULL, updated_at = ?, last_error = NULL,
                        retry_forced = 0, next_retry_at = NULL
                    WHERE project_id = ? AND task_id = ?
                      AND state = 'cancelled'
                      AND task_branch = ? AND head_sha = ?
                    """,
                    (
                        _now_iso(),
                        project_id,
                        task_id,
                        expected_task_branch,
                        expected_head_sha,
                    ),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return bool(result.rowcount)

    def _finish(
        self,
        project_id: str,
        task_id: str,
        *,
        lease_owner: str,
        state: str,
        last_error: str | None,
        next_retry_at: float | None = None,
    ) -> bool:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                owned = self._conn.execute(
                    """
                    SELECT 1 FROM integration_queue
                    WHERE project_id = ? AND task_id = ?
                      AND state = 'integrating' AND lease_owner = ?
                    """,
                    (project_id, task_id, lease_owner),
                ).fetchone()
                if owned is None:
                    self._conn.rollback()
                    return False
                history_sequence = (
                    self._next_history_sequence_locked()
                    if state == "integrated"
                    else 0
                )
                result = self._conn.execute(
                    """
                    UPDATE integration_queue
                    SET state = ?, lease_owner = NULL, lease_expires_at = NULL,
                        updated_at = ?, last_error = ?, next_retry_at = ?,
                        history_sequence = ?
                    WHERE project_id = ? AND task_id = ?
                      AND state = 'integrating' AND lease_owner = ?
                    """,
                    (
                        state,
                        _now_iso(),
                        last_error,
                        next_retry_at,
                        history_sequence,
                        project_id,
                        task_id,
                        lease_owner,
                    ),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return bool(result.rowcount)

    def owns_active_lease(
        self,
        *,
        project_id: str,
        task_id: str,
        task_branch: str,
        head_sha: str,
        lease_owner: str | None,
        now: float | None = None,
    ) -> bool:
        """Return whether an executor still owns this exact integration row.

        Tracker status alone cannot distinguish an expired lease from the
        replacement executor that reclaimed the same Ready-to-Integrate
        submission.  The executor must therefore retain the durable queue
        authority it was claimed with: an ``integrating`` row for the same
        project, task, branch, head, and lease owner.
        """

        values = {
            "project_id": str(project_id or "").strip(),
            "task_id": str(task_id or "").strip(),
            "task_branch": str(task_branch or "").strip(),
            "head_sha": str(head_sha or "").strip(),
            "lease_owner": str(lease_owner or "").strip(),
        }
        if not all(values.values()):
            return False
        observed_at: float | None = None
        if now is not None:
            try:
                observed_at = float(now)
            except (TypeError, ValueError, OverflowError):
                return False
            if not math.isfinite(observed_at):
                return False
        with self._lock:
            row = self._conn.execute(
                """
                SELECT lease_expires_at FROM integration_queue
                WHERE project_id = ? AND task_id = ?
                  AND task_branch = ? AND head_sha = ?
                  AND state = 'integrating' AND lease_owner = ?
                """,
                (
                    values["project_id"],
                    values["task_id"],
                    values["task_branch"],
                    values["head_sha"],
                    values["lease_owner"],
                ),
            ).fetchone()
            # Sample the production clock while the same lock still protects
            # the row read.  A caller delayed on this lock cannot return old
            # authority merely because its invocation began before expiry.
            if observed_at is None:
                observed_at = float(time.time())
        if row is None:
            return False
        expires_at = row["lease_expires_at"]
        if (
            isinstance(expires_at, bool)
            or not isinstance(expires_at, (int, float))
        ):
            return False
        deadline = float(expires_at)
        return (
            math.isfinite(observed_at)
            and math.isfinite(deadline)
            and deadline > observed_at
        )

    def get(
        self,
        project_id: str,
        task_id: str,
    ) -> IntegrationQueueItem | None:
        """Return one queue row without scanning historical siblings."""

        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM integration_queue
                WHERE project_id = ? AND task_id = ?
                """,
                (str(project_id), str(task_id)),
            ).fetchone()
        return self._from_row(row) if row is not None else None

    def run_if_generation(
        self,
        project_id: str,
        task_id: str,
        *,
        expected_generation: str,
        action: Callable[[IntegrationQueueItem], bool],
    ) -> bool:
        """Run ``action`` only while one exact queue row is unchanged.

        ``BEGIN IMMEDIATE`` fences other SQLite connections and ``_lock``
        fences callers sharing this store.  The callback is deliberately run
        inside that authority window so a gate completion, retry, cancellation,
        or replacement submission cannot land between the watchdog's final
        comparison and its tracker status write.
        """

        expected = str(expected_generation or "").strip().lower()
        if not expected:
            return False
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    """
                    SELECT * FROM integration_queue
                    WHERE project_id = ? AND task_id = ?
                    """,
                    (str(project_id), str(task_id)),
                ).fetchone()
                if row is None:
                    self._conn.rollback()
                    return False
                item = self._from_row(row)
                if item.authority_generation() != expected:
                    self._conn.rollback()
                    return False
                if not action(item):
                    self._conn.rollback()
                    return False
                current = self._conn.execute(
                    """
                    SELECT * FROM integration_queue
                    WHERE project_id = ? AND task_id = ?
                    """,
                    (str(project_id), str(task_id)),
                ).fetchone()
                if (
                    current is None
                    or self._from_row(current).authority_generation() != expected
                ):
                    self._conn.rollback()
                    return False
                self._conn.commit()
                return True
            except Exception:
                self._conn.rollback()
                raise

    def run_if_absent(
        self,
        project_id: str,
        task_id: str,
        *,
        action: Callable[[], bool],
    ) -> bool:
        """Run ``action`` only while this task has no durable queue row.

        Historical/manual stalled tasks may legitimately predate the
        integration queue.  Their compatibility reopen must still fence row
        creation, otherwise a replacement submission can become authoritative
        between an absence check and the tracker status write.
        """

        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    """
                    SELECT 1 FROM integration_queue
                    WHERE project_id = ? AND task_id = ?
                    """,
                    (str(project_id), str(task_id)),
                ).fetchone()
                if row is not None:
                    self._conn.rollback()
                    return False
                if not action():
                    self._conn.rollback()
                    return False
                current = self._conn.execute(
                    """
                    SELECT 1 FROM integration_queue
                    WHERE project_id = ? AND task_id = ?
                    """,
                    (str(project_id), str(task_id)),
                ).fetchone()
                if current is not None:
                    self._conn.rollback()
                    return False
                self._conn.commit()
                return True
            except Exception:
                self._conn.rollback()
                raise

    def items(
        self,
        *,
        project_id: str | None = None,
        epic_id: str | None = None,
        states: Sequence[str] | None = None,
        limit: int | None = None,
        after: str | None = None,
    ) -> list[IntegrationQueueItem]:
        """Return queue rows in stable order, optionally using a keyset cursor.

        Integrated rows are ordered by the monotonic history sequence assigned
        when that exact landing checkpoint is written. Mutable epic, priority,
        and submission fields can therefore never move a row behind the cursor.
        """

        clauses: list[str] = []
        params: list[object] = []
        history_order = after is not None
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        if epic_id is not None:
            clauses.append("epic_id = ?")
            params.append(epic_id)
        if states is not None:
            state_values = (
                (states,) if isinstance(states, str) else tuple(states)
            )
            if not state_values:
                return []
            history_order = history_order or {
                str(value).strip().lower() for value in state_values
            } == {"integrated"}
            placeholders = ", ".join("?" for _ in state_values)
            clauses.append(f"state IN ({placeholders})")
            params.extend(str(value) for value in state_values)
        if after is not None:
            cursor = self._decode_cursor(after)
            if cursor is not None:
                clauses.append("history_sequence > ?")
                params.append(cursor)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_clause = ""
        if limit is not None:
            limit_clause = " LIMIT ?"
            params.append(max(int(limit), 0))
        with self._lock:
            order_by = (
                "history_sequence, project_id, task_id"
                if history_order
                else "project_id, epic_id, priority, submitted_at, task_id"
            )
            rows = self._conn.execute(
                f"""
                SELECT * FROM integration_queue
                {where}
                ORDER BY {order_by}
                {limit_clause}
                """,
                params,
            ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def cursor_for(item: IntegrationQueueItem) -> str:
        """Return an opaque durable cursor positioned after *item*."""

        return json.dumps(int(item.history_sequence), separators=(",", ":"))

    @staticmethod
    def _decode_cursor(cursor: str) -> int | None:
        try:
            values = json.loads(cursor)
            if isinstance(values, bool) or not isinstance(values, int) or values < 0:
                return None
            return values
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
