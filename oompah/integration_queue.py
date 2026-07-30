"""Restart-safe per-epic integration queue with expiring leases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
import sqlite3
import threading
import time
from typing import Mapping, Sequence


INTEGRATION_QUEUE_SCHEMA_VERSION = 1
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

    def to_dict(self) -> dict[str, object]:
        return {
            key: getattr(self, key)
            for key in self.__dataclass_fields__
        }


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
    ) -> IntegrationQueueItem:
        """Insert or refresh a submission; identical resubmits are idempotent.
        
        When explicit_retry=True, clears blocked state even for unchanged head/branch,
        allowing explicit user retries while background sync remains idempotent.
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
            if (
                existing is not None
                and existing["head_sha"] == values["head_sha"]
                and existing["task_branch"] == values["task_branch"]
                and not explicit_retry
            ):
                return self._from_row(existing)
            self._conn.execute(
                """
                INSERT INTO integration_queue(
                    project_id, epic_id, task_id, task_branch, head_sha,
                    base_sha, priority, submitted_at, state, attempts,
                    lease_owner, lease_expires_at, updated_at, last_error
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'ready', 0, NULL, NULL, ?, NULL)
                ON CONFLICT(project_id, task_id) DO UPDATE SET
                    epic_id = excluded.epic_id,
                    task_branch = excluded.task_branch,
                    head_sha = excluded.head_sha,
                    base_sha = excluded.base_sha,
                    priority = excluded.priority,
                    submitted_at = excluded.submitted_at,
                    state = 'ready',
                    attempts = 0,
                    lease_owner = NULL,
                    lease_expires_at = NULL,
                    updated_at = excluded.updated_at,
                    last_error = NULL
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
                    ORDER BY priority, submitted_at, task_id
                    """,
                    (project_id, epic_id),
                ).fetchall()
                selected = next(
                    (
                        row
                        for row in rows
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
                        updated_at = ?
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
    ) -> bool:
        return self._finish(
            project_id,
            task_id,
            lease_owner=lease_owner,
            state="ready" if retryable else "blocked",
            last_error=str(error),
        )

    def _finish(
        self,
        project_id: str,
        task_id: str,
        *,
        lease_owner: str,
        state: str,
        last_error: str | None,
    ) -> bool:
        with self._lock:
            result = self._conn.execute(
                """
                UPDATE integration_queue
                SET state = ?, lease_owner = NULL, lease_expires_at = NULL,
                    updated_at = ?, last_error = ?
                WHERE project_id = ? AND task_id = ?
                  AND state = 'integrating' AND lease_owner = ?
                """,
                (
                    state,
                    _now_iso(),
                    last_error,
                    project_id,
                    task_id,
                    lease_owner,
                ),
            )
            self._conn.commit()
        return bool(result.rowcount)

    def items(
        self,
        *,
        project_id: str | None = None,
        epic_id: str | None = None,
    ) -> list[IntegrationQueueItem]:
        clauses: list[str] = []
        params: list[object] = []
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        if epic_id is not None:
            clauses.append("epic_id = ?")
            params.append(epic_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT * FROM integration_queue
                {where}
                ORDER BY project_id, epic_id, priority, submitted_at, task_id
                """,
                params,
            ).fetchall()
        return [self._from_row(row) for row in rows]
