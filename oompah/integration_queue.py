"""Restart-safe per-epic integration queue with expiring leases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import sqlite3
import threading
import time
from typing import Callable, Mapping, Sequence


INTEGRATION_QUEUE_SCHEMA_VERSION = 2
_INITIALIZE_LOCK = threading.Lock()


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

    def to_dict(self) -> dict[str, object]:
        return {
            key: getattr(self, key)
            for key in self.__dataclass_fields__
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
        )

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
                    retry_forced, next_retry_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, NULL, NULL, ?, NULL, ?, ?)
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
                    next_retry_at = excluded.next_retry_at
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
                self._conn.commit()
                row = self._conn.execute(
                    """
                    SELECT * FROM integration_queue
                    WHERE project_id = ? AND task_id = ?
                    """,
                    (project_id, selected["task_id"]),
                ).fetchone()
            except Exception:
                self._conn.rollback()
                raise
        return self._from_row(row) if row is not None else None

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
    ) -> bool:
        """Rearm one exact cycle-fenced row with a compare-and-swap.

        A normal ``enqueue(..., explicit_retry=True)`` is intentionally
        allowed to replace an inactive row during a fresh submission.  Repair
        reconciliation has a narrower contract: it may only restore the row
        it fenced, and must not overwrite a new private head that won a race
        while Git was being repaired.
        """

        with self._lock:
            result = self._conn.execute(
                """
                UPDATE integration_queue
                SET state = 'ready', lease_owner = NULL,
                    lease_expires_at = NULL, updated_at = ?, last_error = NULL,
                    retry_forced = 0, next_retry_at = NULL
                WHERE project_id = ? AND task_id = ?
                  AND state = 'cancelled'
                  AND task_branch = ? AND head_sha = ?
                  AND (? IS NULL OR epic_id = ?)
                """,
                (
                    _now_iso(),
                    project_id,
                    task_id,
                    expected_task_branch,
                    expected_head_sha,
                    expected_epic_id,
                    expected_epic_id,
                ),
            )
            self._conn.commit()
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
            result = self._conn.execute(
                """
                UPDATE integration_queue
                SET state = ?, lease_owner = NULL, lease_expires_at = NULL,
                    updated_at = ?, last_error = ?, next_retry_at = ?
                WHERE project_id = ? AND task_id = ?
                  AND state = 'integrating' AND lease_owner = ?
                """,
                (
                    state,
                    _now_iso(),
                    last_error,
                    next_retry_at,
                    project_id,
                    task_id,
                    lease_owner,
                ),
            )
            self._conn.commit()
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

        The cursor is deliberately based on the full ordering key rather than
        ``updated_at``.  Queue rows can be refreshed or retried while a scan
        is in progress, but a durable cursor must still advance through the
        historical integrated rows without offset pagination skipping rows.
        """

        clauses: list[str] = []
        params: list[object] = []
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
            placeholders = ", ".join("?" for _ in state_values)
            clauses.append(f"state IN ({placeholders})")
            params.extend(str(value) for value in state_values)
        if after is not None:
            cursor = self._decode_cursor(after)
            if cursor is not None:
                clauses.append(
                    "(project_id, epic_id, priority, submitted_at, task_id) "
                    "> (?, ?, ?, ?, ?)"
                )
                params.extend(cursor)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_clause = ""
        if limit is not None:
            limit_clause = " LIMIT ?"
            params.append(max(int(limit), 0))
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT * FROM integration_queue
                {where}
                ORDER BY project_id, epic_id, priority, submitted_at, task_id
                {limit_clause}
                """,
                params,
            ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def cursor_for(item: IntegrationQueueItem) -> str:
        """Return an opaque durable cursor positioned after *item*."""

        return json.dumps(
            [
                str(item.project_id),
                str(item.epic_id),
                int(item.priority),
                str(item.submitted_at),
                str(item.task_id),
            ],
            separators=(",", ":"),
        )

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[str, str, int, str, str] | None:
        try:
            values = json.loads(cursor)
            if not isinstance(values, list) or len(values) != 5:
                return None
            project_id, epic_id, priority, submitted_at, task_id = values
            if not all(
                isinstance(value, str)
                for value in (project_id, epic_id, submitted_at, task_id)
            ):
                return None
            return (
                project_id,
                epic_id,
                int(priority),
                submitted_at,
                task_id,
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
