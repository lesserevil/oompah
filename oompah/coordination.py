"""Durable, provider-neutral coordination between concurrent task workers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import sqlite3
import threading
import uuid
from typing import Iterable, Mapping, Sequence

from oompah.dependency_graph import effective_dependencies, issue_index
from oompah.models import Issue
from oompah.statuses import is_terminal_status


COORDINATION_SCHEMA_VERSION = 2
MAX_MESSAGE_BYTES = 16 * 1024
MAX_CHANGED_PATHS = 256
_INITIALIZE_LOCK = threading.Lock()


@dataclass(frozen=True)
class CoordinationMessage:
    """One durable message in a managed project's coordination timeline."""

    id: str
    project_id: str
    sender_task: str
    recipient_task: str
    kind: str
    text: str
    changed_paths: tuple[str, ...]
    commit_sha: str | None
    created_at: str
    delivered_at: str | None = None
    read_at: str | None = None
    idempotency_key: str | None = None
    sender_run_id: str | None = None
    recipient_run_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "sender_task": self.sender_task,
            "recipient_task": self.recipient_task,
            "kind": self.kind,
            "text": self.text,
            "changed_paths": list(self.changed_paths),
            "commit_sha": self.commit_sha,
            "created_at": self.created_at,
            "delivered_at": self.delivered_at,
            "read_at": self.read_at,
            "idempotency_key": self.idempotency_key,
            "sender_run_id": self.sender_run_id,
            "recipient_run_id": self.recipient_run_id,
        }


@dataclass(frozen=True)
class PeerSuggestion:
    """A task an agent may contact, with deterministic advisory reasons."""

    identifier: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {"identifier": self.identifier, "reasons": list(self.reasons)}


_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS coordination_messages (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    sender_task TEXT NOT NULL,
    recipient_task TEXT NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    changed_paths TEXT NOT NULL DEFAULT '[]',
    commit_sha TEXT,
    created_at TEXT NOT NULL,
    delivered_at TEXT,
    read_at TEXT,
    idempotency_key TEXT,
    sender_run_id TEXT,
    recipient_run_id TEXT,
    UNIQUE(project_id, sender_task, idempotency_key)
);
CREATE INDEX IF NOT EXISTS coordination_inbox_idx
    ON coordination_messages(project_id, recipient_task, created_at, id);
CREATE INDEX IF NOT EXISTS coordination_created_idx
    ON coordination_messages(created_at, id);
CREATE TABLE IF NOT EXISTS coordination_checkpoints (
    project_id TEXT NOT NULL,
    task_identifier TEXT NOT NULL,
    changed_paths TEXT NOT NULL DEFAULT '[]',
    commit_sha TEXT,
    summary TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(project_id, task_identifier)
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_identifier(value: object, *, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _clean_paths(paths: Iterable[object] | None) -> tuple[str, ...]:
    cleaned = tuple(
        sorted(
            {
                str(path).strip()
                for path in (paths or ())
                if str(path).strip()
            }
        )
    )
    if len(cleaned) > MAX_CHANGED_PATHS:
        raise ValueError(
            f"changed_paths is limited to {MAX_CHANGED_PATHS} entries"
        )
    return cleaned


class CoordinationStore:
    """Thread-safe SQLite message store with idempotent writes."""

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
        # Several orchestrators can be constructed concurrently in tests and
        # during process-local reloads.  SQLite's WAL transition takes an
        # exclusive schema lock, so serialize only this short initialization
        # section; normal reads and writes remain independently concurrent.
        with _INITIALIZE_LOCK, self._lock:
            self._conn.execute("PRAGMA busy_timeout=10000")
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)
            columns = {
                str(row["name"])
                for row in self._conn.execute(
                    "PRAGMA table_info(coordination_messages)"
                ).fetchall()
            }
            for column in ("sender_run_id", "recipient_run_id"):
                if column not in columns:
                    self._conn.execute(
                        f"ALTER TABLE coordination_messages "
                        f"ADD COLUMN {column} TEXT"
                    )
            self._conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
                ("version", str(COORDINATION_SCHEMA_VERSION)),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _ensure_conn(self) -> None:
        """Re-open the connection if it was closed, preventing 'closed database' errors.
        
        This handles the race condition where an orchestrator is replaced and the
        old store may be garbage collected while API threads still hold references
        to it and try to access it.
        """
        try:
            # Test if the connection is alive by executing a simple query
            self._conn.execute("SELECT 1")
        except sqlite3.ProgrammingError:
            # Connection is closed, re-open it
            self._conn = sqlite3.connect(
                self.path,
                check_same_thread=False,
                timeout=10,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA busy_timeout=10000")
            self._conn.execute("PRAGMA journal_mode=WAL")

    @property
    def schema_version(self) -> int:
        with self._lock:
            self._ensure_conn()
            row = self._conn.execute(
                "SELECT value FROM schema_meta WHERE key = 'version'"
            ).fetchone()
        return int(row["value"]) if row else 0

    @staticmethod
    def _from_row(row: sqlite3.Row) -> CoordinationMessage:
        try:
            raw_paths = json.loads(row["changed_paths"])
        except (TypeError, json.JSONDecodeError):
            raw_paths = []
        return CoordinationMessage(
            id=row["id"],
            project_id=row["project_id"],
            sender_task=row["sender_task"],
            recipient_task=row["recipient_task"],
            kind=row["kind"],
            text=row["text"],
            changed_paths=tuple(str(path) for path in raw_paths),
            commit_sha=row["commit_sha"],
            created_at=row["created_at"],
            delivered_at=row["delivered_at"],
            read_at=row["read_at"],
            idempotency_key=row["idempotency_key"],
            sender_run_id=row["sender_run_id"],
            recipient_run_id=row["recipient_run_id"],
        )

    def append(
        self,
        *,
        project_id: str,
        sender_task: str,
        recipient_task: str,
        text: str,
        kind: str = "message",
        changed_paths: Iterable[object] | None = None,
        commit_sha: str | None = None,
        idempotency_key: str | None = None,
        sender_run_id: str | None = None,
        recipient_run_id: str | None = None,
    ) -> CoordinationMessage:
        """Append a message, returning the prior row on an idempotent retry."""

        project = _clean_identifier(project_id, name="project_id")
        sender = _clean_identifier(sender_task, name="sender_task")
        recipient = _clean_identifier(
            recipient_task, name="recipient_task"
        )
        clean_kind = _clean_identifier(kind, name="kind").lower()
        clean_text = str(text or "").strip()
        if not clean_text:
            raise ValueError("text is required")
        if len(clean_text.encode("utf-8")) > MAX_MESSAGE_BYTES:
            raise ValueError(
                f"text is limited to {MAX_MESSAGE_BYTES} UTF-8 bytes"
            )
        paths = _clean_paths(changed_paths)
        clean_key = str(idempotency_key or "").strip() or None
        created_at = _now_iso()
        message_id = uuid.uuid4().hex
        with self._lock:
            self._ensure_conn()
            if clean_key:
                existing = self._conn.execute(
                    """
                    SELECT * FROM coordination_messages
                    WHERE project_id = ? AND sender_task = ?
                      AND idempotency_key = ?
                    """,
                    (project, sender, clean_key),
                ).fetchone()
                if existing is not None:
                    return self._from_row(existing)
            self._conn.execute(
                """
                INSERT INTO coordination_messages(
                    id, project_id, sender_task, recipient_task, kind, text,
                    changed_paths, commit_sha, created_at, idempotency_key,
                    sender_run_id, recipient_run_id
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    project,
                    sender,
                    recipient,
                    clean_kind,
                    clean_text,
                    json.dumps(paths),
                    str(commit_sha or "").strip() or None,
                    created_at,
                    clean_key,
                    str(sender_run_id or "").strip() or None,
                    str(recipient_run_id or "").strip() or None,
                ),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM coordination_messages WHERE id = ?",
                (message_id,),
            ).fetchone()
        assert row is not None
        return self._from_row(row)

    def inbox(
        self,
        project_id: str,
        recipient_task: str,
        *,
        unread_only: bool = False,
        after_id: str | None = None,
        limit: int = 100,
    ) -> list[CoordinationMessage]:
        """Return a task inbox in stable FIFO order."""

        project = _clean_identifier(project_id, name="project_id")
        recipient = _clean_identifier(
            recipient_task, name="recipient_task"
        )
        clauses = ["project_id = ?", "recipient_task = ?"]
        params: list[object] = [project, recipient]
        if unread_only:
            clauses.append("read_at IS NULL")
        if after_id:
            cursor = self.get(after_id)
            if cursor is not None:
                clauses.append("(created_at, id) > (?, ?)")
                params.extend([cursor.created_at, cursor.id])
        params.append(max(1, min(int(limit), 500)))
        with self._lock:
            self._ensure_conn()
            rows = self._conn.execute(
                f"""
                SELECT * FROM coordination_messages
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at, id
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def timeline(
        self,
        project_id: str,
        task_identifier: str,
        *,
        limit: int = 100,
    ) -> list[CoordinationMessage]:
        """Return messages sent or received by one task."""

        project = _clean_identifier(project_id, name="project_id")
        task = _clean_identifier(task_identifier, name="task_identifier")
        with self._lock:
            self._ensure_conn()
            rows = self._conn.execute(
                """
                SELECT * FROM coordination_messages
                WHERE project_id = ?
                  AND (sender_task = ? OR recipient_task = ?)
                ORDER BY created_at, id
                LIMIT ?
                """,
                (project, task, task, max(1, min(int(limit), 500))),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def get(self, message_id: str) -> CoordinationMessage | None:
        with self._lock:
            self._ensure_conn()
            row = self._conn.execute(
                "SELECT * FROM coordination_messages WHERE id = ?",
                (str(message_id),),
            ).fetchone()
        return self._from_row(row) if row is not None else None

    def mark_delivered(self, message_id: str) -> bool:
        return self._mark(message_id, "delivered_at")

    def mark_read(self, message_id: str) -> bool:
        return self._mark(message_id, "read_at")

    def _mark(self, message_id: str, column: str) -> bool:
        if column not in {"delivered_at", "read_at"}:
            raise ValueError("unsupported coordination marker")
        with self._lock:
            self._ensure_conn()
            result = self._conn.execute(
                f"""
                UPDATE coordination_messages
                SET {column} = COALESCE({column}, ?)
                WHERE id = ?
                """,
                (_now_iso(), str(message_id)),
            )
            self._conn.commit()
        return bool(result.rowcount)

    def unread_count(self, project_id: str, recipient_task: str) -> int:
        with self._lock:
            self._ensure_conn()
            row = self._conn.execute(
                """
                SELECT COUNT(*) AS count FROM coordination_messages
                WHERE project_id = ? AND recipient_task = ?
                  AND read_at IS NULL
                """,
                (str(project_id), str(recipient_task)),
            ).fetchone()
        return int(row["count"]) if row else 0

    def checkpoint(
        self,
        *,
        project_id: str,
        task_identifier: str,
        changed_paths: Iterable[object] | None = None,
        commit_sha: str | None = None,
        summary: str | None = None,
    ) -> dict[str, object]:
        """Persist the latest changed-path checkpoint for one active task."""

        project = _clean_identifier(project_id, name="project_id")
        task = _clean_identifier(
            task_identifier, name="task_identifier"
        )
        paths = _clean_paths(changed_paths)
        updated_at = _now_iso()
        with self._lock:
            self._ensure_conn()
            self._conn.execute(
                """
                INSERT INTO coordination_checkpoints(
                    project_id, task_identifier, changed_paths, commit_sha,
                    summary, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, task_identifier) DO UPDATE SET
                    changed_paths = excluded.changed_paths,
                    commit_sha = excluded.commit_sha,
                    summary = excluded.summary,
                    updated_at = excluded.updated_at
                """,
                (
                    project,
                    task,
                    json.dumps(paths),
                    str(commit_sha or "").strip() or None,
                    str(summary or "").strip() or None,
                    updated_at,
                ),
            )
            self._conn.commit()
        return {
            "project_id": project,
            "task_identifier": task,
            "changed_paths": list(paths),
            "commit_sha": str(commit_sha or "").strip() or None,
            "summary": str(summary or "").strip() or None,
            "updated_at": updated_at,
        }

    def checkpoints(self, project_id: str) -> dict[str, dict[str, object]]:
        """Return the latest task checkpoints for one project."""

        with self._lock:
            self._ensure_conn()
            rows = self._conn.execute(
                """
                SELECT * FROM coordination_checkpoints
                WHERE project_id = ?
                ORDER BY task_identifier
                """,
                (str(project_id),),
            ).fetchall()
        result: dict[str, dict[str, object]] = {}
        for row in rows:
            try:
                paths = json.loads(row["changed_paths"])
            except (TypeError, json.JSONDecodeError):
                paths = []
            result[row["task_identifier"]] = {
                "changed_paths": [str(path) for path in paths],
                "commit_sha": row["commit_sha"],
                "summary": row["summary"],
                "updated_at": row["updated_at"],
            }
        return result

    def prune_before(self, cutoff_iso: str, *, limit: int = 1000) -> int:
        """Delete old read messages in bounded batches."""

        with self._lock:
            self._ensure_conn()
            rows = self._conn.execute(
                """
                SELECT id FROM coordination_messages
                WHERE read_at IS NOT NULL AND created_at < ?
                ORDER BY created_at, id
                LIMIT ?
                """,
                (str(cutoff_iso), max(1, int(limit))),
            ).fetchall()
            ids = [row["id"] for row in rows]
            if ids:
                placeholders = ",".join("?" for _ in ids)
                self._conn.execute(
                    f"DELETE FROM coordination_messages WHERE id IN ({placeholders})",
                    ids,
                )
                self._conn.commit()
        return len(ids)


def derive_peer_suggestions(
    issue: Issue,
    issues: Sequence[Issue],
    *,
    changed_paths: Mapping[str, Iterable[str]] | None = None,
) -> list[PeerSuggestion]:
    """Derive deterministic advisory peers from graph, ancestry, and overlap."""

    own_ids = {
        str(value).strip()
        for value in (issue.id, issue.identifier)
        if str(value or "").strip()
    }
    if not own_ids:
        return []
    project_id = str(issue.project_id or "").strip()
    changed = {
        key: set(_clean_paths(paths))
        for key, paths in (changed_paths or {}).items()
    }
    own_paths: set[str] = set()
    for key in own_ids:
        own_paths.update(changed.get(key, set()))

    reasons_by_peer: dict[str, set[str]] = {}
    graph_index = issue_index(issues)
    own_dependencies = set(effective_dependencies(issue, graph_index))
    own_dependencies.update(
        str(ref.identifier or ref.id or "").strip()
        for ref in (issue.start_blocked_by or [])
        if str(ref.identifier or ref.id or "").strip()
    )
    for candidate in issues:
        if candidate is issue:
            continue
        if project_id and str(candidate.project_id or "").strip() != project_id:
            continue
        if is_terminal_status(candidate.state):
            continue
        candidate_ids = {
            str(value).strip()
            for value in (candidate.id, candidate.identifier)
            if str(value or "").strip()
        }
        if own_ids & candidate_ids:
            continue
        identifier = str(candidate.identifier or candidate.id or "").strip()
        if not identifier:
            continue
        reasons: set[str] = set()
        candidate_dependencies = set(
            effective_dependencies(candidate, graph_index)
        )
        candidate_dependencies.update(
            str(ref.identifier or ref.id or "").strip()
            for ref in (candidate.start_blocked_by or [])
            if str(ref.identifier or ref.id or "").strip()
        )
        if own_dependencies & candidate_ids or candidate_dependencies & own_ids:
            reasons.add("dependency")
        if (
            issue.parent_id
            and candidate.parent_id
            and str(issue.parent_id) == str(candidate.parent_id)
        ):
            reasons.add("epic-sibling")
        if str(issue.parent_id or "") in candidate_ids:
            reasons.add("epic-parent")
        if str(candidate.parent_id or "") in own_ids:
            reasons.add("epic-child")
        candidate_paths: set[str] = set()
        for key in candidate_ids:
            candidate_paths.update(changed.get(key, set()))
        if own_paths and candidate_paths and own_paths & candidate_paths:
            reasons.add("changed-path-overlap")
        if reasons:
            reasons_by_peer.setdefault(identifier, set()).update(reasons)

    return [
        PeerSuggestion(identifier=identifier, reasons=tuple(sorted(reasons)))
        for identifier, reasons in sorted(reasons_by_peer.items())
    ]
